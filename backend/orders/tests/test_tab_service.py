from decimal import Decimal
from unittest.mock import patch
import pytest
from orders.models import Tab
from orders.tab_service import TabService
from orders.tests.factories import OrderFactory, TabFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestGetPaymentConfig:
    def test_default_config_no_pos(self):
        restaurant = RestaurantFactory()
        config = TabService.get_payment_config(restaurant)
        assert config == {"payment_mode": "stripe", "payment_model": "upfront"}

    def test_tab_mode_no_pos(self):
        restaurant = RestaurantFactory(payment_model="tab")
        config = TabService.get_payment_config(restaurant)
        assert config == {"payment_mode": "stripe", "payment_model": "tab"}

    @patch("orders.tab_service.POSConnection")
    def test_pos_collected_with_tab(self, mock_pos_cls):
        restaurant = RestaurantFactory(payment_model="tab")
        mock_pos_cls.objects.get.return_value = type("POSConn", (), {"payment_mode": "pos_collected"})()
        config = TabService.get_payment_config(restaurant)
        assert config == {"payment_mode": "pos_collected", "payment_model": "tab"}


@pytest.mark.django_db
class TestGetOrCreateTab:
    def test_creates_new_tab(self):
        restaurant = RestaurantFactory()
        tab = TabService.get_or_create_tab(restaurant, "A3")
        assert tab.table_identifier == "A3"
        assert tab.status == "open"
        assert Tab.objects.count() == 1

    def test_returns_existing_open_tab(self):
        restaurant = RestaurantFactory()
        tab1 = TabService.get_or_create_tab(restaurant, "A3")
        tab2 = TabService.get_or_create_tab(restaurant, "A3")
        assert tab1.id == tab2.id
        assert Tab.objects.count() == 1

    def test_different_tables_get_different_tabs(self):
        restaurant = RestaurantFactory()
        tab1 = TabService.get_or_create_tab(restaurant, "A3")
        tab2 = TabService.get_or_create_tab(restaurant, "B1")
        assert tab1.id != tab2.id

    def test_rejects_order_on_closing_tab(self):
        tab = TabFactory(status="closing")
        with pytest.raises(ValueError, match="closing"):
            TabService.get_or_create_tab(tab.restaurant, tab.table_identifier)


@pytest.mark.django_db
class TestCloseTab:
    def test_close_tab_sets_status_to_closing(self):
        tab = TabFactory()
        TabService.close_tab(tab)
        tab.refresh_from_db()
        assert tab.status == "closing"

    def test_close_already_closing_tab_is_noop(self):
        tab = TabFactory(status="closing")
        TabService.close_tab(tab)
        tab.refresh_from_db()
        assert tab.status == "closing"
