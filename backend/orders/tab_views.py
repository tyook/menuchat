from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from orders.models import Tab
from orders.serializers import ConfirmOrderSerializer, OrderResponseSerializer, TabResponseSerializer
from orders.services import OrderService
from orders.tab_service import TabService
from restaurants.models import Restaurant, RestaurantStaff


class TabDetailView(APIView):
    """GET /api/order/{slug}/tab/?table={id}"""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        table = request.query_params.get("table")
        if not table:
            return Response({"error": "table query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)
        tab = TabService.get_open_tab(restaurant, table)
        if not tab:
            return Response({"error": "No open tab for this table"}, status=status.HTTP_404_NOT_FOUND)
        return Response(TabResponseSerializer(tab).data)


class TabOrderView(APIView):
    """POST /api/order/{slug}/tab/order/ — place an order on a tab"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if restaurant.payment_model != "tab":
            return Response({"error": "This restaurant does not use tab mode"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        table_identifier = data.get("table_identifier", "")
        if not table_identifier:
            return Response({"error": "table_identifier is required for tab orders"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tab = TabService.get_or_create_tab(restaurant, table_identifier)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        validated_items, pricing = OrderService.validate_and_price_items(restaurant, data["items"])
        if not validated_items:
            return Response({"error": "No valid items in order"}, status=status.HTTP_400_BAD_REQUEST)

        user = OrderService.resolve_user_from_request(request)

        order = OrderService.create_order(
            restaurant, validated_items, pricing,
            user=user, order_status="confirmed", payment_status="deferred",
            raw_input=data.get("raw_input", ""),
            language=data.get("language", ""),
            table_identifier=table_identifier,
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            customer_allergies=data.get("allergies", []),
            tab=tab,
        )

        response_data = OrderResponseSerializer(order).data
        response_data["tab"] = TabResponseSerializer(tab).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class TabCloseView(APIView):
    """POST /api/order/{slug}/tab/close/"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)
        table_identifier = request.data.get("table_identifier")
        if not table_identifier:
            return Response({"error": "table_identifier is required"}, status=status.HTTP_400_BAD_REQUEST)
        tab = TabService.get_open_tab(restaurant, table_identifier)
        if not tab:
            return Response({"error": "No open tab for this table"}, status=status.HTTP_404_NOT_FOUND)
        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)


class KitchenTabCloseView(APIView):
    """POST /api/kitchen/tab/{tab_id}/close/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, tab_id):
        try:
            tab = Tab.objects.select_related("restaurant").get(id=tab_id)
        except Tab.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        user = request.user
        restaurant = tab.restaurant
        is_staff = (
            restaurant.owner == user
            or RestaurantStaff.objects.filter(user=user, restaurant=restaurant).exists()
        )
        if not is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)
        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)
