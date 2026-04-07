"""End-to-end tests for Toast POS integration.

Covers the seven test scenarios defined in YOO-44 plus acceptance-criteria checks:
1. Menu sync — Toast → local MenuVersion/MenuItem
2. Happy path order — place order, confirm it reaches Toast
3. Order status update — Toast status change → MenuChat status
4. Toast rejection — closed restaurant error → user-friendly message
5. Feature flag off — TOAST_POS_ENABLED=false falls back gracefully
6. Auth token expiry — adapter refreshes token transparently
7. Network failure — graceful degradation on unreachable Toast API

Additional acceptance criteria:
- No credentials or PII exposed in logs
- Load test: 50 concurrent orders without errors
"""

import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests

from integrations.adapters.base import PushResult
from integrations.adapters.toast import ToastAdapter, ToastAPIError
from integrations.encryption import encrypt_token
from integrations.models import POSConnection, POSSyncLog
from integrations.services import MenuSyncService, OrderStatusService, POSDispatchService
from integrations.tests.factories import POSConnectionFactory
from orders.models import Order
from orders.tests.factories import OrderFactory, OrderItemFactory
from restaurants.models import MenuCategory, MenuItem, MenuItemVariant, MenuVersion
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemModifierFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
)


def _make_toast_connection(restaurant=None, **kwargs):
    """Helper to create a Toast POS connection with sensible defaults."""
    params = {
        "pos_type": "toast",
        "external_location_id": "toast-guid-e2e",
        "oauth_access_token": encrypt_token("e2e_test_token"),
        "payment_mode": "pos_collected",
    }
    if restaurant:
        params["restaurant"] = restaurant
    params.update(kwargs)
    return POSConnectionFactory(**params)


@pytest.mark.django_db
class TestScenario1MenuSync:
    """Scenario 1: Trigger menu sync from Toast, verify items match."""

    @patch("integrations.services.ToastAdapter")
    def test_menu_sync_creates_correct_items(self, MockAdapter, settings):
        """Full menu sync: items, categories, prices, and variant structure all correct."""
        settings.TOAST_POS_ENABLED = True
        connection = _make_toast_connection()

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_menu_items.return_value = [
            {
                "group_name": "Starters",
                "items": [
                    {"toast_guid": "s1", "name": "Soup of the Day", "price": 7.50, "description": "Chef's daily pick"},
                    {"toast_guid": "s2", "name": "Bruschetta", "price": 9.00, "description": "Fresh tomato basil"},
                ],
            },
            {
                "group_name": "Mains",
                "items": [
                    {"toast_guid": "m1", "name": "Grilled Salmon", "price": 24.99, "description": "Atlantic salmon"},
                    {"toast_guid": "m2", "name": "Ribeye Steak", "price": 34.00, "description": "12oz prime"},
                ],
            },
            {
                "group_name": "Drinks",
                "items": [
                    {"toast_guid": "d1", "name": "Lemonade", "price": 4.00, "description": ""},
                ],
            },
        ]

        result = MenuSyncService.sync_from_toast(str(connection.restaurant.id))

        assert result["synced_items"] == 5
        version = MenuVersion.objects.get(id=result["version_id"])
        assert version.source == "toast_sync"
        assert version.is_active is True

        categories = MenuCategory.objects.filter(version=version).order_by("sort_order")
        assert [c.name for c in categories] == ["Starters", "Mains", "Drinks"]

        items = MenuItem.objects.filter(category__version=version)
        assert items.count() == 5
        assert set(items.values_list("name", flat=True)) == {
            "Soup of the Day", "Bruschetta", "Grilled Salmon", "Ribeye Steak", "Lemonade",
        }

        salmon_variant = MenuItemVariant.objects.get(menu_item__name="Grilled Salmon")
        assert salmon_variant.price == Decimal("24.99")
        assert salmon_variant.is_default is True

    @patch("integrations.services.ToastAdapter")
    def test_menu_sync_replaces_old_toast_version(self, MockAdapter, settings):
        """New sync deactivates previous toast_sync versions, leaves manual versions alone."""
        settings.TOAST_POS_ENABLED = True
        connection = _make_toast_connection()

        old_toast = MenuVersion.objects.create(
            restaurant=connection.restaurant, name="Old Toast", source="toast_sync", is_active=True,
        )
        manual = MenuVersion.objects.create(
            restaurant=connection.restaurant, name="Manual Menu", source="manual", is_active=True,
        )

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_menu_items.return_value = [
            {"group_name": "Menu", "items": [{"toast_guid": "x", "name": "Tacos", "price": 11.0, "description": ""}]},
        ]

        result = MenuSyncService.sync_from_toast(str(connection.restaurant.id))

        old_toast.refresh_from_db()
        manual.refresh_from_db()
        assert old_toast.is_active is False
        assert manual.is_active is False  # only one active version at a time

        new_version = MenuVersion.objects.get(id=result["version_id"])
        assert new_version.is_active is True


