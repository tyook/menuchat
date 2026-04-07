import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.utils import timezone

from integrations.adapters.base import PushResult
from integrations.adapters.toast import ToastAdapter, ToastAPIError
from integrations.encryption import encrypt_token
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory, OrderItemFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemModifierFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestToastAdapter:
    @pytest.fixture
    def setup(self):
        restaurant = RestaurantFactory()
        connection = POSConnectionFactory(
            restaurant=restaurant,
            pos_type="toast",
            external_location_id="toast-guid-123",
            oauth_access_token=encrypt_token("test_toast_token"),
            oauth_refresh_token="",
        )
        connection.oauth_token_expires_at = timezone.now() + timedelta(hours=1)
        connection.save()

        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat, name="Pad Thai")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("13.99")
        )
        modifier = MenuItemModifierFactory(
            menu_item=item, name="Extra Peanuts", price_adjustment=Decimal("1.00")
        )
        order = OrderFactory(
            restaurant=restaurant,
            subtotal=Decimal("14.99"),
            tax_amount=Decimal("1.35"),
            total_price=Decimal("16.34"),
        )
        order_item = OrderItemFactory(
            order=order,
            menu_item=item,
            variant=variant,
            quantity=1,
        )
        order_item.modifiers.add(modifier)
        return {
            "connection": connection,
            "restaurant": restaurant,
            "order": order,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    # --- Authentication ---

    @patch("integrations.adapters.toast.requests.post")
    def test_authenticate_success(self, mock_post, setup):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "token": {"accessToken": "new_token_abc", "expiresIn": 3600}
        }
        mock_post.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        token = adapter._authenticate()

        assert token == "new_token_abc"
        setup["connection"].refresh_from_db()
        assert setup["connection"].oauth_token_expires_at is not None
        mock_post.assert_called_once()

    @patch("integrations.adapters.toast.requests.post")
    def test_authenticate_failure_raises(self, mock_post, setup):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Invalid credentials"
        mock_post.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        with pytest.raises(ToastAPIError) as exc_info:
            adapter._authenticate()
        assert exc_info.value.status_code == 401

    # --- Token management ---

    def test_get_valid_token_returns_cached_when_not_expired(self, setup):
        adapter = ToastAdapter(setup["connection"])
        token = adapter._get_valid_token()
        assert token == "test_toast_token"

    @patch("integrations.adapters.toast.requests.post")
    def test_get_valid_token_refreshes_when_expired(self, mock_post, setup):
        setup["connection"].oauth_token_expires_at = timezone.now() - timedelta(hours=1)
        setup["connection"].save()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "token": {"accessToken": "refreshed_token", "expiresIn": 3600}
        }
        mock_post.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        token = adapter._get_valid_token()
        assert token == "refreshed_token"

    # --- Request with 401 retry ---

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_request_retries_on_401(self, mock_post, mock_request, setup):
        # First call returns 401, retry should re-authenticate then succeed
        resp_401 = MagicMock()
        resp_401.status_code = 401

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"ok": True}

        mock_request.side_effect = [resp_401, resp_200]

        mock_auth_resp = MagicMock()
        mock_auth_resp.status_code = 200
        mock_auth_resp.json.return_value = {
            "token": {"accessToken": "retry_token", "expiresIn": 3600}
        }
        mock_post.return_value = mock_auth_resp

        adapter = ToastAdapter(setup["connection"])
        resp = adapter._request("GET", "/test/path")
        assert resp.status_code == 200
        assert mock_request.call_count == 2

    @patch("integrations.adapters.toast.requests.request")
    def test_request_raises_on_4xx(self, mock_request, setup):
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.text = "Bad Request"
        mock_request.return_value = resp_400

        adapter = ToastAdapter(setup["connection"])
        with pytest.raises(ToastAPIError) as exc_info:
            adapter._request("GET", "/test/path", retry_on_401=False)
        assert exc_info.value.status_code == 400

    # --- Push order ---

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_push_order_success(self, mock_request, setup):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"guid": "toast_order_abc123"}
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is True
        assert result.external_order_id == "toast_order_abc123"
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert "orders/v2/orders" in call_args.args[1]

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_push_order_failure(self, mock_request, setup):
        mock_request.side_effect = ToastAPIError(400, "Restaurant closed")

        adapter = ToastAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is False
        assert "Restaurant closed" in result.error_message

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_push_order_with_stripe_payment(self, mock_request, setup):
        setup["connection"].payment_mode = "stripe"
        setup["connection"].save()
        setup["order"].payment_status = "paid"
        setup["order"].save()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"guid": "toast_order_paid"}
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is True
        call_kwargs = mock_request.call_args.kwargs
        payload = call_kwargs["json"]
        # Should include payment info in check
        assert "payments" in payload["checks"][0]
        assert payload["checks"][0]["payments"][0]["paymentStatus"] == "CAPTURED"

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_push_order_includes_modifiers(self, mock_request, setup):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"guid": "toast_order_mod"}
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        adapter.push_order(setup["order"])

        call_kwargs = mock_request.call_args.kwargs
        payload = call_kwargs["json"]
        selections = payload["checks"][0]["selections"]
        assert len(selections) == 1
        assert selections[0]["item"]["name"] == "Pad Thai"
        assert len(selections[0]["modifiers"]) == 1
        assert selections[0]["modifiers"][0]["modifier"]["name"] == "Extra Peanuts"

    # --- Get order status ---

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_get_order_status_success(self, mock_request, setup):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "OPEN"}
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        assert adapter.get_order_status("toast_order_abc") == "OPEN"

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_get_order_status_failure_returns_unknown(self, mock_request, setup):
        mock_request.side_effect = ToastAPIError(500, "Internal error")

        adapter = ToastAdapter(setup["connection"])
        assert adapter.get_order_status("toast_order_abc") == "unknown"

    # --- Cancel order ---

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_cancel_order_success(self, mock_request, setup):
        mock_resp = MagicMock()
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        assert adapter.cancel_order("toast_order_abc") is True
        call_args = mock_request.call_args
        assert call_args.kwargs["json"] == {"status": "CANCELLED"}

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_cancel_order_failure(self, mock_request, setup):
        mock_request.side_effect = ToastAPIError(404, "Order not found")

        adapter = ToastAdapter(setup["connection"])
        assert adapter.cancel_order("toast_order_abc") is False

    # --- Validate connection ---

    def test_validate_connection_with_valid_token(self, setup):
        adapter = ToastAdapter(setup["connection"])
        assert adapter.validate_connection() is True

    @patch("integrations.adapters.toast.requests.post")
    def test_validate_connection_with_expired_token_and_failed_auth(self, mock_post, setup):
        setup["connection"].oauth_token_expires_at = timezone.now() - timedelta(hours=1)
        setup["connection"].save()

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        assert adapter.validate_connection() is False

    # --- Refresh tokens ---

    @patch("integrations.adapters.toast.requests.post")
    def test_refresh_tokens_success(self, mock_post, setup):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "token": {"accessToken": "fresh_token", "expiresIn": 7200}
        }
        mock_post.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        assert adapter.refresh_tokens() is True

    @patch("integrations.adapters.toast.requests.post")
    def test_refresh_tokens_failure(self, mock_post, setup):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        assert adapter.refresh_tokens() is False

    # --- Get menu items ---

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_get_menu_items(self, mock_request, setup):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "name": "Lunch Menu",
                "groups": [
                    {
                        "name": "Entrees",
                        "items": [
                            {
                                "guid": "item-guid-1",
                                "name": "Pad Thai",
                                "price": 13.99,
                                "description": "Classic Thai noodles",
                            },
                            {
                                "guid": "item-guid-2",
                                "name": "Green Curry",
                                "price": 15.99,
                                "description": "Spicy green curry",
                            },
                        ],
                    }
                ],
            }
        ]
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        groups = adapter.get_menu_items()

        assert len(groups) == 1
        assert groups[0]["group_name"] == "Entrees"
        assert len(groups[0]["items"]) == 2
        assert groups[0]["items"][0]["toast_guid"] == "item-guid-1"
        assert groups[0]["items"][0]["name"] == "Pad Thai"
        assert groups[0]["items"][1]["name"] == "Green Curry"

    @patch("integrations.adapters.toast.ToastAdapter._request")
    def test_get_menu_items_empty(self, mock_request, setup):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_request.return_value = mock_resp

        adapter = ToastAdapter(setup["connection"])
        items = adapter.get_menu_items()
        assert items == []

    # --- Network failure ---

    @patch("integrations.adapters.toast.requests.request")
    def test_network_failure_on_request(self, mock_request, setup):
        import requests as req
        mock_request.side_effect = req.ConnectionError("Connection refused")

        adapter = ToastAdapter(setup["connection"])
        assert adapter.get_order_status("some-id") == "unknown"

    @patch("integrations.adapters.toast.requests.request")
    def test_network_timeout(self, mock_request, setup):
        import requests as req
        mock_request.side_effect = req.Timeout("Request timed out")

        adapter = ToastAdapter(setup["connection"])
        assert adapter.cancel_order("some-id") is False
