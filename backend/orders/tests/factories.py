import factory

from orders.models import Order, OrderItem, Tab
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


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    menu_item = factory.SubFactory(MenuItemFactory)
    variant = factory.SubFactory(MenuItemVariantFactory)
    quantity = 1