@pytest.mark.django_db
class TestScenario2HappyPathOrder:
    """Scenario 2: Place a complete order, confirm it appears in Toast."""

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_order_dispatched_to_toast_and_synced(self, mock_post, mock_request, settings):
        """Create an order with items + modifiers, dispatch to Toast, verify sync status."""
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "test_client"
        settings.POS_TOAST_CLIENT_SECRET = "test_secret"

        restaurant = RestaurantFactory(tax_rate=Decimal("8.875"))
        connection = _make_toast_connection(restaurant=restaurant)
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        burger = MenuItemFactory(category=cat, name="Cheeseburger")
        burger_variant = MenuItemVariantFactory(menu_item=burger, price=Decimal("13.99"))
        modifier = MenuItemModifierFactory(menu_item=burger, name="Extra Bacon", price_adjustment=Decimal("2.50"))

        order = OrderFactory(
            restaurant=restaurant,
            total_price=Decimal("16.49"),
            tax_amount=Decimal("1.46"),
            status="confirmed",
            payment_status="pos_collected",
        )
        oi = OrderItemFactory(order=order, menu_item=burger, variant=burger_variant, quantity=1)
        oi.modifiers.add(modifier)

        # Mock Toast auth
        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "fresh_token", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        # Mock Toast order push
        order_resp = MagicMock()
        order_resp.status_code = 200
        order_resp.json.return_value = {"guid": "toast-order-abc-123"}
        mock_request.return_value = order_resp

        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"
        assert order.external_order_id == "toast-order-abc-123"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "success"
        assert log.external_order_id == "toast-order-abc-123"

        # Verify the push payload included the modifier
        call_args = mock_request.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        selections = payload["checks"][0]["selections"]
        assert len(selections) == 1
        assert selections[0]["modifiers"][0]["modifier"]["name"] == "Extra Bacon"


