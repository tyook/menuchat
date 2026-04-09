import factory

from orders.models import Order, OrderItem, Tab, TabPayment
from restaurants.tests.factories import (
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


class TabFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tab

    restaurant = factory.SubFactory(RestaurantFactory)
    table_identifier = factory.Sequence(lambda n: f"T{n}")


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    restaurant = factory.SubFactory(RestaurantFactory)
    raw_input = "Test order input"
    parsed_json = factory.LazyFunction(dict)
    total_price = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    user = None
    customer_name = ""
    customer_phone = ""
    tab = None


class TabPaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TabPayment

    tab = factory.SubFactory(TabFactory)
    type = "full"
    amount = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    tax_amount = factory.Faker("pydecimal", left_digits=1, right_digits=2, positive=True)


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    menu_item = factory.SubFactory(MenuItemFactory)
    variant = factory.SubFactory(MenuItemVariantFactory)
    quantity = 1
