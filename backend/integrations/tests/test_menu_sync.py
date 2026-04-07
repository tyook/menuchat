import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from integrations.models import POSConnection
from integrations.services import MenuSyncService, OrderStatusService, ToastErrorTranslator
from integrations.tests.factories import POSConnectionFactory
from integrations.encryption import encrypt_token
from orders.tests.factories import OrderFactory
from restaurants.models import MenuCategory, MenuItem, MenuItemVariant, MenuVersion


@pytest.mark.django_db
class TestMenuSyncService:
    """Tests for MenuSyncService.sync_from_toast()."""

    def _make_toast_connection(self, **kwargs):
        return POSConnectionFactory(
            pos_type="toast",
            external_location_id="restaurant-guid-123",
            oauth_access_token=encrypt_token("tok"),
            **kwargs,
        )

    @patch("integrations.services.ToastAdapter")
    def test_sync_creates_menu_version_and_items(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        connection = self._make_toast_connection()

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_menu_items.return_value = [
            {
                "group_name": "Mains",
                "items": [
                    {"toast_guid": "g1", "name": "Burger", "price": 12.99, "description": "Juicy beef burger"},
                    {"toast_guid": "g2", "name": "Fries", "price": 4.50, "description": "Crispy fries"},
                ],
            },
        ]

        result = MenuSyncService.sync_from_toast(str(connection.restaurant.id))

        assert result["synced_items"] == 2
        assert result["version_id"] is not None

        version = MenuVersion.objects.get(id=result["version_id"])
        assert version.source == "toast_sync"
        assert version.is_active is True
        assert version.restaurant == connection.restaurant

        # Category preserves Toast group name
        categories = MenuCategory.objects.filter(version=version)
        assert categories.count() == 1
        assert categories.first().name == "Mains"

        items = MenuItem.objects.filter(category__version=version)
        assert items.count() == 2
        assert items.filter(name="Burger").exists()
        assert items.filter(name="Fries").exists()

        burger_variant = MenuItemVariant.objects.get(menu_item__name="Burger")
        assert burger_variant.price == Decimal("12.99")
        assert burger_variant.is_default is True

    @patch("integrations.services.ToastAdapter")
    def test_sync_preserves_multiple_groups_as_categories(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        connection = self._make_toast_connection()

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_menu_items.return_value = [
            {
                "group_name": "Appetizers",
                "items": [{"toast_guid": "g1", "name": "Wings", "price": 9.99, "description": ""}],
            },
            {
                "group_name": "Entrees",
                "items": [{"toast_guid": "g2", "name": "Steak", "price": 24.99, "description": ""}],
            },
        ]

        result = MenuSyncService.sync_from_toast(str(connection.restaurant.id))
        assert result["synced_items"] == 2

        version = MenuVersion.objects.get(id=result["version_id"])
        categories = MenuCategory.objects.filter(version=version).order_by("sort_order")
        assert categories.count() == 2
        assert categories[0].name == "Appetizers"
        assert categories[1].name == "Entrees"

        assert MenuItem.objects.filter(category=categories[0]).first().name == "Wings"
        assert MenuItem.objects.filter(category=categories[1]).first().name == "Steak"

    @patch("integrations.services.ToastAdapter")
    def test_sync_deactivates_previous_toast_versions(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        connection = self._make_toast_connection()

        # Create an existing toast_sync version
        old_version = MenuVersion.objects.create(
            restaurant=connection.restaurant,
            name="Old Toast Sync",
            source="toast_sync",
            is_active=True,
        )

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_menu_items.return_value = [
            {
                "group_name": "Menu",
                "items": [{"toast_guid": "g1", "name": "Pizza", "price": 15.00, "description": ""}],
            },
        ]

        result = MenuSyncService.sync_from_toast(str(connection.restaurant.id))

        old_version.refresh_from_db()
        assert old_version.is_active is False

        new_version = MenuVersion.objects.get(id=result["version_id"])
        assert new_version.is_active is True

    @patch("integrations.services.ToastAdapter")
    def test_sync_returns_empty_when_no_items(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        connection = self._make_toast_connection()

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_menu_items.return_value = []

        result = MenuSyncService.sync_from_toast(str(connection.restaurant.id))

        assert result["synced_items"] == 0
        assert result["version_id"] is None

    def test_sync_raises_when_toast_disabled(self, settings):
        settings.TOAST_POS_ENABLED = False
        connection = self._make_toast_connection()

        with pytest.raises(ValueError, match="Toast POS integration is disabled"):
            MenuSyncService.sync_from_toast(str(connection.restaurant.id))

    def test_sync_raises_when_no_toast_connection(self, settings):
        settings.TOAST_POS_ENABLED = True
        connection = self._make_toast_connection()
        # Change POS type to non-toast
        connection.pos_type = "square"
        connection.save()

        with pytest.raises(ValueError, match="No active Toast POS connection"):
            MenuSyncService.sync_from_toast(str(connection.restaurant.id))


@pytest.mark.django_db
class TestOrderStatusService:
    """Tests for OrderStatusService.poll_order_status()."""

    def _setup_synced_order(self, order_status="confirmed"):
        connection = POSConnectionFactory(
            pos_type="toast",
            external_location_id="guid-123",
            oauth_access_token=encrypt_token("tok"),
        )
        order = OrderFactory(
            restaurant=connection.restaurant,
            status=order_status,
            pos_sync_status="synced",
            external_order_id="toast-order-id-abc",
        )
        return order, connection

    @patch("integrations.services.ToastAdapter")
    def test_poll_updates_status_forward(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order(order_status="confirmed")

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "IN_PROGRESS"

        result = OrderStatusService.poll_order_status(str(order.id))

        assert result == "preparing"
        order.refresh_from_db()
        assert order.status == "preparing"

    @patch("integrations.services.ToastAdapter")
    def test_poll_skips_backward_transition(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order(order_status="preparing")

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "OPEN"

        result = OrderStatusService.poll_order_status(str(order.id))

        assert result is None
        order.refresh_from_db()
        assert order.status == "preparing"

    @patch("integrations.services.ToastAdapter")
    def test_poll_skips_same_status(self, MockAdapter, settings):
        settings.TOAST_POS_ENABLED = True
        order, _ = self._setup_synced_order(order_status="confirmed")

        mock_adapter = MagicMock()
        MockAdapter.return_value = mock_adapter
        mock_adapter.get_order_status.return_value = "OPEN"

        result = OrderStatusService.poll_order_status(str(order.id))
        assert result is None

    def test_poll_returns_none_when_disabled(self, settings):
        settings.TOAST_POS_ENABLED = False
        order, _ = self._setup_synced_order()

        result = OrderStatusService.poll_order_status(str(order.id))
        assert result is None

    def test_poll_returns_none_for_unsynced_order(self, settings):
        settings.TOAST_POS_ENABLED = True
        connection = POSConnectionFactory(
            pos_type="toast",
            external_location_id="guid-123",
            oauth_access_token=encrypt_token("tok"),
        )
        order = OrderFactory(
            restaurant=connection.restaurant,
            pos_sync_status="not_applicable",
        )

        result = OrderStatusService.poll_order_status(str(order.id))
        assert result is None


class TestToastErrorTranslator:
    """Tests for ToastErrorTranslator."""

    def test_translates_closed_restaurant(self):
        msg = ToastErrorTranslator.translate("Toast API error 400: Restaurant is closed")
        assert "closed" in msg.lower()
        assert "business hours" in msg.lower()

    def test_translates_out_of_stock(self):
        msg = ToastErrorTranslator.translate("item out of stock for guid-123")
        assert "out of stock" in msg.lower()

    def test_returns_default_for_unknown_error(self):
        msg = ToastErrorTranslator.translate("Some random error 500")
        assert "couldn't process" in msg.lower()

    def test_handles_empty_string(self):
        msg = ToastErrorTranslator.translate("")
        assert "couldn't process" in msg.lower()

    def test_handles_none(self):
        msg = ToastErrorTranslator.translate(None)
        assert "couldn't process" in msg.lower()
