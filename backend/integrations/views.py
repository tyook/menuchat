from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import POSConnection, POSSyncLog
from integrations.serializers import (
    POSConnectionSerializer,
    POSConnectionUpdateSerializer,
    POSSyncLogSerializer,
)
from integrations.tasks import dispatch_order_to_pos
from orders.models import Order
from restaurants.models import Restaurant


class RestaurantPOSMixin:
    def get_restaurant(self, slug):
        try:
            return Restaurant.objects.get(slug=slug, owner=self.request.user)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")


class POSConnectionDetailView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        restaurant = self.get_restaurant(slug)
        try:
            connection = POSConnection.objects.get(restaurant=restaurant)
        except POSConnection.DoesNotExist:
            return Response(
                {"pos_type": "none", "is_connected": False, "payment_mode": "stripe"}
            )
        return Response(POSConnectionSerializer(connection).data)

    def patch(self, request, slug):
        restaurant = self.get_restaurant(slug)
        try:
            connection = POSConnection.objects.get(restaurant=restaurant)
        except POSConnection.DoesNotExist:
            raise NotFound("No POS connection found for this restaurant.")
        serializer = POSConnectionUpdateSerializer(
            connection, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(POSConnectionSerializer(connection).data)

    def delete(self, request, slug):
        restaurant = self.get_restaurant(slug)
        POSConnection.objects.filter(restaurant=restaurant).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


ENABLED_POS_VENDORS = {"square", "none"}


class POSVendorSelectView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        restaurant = self.get_restaurant(slug)
        pos_type = request.data.get("pos_type")

        if pos_type not in ENABLED_POS_VENDORS:
            return Response(
                {"error": f"Unsupported POS type: {pos_type}. Allowed: {', '.join(sorted(ENABLED_POS_VENDORS))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection, _ = POSConnection.objects.update_or_create(
            restaurant=restaurant,
            defaults={"pos_type": pos_type, "is_active": False},
        )
        return Response(POSConnectionSerializer(connection).data)


class POSSyncLogListView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        restaurant = self.get_restaurant(slug)
        logs = POSSyncLog.objects.filter(
            pos_connection__restaurant=restaurant
        ).select_related("order")

        status_filter = request.query_params.get("status")
        if status_filter:
            logs = logs.filter(status=status_filter)

        return Response(POSSyncLogSerializer(logs, many=True).data)


class RetryOrderSyncView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, order_id):
        restaurant = self.get_restaurant(slug)
        try:
            order = Order.objects.get(id=order_id, restaurant=restaurant)
        except Order.DoesNotExist:
            raise NotFound("Order not found.")
        order.pos_sync_status = "pending"
        order.save(update_fields=["pos_sync_status"])
        dispatch_order_to_pos.delay(str(order.id))
        return Response({"status": "retry_queued"})


class RetryAllSyncView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        restaurant = self.get_restaurant(slug)
        failed_orders = Order.objects.filter(
            restaurant=restaurant, pos_sync_status="failed"
        )
        count = failed_orders.count()
        for order in failed_orders:
            order.pos_sync_status = "pending"
            order.save(update_fields=["pos_sync_status"])
            dispatch_order_to_pos.delay(str(order.id))
        return Response({"status": "retry_queued", "count": count})


class POSSyncLogDetailView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, log_id):
        restaurant = self.get_restaurant(slug)
        try:
            log = POSSyncLog.objects.get(
                id=log_id, pos_connection__restaurant=restaurant
            )
        except POSSyncLog.DoesNotExist:
            raise NotFound("Sync log not found.")
        new_status = request.data.get("status")
        if new_status == "manually_resolved":
            log.status = POSSyncLog.Status.MANUALLY_RESOLVED
            log.save(update_fields=["status"])
            Order.objects.filter(id=log.order_id).update(
                pos_sync_status="manually_resolved"
            )
        return Response(POSSyncLogSerializer(log).data)


from django.conf import settings as django_settings
from django.http import HttpResponseRedirect
from django.utils.dateparse import parse_datetime
from square import Square as SquareClient

import hashlib
import hmac

from integrations.encryption import encrypt_token


def _sign_oauth_state(payload: str) -> str:
    """HMAC-sign an OAuth state string to prevent tampering."""
    from django.conf import settings as s
    key = s.SECRET_KEY.encode()
    sig = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


def _verify_oauth_state(state: str) -> tuple[str, str]:
    """Verify and parse an HMAC-signed OAuth state. Returns (slug, user_id)."""
    from django.conf import settings as s
    parts = state.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError("Invalid OAuth state format")
    slug, user_id, sig = parts
    key = s.SECRET_KEY.encode()
    expected = hmac.new(key, f"{slug}:{user_id}".encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid OAuth state signature")
    return slug, user_id


class POSConnectInitiateView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        restaurant = self.get_restaurant(slug)
        pos_type = request.data.get("pos_type")

        if pos_type == "square":
            state = _sign_oauth_state(f"{restaurant.slug}:{request.user.id}")
            auth_url = (
                f"https://connect.squareup.com/oauth2/authorize"
                f"?client_id={django_settings.POS_SQUARE_CLIENT_ID}"
                f"&scope=ORDERS_WRITE+ORDERS_READ+MERCHANT_PROFILE_READ"
                f"&state={state}"
                f"&session=false"
            )
            return Response({"auth_url": auth_url})

        return Response(
            {"error": f"Unsupported POS type: {pos_type}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class SquareOAuthCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            return Response(
                {"error": "Missing code or state"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slug, user_id = _verify_oauth_state(state)
        except ValueError:
            return Response(
                {"error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            restaurant = Restaurant.objects.get(slug=slug, owner_id=user_id)
        except Restaurant.DoesNotExist:
            return Response(
                {"error": "Restaurant not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = SquareClient(environment="production")
        result = client.o_auth.obtain_token(
            body={
                "client_id": django_settings.POS_SQUARE_CLIENT_ID,
                "client_secret": django_settings.POS_SQUARE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            }
        )

        if not result.is_success():
            frontend_url = getattr(django_settings, "FRONTEND_URL", "http://localhost:3000")
            return HttpResponseRedirect(
                f"{frontend_url}/account/restaurants/{slug}/integrations?error=oauth_failed"
            )

        token_data = result.body
        connection, _ = POSConnection.objects.update_or_create(
            restaurant=restaurant,
            defaults={
                "pos_type": POSConnection.POSType.SQUARE,
                "is_active": True,
                "oauth_access_token": encrypt_token(token_data["access_token"]),
                "oauth_refresh_token": encrypt_token(
                    token_data.get("refresh_token", "")
                ),
                "oauth_token_expires_at": parse_datetime(
                    token_data.get("expires_at", "")
                ),
            },
        )

        frontend_url = getattr(django_settings, "FRONTEND_URL", "http://localhost:3000")
        return HttpResponseRedirect(
            f"{frontend_url}/account/restaurants/{slug}/integrations?connected=square"
        )
