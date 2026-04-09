from decimal import Decimal
import pytest
from orders.serializers import TabOrderSerializer, TabResponseSerializer, TabPaymentRequestSerializer
from orders.tests.factories import OrderFactory, TabFactory, TabPaymentFactory
from restaurants.tests.factories import (MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory, MenuVersionFactory)

@pytest.mark.django_db
class TestTabResponseSerializer:
    def test_serializes_tab_with_orders(self):
        tab = TabFactory()
        version = MenuVersionFactory(restaurant=tab.restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        OrderFactory(
            restaurant=tab.restaurant, tab=tab,
            subtotal=Decimal("10.00"), tax_amount=Decimal("0.89"), total_price=Decimal("10.89"),
        )
        data = TabResponseSerializer(tab).data
        assert data["table_identifier"] == tab.table_identifier
        assert data["status"] == "open"
        assert len(data["orders"]) == 1
        assert data["subtotal"] == "10.00"
        assert data["total"] == "10.89"
        assert data["amount_paid"] == "0.00"
        assert data["amount_remaining"] == "10.89"

@pytest.mark.django_db
class TestTabPaymentRequestSerializer:
    def test_valid_full_payment(self):
        tab = TabFactory()
        serializer = TabPaymentRequestSerializer(data={"tab_id": str(tab.id), "type": "full"})
        assert serializer.is_valid(), serializer.errors

    def test_split_even_requires_split_count(self):
        tab = TabFactory()
        serializer = TabPaymentRequestSerializer(data={"tab_id": str(tab.id), "type": "split_even"})
        assert not serializer.is_valid()
        assert "split_count" in serializer.errors

    def test_pay_by_item_requires_item_ids(self):
        tab = TabFactory()
        serializer = TabPaymentRequestSerializer(data={"tab_id": str(tab.id), "type": "pay_by_item"})
        assert not serializer.is_valid()
        assert "item_ids" in serializer.errors
