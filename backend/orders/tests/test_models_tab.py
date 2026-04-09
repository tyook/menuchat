import pytest
from django.db import IntegrityError
from django.utils import timezone
from orders.models import Tab
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestTabModel:
    def test_create_tab(self):
        restaurant = RestaurantFactory()
        tab = Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        assert tab.status == "open"
        assert tab.table_identifier == "A3"
        assert tab.opened_at is not None
        assert tab.closed_at is None
        assert str(tab.id)

    def test_only_one_open_tab_per_table(self):
        restaurant = RestaurantFactory()
        Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        with pytest.raises(IntegrityError):
            Tab.objects.create(restaurant=restaurant, table_identifier="A3")

    def test_can_open_new_tab_after_closing(self):
        restaurant = RestaurantFactory()
        tab1 = Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        tab1.status = "closed"
        tab1.closed_at = timezone.now()
        tab1.save()
        tab2 = Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        assert tab2.status == "open"
        assert tab2.id != tab1.id

    def test_tab_totals_computed_from_orders(self):
        restaurant = RestaurantFactory()
        tab = Tab.objects.create(restaurant=restaurant, table_identifier="B1")
        assert tab.subtotal == 0
        assert tab.tax_amount == 0
        assert tab.total == 0