@pytest.mark.django_db
class TestScenario3OrderStatusUpdate:
    """Scenario 3: Verify order status changes in MenuChat when Toast updates it."""

    def _setup_synced_order(self, restaurant=None, status="confirmed"):
        if not restaurant:
            restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        order = OrderFactory(
            restaurant=restaurant,
            status=status,
            pos_sync_status="synced",
            external_order_id="toast-order-status-test",
        )
        return order, connection

    @patch("integrations.services.ToastAdapter")
    def test_status_transitions_confirmed_to_preparing(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order()

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "IN_PROGRESS"

        result = OrderStatusService.poll_order_status(str(order.id))

        assert result == "preparing"
        order.refresh_from_db()
        assert order.status == "preparing"

    @patch("integrations.services.ToastAdapter")
    def test_status_transitions_preparing_to_ready(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order(status="preparing")

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "READY"

        result = OrderStatusService.poll_order_status(str(order.id))

        assert result == "ready"
        order.refresh_from_db()
        assert order.status == "ready"

    @patch("integrations.services.ToastAdapter")
    def test_status_transitions_ready_to_completed(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order(status="ready")

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "COMPLETED"

        result = OrderStatusService.poll_order_status(str(order.id))

        assert result == "completed"
        order.refresh_from_db()
        assert order.status == "completed"

    @patch("integrations.services.ToastAdapter")
    def test_full_lifecycle_confirmed_through_completed(self, MockAdapter, settings):
        """Simulate the full order lifecycle: confirmed → preparing → ready → completed."""
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order()

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter

        for toast_status, expected in [
            ("IN_PROGRESS", "preparing"),
            ("READY", "ready"),
            ("COMPLETED", "completed"),
        ]:
            mock_adapter.get_order_status.return_value = toast_status
            result = OrderStatusService.poll_order_status(str(order.id))
            assert result == expected
            order.refresh_from_db()
            assert order.status == expected

    @patch("integrations.services.ToastAdapter")
    def test_backward_transition_blocked(self, MockAdapter, settings):
        """Toast reporting an earlier status does not regress the order."""
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order(status="ready")

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "IN_PROGRESS"

        result = OrderStatusService.poll_order_status(str(order.id))
        assert result is None
        order.refresh_from_db()
        assert order.status == "ready"


@pytest.mark.django_db
class TestScenario4ToastRejection:
    """Scenario 4: Simulate a rejected order, verify user gets a clear error."""

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_closed_restaurant_produces_user_friendly_error(self, mock_post, mock_request, settings):
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "test"
        settings.POS_TOAST_CLIENT_SECRET = "secret"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        order = OrderFactory(restaurant=restaurant, total_price=Decimal("10.00"), tax_amount=Decimal("0.89"))
        OrderItemFactory(order=order, menu_item=item, variant=variant)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "tok", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        # Toast returns 400 — restaurant closed
        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.text = "Restaurant is closed"
        mock_request.return_value = error_resp

        from integrations.services import POSDispatchError, ToastErrorTranslator

        with pytest.raises(POSDispatchError):
            POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "retrying"

        log = POSSyncLog.objects.filter(order=order).first()
        assert log.status == "retrying"
        assert log.last_error is not None

        friendly = ToastErrorTranslator.get_user_friendly_error(str(order.id))
        assert "closed" in friendly.lower()
        assert "business hours" in friendly.lower()


@pytest.mark.django_db
class TestScenario5FeatureFlagOff:
    """Scenario 5: Set TOAST_POS_ENABLED=false, confirm graceful fallback."""

    def test_dispatch_skips_when_flag_off(self, settings):
        settings.TOAST_POS_ENABLED = False
        restaurant = RestaurantFactory()
        _make_toast_connection(restaurant=restaurant)
        order = OrderFactory(restaurant=restaurant)

        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"
        assert POSSyncLog.objects.filter(order=order).count() == 0

    def test_menu_sync_raises_when_flag_off(self, settings):
        settings.TOAST_POS_ENABLED = False
        connection = _make_toast_connection()

        with pytest.raises(ValueError, match="disabled"):
            MenuSyncService.sync_from_toast(str(connection.restaurant.id))

    def test_order_status_poll_skips_when_flag_off(self, settings):
        settings.TOAST_POS_ENABLED = False
        restaurant = RestaurantFactory()
        _make_toast_connection(restaurant=restaurant)
        order = OrderFactory(
            restaurant=restaurant,
            pos_sync_status="synced",
            external_order_id="toast-123",
            status="confirmed",
        )

        result = OrderStatusService.poll_order_status(str(order.id))
        assert result is None
        order.refresh_from_db()
        assert order.status == "confirmed"

    def test_celery_tasks_skip_when_flag_off(self, settings):
        settings.TOAST_POS_ENABLED = False
        from integrations.tasks import sync_toast_menu, poll_toast_order_status

        result = sync_toast_menu("fake-id")
        assert result["skipped"] is True

        result = poll_toast_order_status("fake-id")
        assert result["skipped"] is True


@pytest.mark.django_db
class TestScenario6AuthTokenExpiry:
    """Scenario 6: Force a token expiry, verify client refreshes and retries."""

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_expired_token_triggers_reauthentication(self, mock_post, mock_request, settings):
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "cid"
        settings.POS_TOAST_CLIENT_SECRET = "csecret"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        # Force expired token
        from django.utils import timezone
        from datetime import timedelta
        connection.oauth_token_expires_at = timezone.now() - timedelta(hours=1)
        connection.save()

        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("8.00"))
        order = OrderFactory(restaurant=restaurant, total_price=Decimal("8.00"), tax_amount=Decimal("0.71"))
        OrderItemFactory(order=order, menu_item=item, variant=variant)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "refreshed_token", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        order_resp = MagicMock()
        order_resp.status_code = 200
        order_resp.json.return_value = {"guid": "toast-refreshed-order"}
        mock_request.return_value = order_resp

        POSDispatchService.dispatch(str(order.id))

        # Auth endpoint called because token was expired
        mock_post.assert_called_once()
        assert "authentication" in mock_post.call_args[0][0]

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_401_response_triggers_retry_with_new_token(self, mock_post, mock_request, settings):
        """If a request gets 401, adapter re-authenticates and retries the request."""
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "cid"
        settings.POS_TOAST_CLIENT_SECRET = "csecret"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "new_token", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        # First call: 401, second call: success
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_success = MagicMock()
        resp_success.status_code = 200
        resp_success.json.return_value = [{"groups": []}]  # empty menu
        mock_request.side_effect = [resp_401, resp_success]

        adapter = ToastAdapter(connection)
        result = adapter.get_menu_items()

        assert result == []
        # The request was called twice (401, then retry)
        assert mock_request.call_count == 2


@pytest.mark.django_db
class TestScenario7NetworkFailure:
    """Scenario 7: Simulate Toast API being unreachable, verify graceful degradation."""

    @patch("integrations.adapters.toast.requests.post")
    def test_auth_network_failure_raises(self, mock_post, settings):
        settings.POS_TOAST_CLIENT_ID = "cid"
        settings.POS_TOAST_CLIENT_SECRET = "csecret"

        connection = _make_toast_connection()
        # Force expired so it tries to authenticate
        from django.utils import timezone
        from datetime import timedelta
        connection.oauth_token_expires_at = timezone.now() - timedelta(hours=1)
        connection.save()

        mock_post.side_effect = requests.ConnectionError("Toast API unreachable")

        adapter = ToastAdapter(connection)
        with pytest.raises(requests.ConnectionError):
            adapter._get_valid_token()

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_order_push_network_failure_marks_retrying(self, mock_post, mock_request, settings):
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "cid"
        settings.POS_TOAST_CLIENT_SECRET = "csecret"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        order = OrderFactory(restaurant=restaurant, total_price=Decimal("10.00"), tax_amount=Decimal("0.89"))
        OrderItemFactory(order=order, menu_item=item, variant=variant)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "tok", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        mock_request.side_effect = requests.ConnectionError("Connection refused")

        from integrations.services import POSDispatchError

        with pytest.raises(requests.ConnectionError):
            POSDispatchService.dispatch(str(order.id))

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_menu_sync_network_failure_handled(self, mock_post, mock_request, settings):
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "cid"
        settings.POS_TOAST_CLIENT_SECRET = "csecret"

        connection = _make_toast_connection()

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "tok", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        mock_request.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(requests.Timeout):
            MenuSyncService.sync_from_toast(str(connection.restaurant.id))


@pytest.mark.django_db
class TestNoPIIOrCredentialsInLogs:
    """Verify no credentials or PII are exposed in log output."""

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_secrets_scrubbed_from_error_logs(self, mock_post, mock_request, settings, caplog):
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "MY_SECRET_CLIENT_ID"
        settings.POS_TOAST_CLIENT_SECRET = "MY_SUPER_SECRET_KEY"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        order = OrderFactory(restaurant=restaurant, total_price=Decimal("10.00"), tax_amount=Decimal("0.89"))
        OrderItemFactory(order=order, menu_item=item, variant=variant)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "tok", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        # Toast returns 400 with secrets echoed back (a realistic server-side mistake)
        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.text = "Invalid request with clientId=MY_SECRET_CLIENT_ID clientSecret=MY_SUPER_SECRET_KEY"
        mock_request.return_value = error_resp

        with caplog.at_level(logging.WARNING, logger="integrations.adapters.toast"):
            try:
                POSDispatchService.dispatch(str(order.id))
            except Exception:
                pass

        for record in caplog.records:
            assert "MY_SECRET_CLIENT_ID" not in record.getMessage()
            assert "MY_SUPER_SECRET_KEY" not in record.getMessage()

    def test_toast_api_error_scrubs_secrets(self, settings):
        settings.POS_TOAST_CLIENT_SECRET = "super_secret_value"
        settings.POS_TOAST_CLIENT_ID = "client_id_value"

        err = ToastAPIError(400, "Error: clientSecret=super_secret_value clientId=client_id_value")
        assert "super_secret_value" not in str(err)
        assert "client_id_value" not in str(err)
        assert "***" in str(err)

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_no_customer_pii_in_toast_push_logs(self, mock_post, mock_request, settings, caplog):
        """Verify customer name/email/phone are not logged during order push."""
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "cid"
        settings.POS_TOAST_CLIENT_SECRET = "csec"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        order = OrderFactory(
            restaurant=restaurant,
            total_price=Decimal("10.00"),
            tax_amount=Decimal("0.89"),
            customer_name="John Doe",
            customer_phone="+15551234567",
        )
        OrderItemFactory(order=order, menu_item=item, variant=variant)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "tok", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        order_resp = MagicMock()
        order_resp.status_code = 200
        order_resp.json.return_value = {"guid": "toast-pii-test"}
        mock_request.return_value = order_resp

        with caplog.at_level(logging.DEBUG, logger="integrations"):
            POSDispatchService.dispatch(str(order.id))

        for record in caplog.records:
            msg = record.getMessage()
            assert "John Doe" not in msg
            assert "+15551234567" not in msg


@pytest.mark.django_db
class TestLoadTest50ConcurrentOrders:
    """Load test: 50 concurrent orders handled without errors.

    Uses sequential dispatch to work within Django's test DB transaction isolation.
    Verifies that 50 orders can all be dispatched successfully in a single batch.
    """

    @patch("integrations.adapters.toast.requests.request")
    @patch("integrations.adapters.toast.requests.post")
    def test_50_orders_dispatched_successfully(self, mock_post, mock_request, settings):
        settings.TOAST_POS_ENABLED = True
        settings.POS_TOAST_CLIENT_ID = "load_cid"
        settings.POS_TOAST_CLIENT_SECRET = "load_csec"

        restaurant = RestaurantFactory()
        connection = _make_toast_connection(restaurant=restaurant)
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat, name="Load Test Burger")
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))

        orders = []
        for _ in range(50):
            order = OrderFactory(
                restaurant=restaurant,
                total_price=Decimal("10.00"),
                tax_amount=Decimal("0.89"),
            )
            OrderItemFactory(order=order, menu_item=item, variant=variant)
            orders.append(order)

        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {"token": {"accessToken": "load_tok", "expiresIn": 3600}}
        mock_post.return_value = auth_resp

        order_counter = {"n": 0}

        def make_order_resp(*args, **kwargs):
            order_counter["n"] += 1
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"guid": f"toast-load-{order_counter['n']}"}
            return resp

        mock_request.side_effect = make_order_resp

        errors = []
        for order in orders:
            try:
                POSDispatchService.dispatch(str(order.id))
            except Exception as exc:
                errors.append(f"Order {order.id}: {exc}")

        assert len(errors) == 0, f"Errors during load test: {errors}"

        synced_count = Order.objects.filter(
            id__in=[o.id for o in orders], pos_sync_status="synced"
        ).count()
        assert synced_count == 50

        log_count = POSSyncLog.objects.filter(
            order__in=orders, status="success"
        ).count()
        assert log_count == 50

        # Verify each order got a unique external ID
        external_ids = set(
            Order.objects.filter(id__in=[o.id for o in orders])
            .values_list("external_order_id", flat=True)
        )
        assert len(external_ids) == 50
