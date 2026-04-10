import pytest
from django.test import TestCase
from django.db import IntegrityError
from accounts.models import User
from notifications.models import DeviceToken


class DeviceTokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_create_device_token_with_user(self):
        token = DeviceToken.objects.create(
            user=self.user,
            token="fcm-token-123",
            platform="ios",
        )
        assert token.is_active is True
        assert token.user == self.user
        assert token.order is None

    def test_create_device_token_with_order(self):
        from orders.models import Order
        from restaurants.models import Restaurant

        restaurant = Restaurant.objects.create(
            name="Test", slug="test", owner=self.user
        )
        order = Order.objects.create(restaurant=restaurant)
        token = DeviceToken.objects.create(
            order=order,
            token="fcm-token-456",
            platform="android",
        )
        assert token.order == order
        assert token.user is None

    def test_token_unique(self):
        DeviceToken.objects.create(
            user=self.user, token="same-token", platform="ios"
        )
        with pytest.raises(IntegrityError):
            DeviceToken.objects.create(
                user=self.user, token="same-token", platform="android"
            )
