from decimal import Decimal
import pytest
from restaurants.models import Restaurant
from restaurants.tests.factories import UserFactory


@pytest.mark.django_db
class TestRestaurantPaymentModel:
    def test_default_payment_model_is_upfront(self):
        owner = UserFactory()
        restaurant = Restaurant.objects.create(name="Test", slug="test", owner=owner)
        assert restaurant.payment_model == "upfront"

    def test_can_set_payment_model_to_tab(self):
        owner = UserFactory()
        restaurant = Restaurant.objects.create(
            name="Tab Test", slug="tab-test", owner=owner, payment_model="tab"
        )
        assert restaurant.payment_model == "tab"

    def test_payment_model_choices_are_valid(self):
        owner = UserFactory()
        restaurant = Restaurant.objects.create(name="Test", slug="test-valid", owner=owner)
        restaurant.payment_model = "upfront"
        restaurant.full_clean()
        restaurant.payment_model = "tab"
        restaurant.full_clean()
