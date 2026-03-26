import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from rest_framework import status

from integrations.adapters.base import PushResult
from integrations.models import POSConnection, POSSyncLog
from integrations.tests.factories import POSConnectionFactory
from orders.models import Order
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestPOSIntegrationEndToEnd:
    @pytest.fixture
    def full_setup(self):
        restaurant = RestaurantFactory(slug="e2e-test", tax_rate=Decimal("8.875"))
        connection = POSConnectionFactory(
            restaurant=restaurant,
            pos_type="square",
            payment_mode="stripe",
        )
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        return {
            "restaurant": restaurant,
            "connection": connection,
            "item": item,
            "variant": variant,
        }

    @patch("orders.broadcast.broadcast_order_to_kitchen")
    @patch("orders.views.dispatch_order_to_pos")
    def test_order_confirm_triggers_dispatch(self, mock_task, mock_broadcast, api_client, full_setup):
        """Confirm an order (pos_collected mode) and verify the POS dispatch task is enqueued."""
        # Update the connection to pos_collected so ConfirmOrderView dispatches immediately
        full_setup["connection"].payment_mode = "pos_collected"
        full_setup["connection"].save()

        data = {
            "items": [
                {
                    "menu_item_id": full_setup["item"].id,
                    "variant_id": full_setup["variant"].id,
                    "quantity": 1,
                    "modifier_ids": [],
                }
            ],
            "raw_input": "one burger",
            "table_identifier": "7",
        }
        response = api_client.post(
            "/api/order/e2e-test/confirm/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        mock_task.delay.assert_called_once()

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_dispatch_creates_sync_log_on_success(self, mock_get_client, full_setup):
        """Run the dispatch service and verify sync log is created."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"id": "sq_e2e_order"}}
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        from orders.tests.factories import OrderFactory
        order = OrderFactory(restaurant=full_setup["restaurant"])

        from integrations.services import POSDispatchService
        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"
        assert order.external_order_id == "sq_e2e_order"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "success"

    def test_menu_endpoint_returns_payment_mode(self, api_client, full_setup):
        """Verify the public menu endpoint includes payment_mode."""
        response = api_client.get("/api/order/e2e-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert "payment_mode" in response.data
