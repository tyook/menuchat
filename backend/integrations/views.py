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
