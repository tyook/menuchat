from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone
from orders.models import Order, Tab, TabPayment
from orders.tests.factories import OrderFactory, TabFactory, TabPaymentFactory
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


@pytest.mark.django_db
class TestOrderTabRelation:
    def test_order_can_have_tab(self):
        tab = TabFactory()
        order = OrderFactory(restaurant=tab.restaurant, tab=tab)
        assert order.tab == tab
        assert order in tab.orders.all()

    def test_order_tab_is_optional(self):
        order = OrderFactory()
        assert order.tab is None

    def test_deferred_payment_status(self):
        tab = TabFactory()
        order = OrderFactory(restaurant=tab.restaurant, tab=tab, payment_status="deferred", status="confirmed")
        order.full_clean()
        assert order.payment_status == "deferred"

    def test_tab_totals_with_orders(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=10, tax_amount=1, total_price=11)
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=20, tax_amount=2, total_price=22)
        assert tab.subtotal == 30
        assert tab.tax_amount == 3
        assert tab.total == 33


@pytest.mark.django_db
class TestTabPaymentModel:
    def test_create_full_payment(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=20, tax_amount=2, total_price=22)
        payment = TabPayment.objects.create(tab=tab, type="full", amount=Decimal("22.00"), tax_amount=Decimal("2.00"))
        assert payment.payment_status == "pending"
        assert payment.paid_at is None

    def test_create_split_even_payment(self):
        tab = TabFactory()
        payment = TabPayment.objects.create(tab=tab, type="split_even", amount=Decimal("11.00"), tax_amount=Decimal("1.00"), split_count=2)
        assert payment.type == "split_even"
        assert payment.split_count == 2

    def test_tab_amount_paid_tracks_payments(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=40, tax_amount=4, total_price=44)
        TabPayment.objects.create(tab=tab, type="split_even", amount=Decimal("22.00"), tax_amount=Decimal("2.00"), payment_status="paid")
        assert tab.amount_paid == Decimal("22.00")
        assert tab.amount_remaining == Decimal("22.00")

    def test_tab_fully_paid(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=20, tax_amount=2, total_price=22)
        TabPayment.objects.create(tab=tab, type="full", amount=Decimal("22.00"), tax_amount=Decimal("2.00"), payment_status="paid")
        assert tab.amount_remaining == 0
