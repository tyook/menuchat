from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from orders.models import Order, Tab, TabPayment
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestTabFullFlow:
    """Tests the complete tab lifecycle: order -> order again -> close -> pay -> closed."""

    @pytest.fixture
    def tab_restaurant(self):
        restaurant = RestaurantFactory(slug="full-flow", payment_model="tab", tax_rate=Decimal("8.875"))
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        burger = MenuItemFactory(category=cat, name="Burger")
        burger_var = MenuItemVariantFactory(menu_item=burger, price=Decimal("10.00"), is_default=True)
        fries = MenuItemFactory(category=cat, name="Fries")
        fries_var = MenuItemVariantFactory(menu_item=fries, price=Decimal("5.00"), is_default=True)
        return {
            "restaurant": restaurant,
            "burger": burger,
            "burger_var": burger_var,
            "fries": fries,
            "fries_var": fries_var,
        }

    @pytest.mark.django_db(transaction=True)
    @patch("orders.tab_views.broadcast_tab_update")
    @patch("orders.tab_service.broadcast_tab_update")
    @patch("orders.tab_payment_service.broadcast_tab_update")
    @patch("orders.tab_payment_service.stripe")
    def test_full_tab_lifecycle(self, mock_stripe, mock_broadcast_pay, mock_broadcast_svc, mock_broadcast_views, api_client, tab_restaurant):
        r = tab_restaurant

        # 1. Place first order
        resp1 = api_client.post(
            "/api/order/full-flow/tab/order/",
            {
                "items": [{"menu_item_id": r["burger"].id, "variant_id": r["burger_var"].id, "quantity": 2}],
                "raw_input": "Two burgers",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert resp1.status_code == status.HTTP_201_CREATED
        assert resp1.data["status"] == "confirmed"
        assert resp1.data["payment_status"] == "deferred"
        tab_id = resp1.data["tab"]["id"]

        # 2. Place second order on same tab
        resp2 = api_client.post(
            "/api/order/full-flow/tab/order/",
            {
                "items": [{"menu_item_id": r["fries"].id, "variant_id": r["fries_var"].id, "quantity": 1}],
                "raw_input": "One fries",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert resp2.status_code == status.HTTP_201_CREATED
        assert resp2.data["tab"]["id"] == tab_id

        # 3. Verify tab shows both orders
        resp_tab = api_client.get("/api/order/full-flow/tab/", {"table": "A3"})
        assert resp_tab.status_code == status.HTTP_200_OK
        assert len(resp_tab.data["orders"]) == 2
        # Subtotal: 20.00 + 5.00 = 25.00
        assert resp_tab.data["subtotal"] == "25.00"

        # 4. Close the tab
        resp_close = api_client.post(
            "/api/order/full-flow/tab/close/",
            {"table_identifier": "A3"},
            format="json",
        )
        assert resp_close.status_code == status.HTTP_200_OK
        assert resp_close.data["status"] == "closing"

        # 5. Create payment
        mock_intent = MagicMock()
        mock_intent.id = "pi_flow_test"
        mock_intent.client_secret = "pi_flow_test_secret"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        resp_pay = api_client.post(
            "/api/order/full-flow/tab/pay/",
            {"tab_id": tab_id, "type": "full"},
            format="json",
        )
        assert resp_pay.status_code == status.HTTP_201_CREATED
        assert resp_pay.data["client_secret"] == "pi_flow_test_secret"

        # 6. Confirm payment
        mock_intent_retrieved = MagicMock()
        mock_intent_retrieved.status = "succeeded"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent_retrieved

        payment_id = resp_pay.data["payment_id"]
        resp_confirm = api_client.post(f"/api/order/full-flow/tab/confirm-payment/{payment_id}/")
        assert resp_confirm.status_code == status.HTTP_200_OK
        assert resp_confirm.data["status"] == "closed"

        # 7. Verify all orders are now paid
        orders = Order.objects.filter(tab__id=tab_id)
        for order in orders:
            assert order.payment_status == "paid"
            assert order.paid_at is not None

        # 8. Verify new tab can be opened for same table
        resp_new = api_client.post(
            "/api/order/full-flow/tab/order/",
            {
                "items": [{"menu_item_id": r["burger"].id, "variant_id": r["burger_var"].id, "quantity": 1}],
                "raw_input": "One burger",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert resp_new.status_code == status.HTTP_201_CREATED
        assert resp_new.data["tab"]["id"] != tab_id
