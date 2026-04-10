from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from notifications.models import DeviceToken


class DeviceRegisterViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_register_device_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/devices/register/", {
            "token": "fcm-token-abc",
            "platform": "ios",
        })
        assert response.status_code == 201
        token = DeviceToken.objects.get(token="fcm-token-abc")
        assert token.user == self.user
        assert token.platform == "ios"
        assert token.is_active is True

    def test_register_device_unauthenticated_with_order(self):
        from orders.models import Order
        from restaurants.models import Restaurant

        restaurant = Restaurant.objects.create(
            name="Test", slug="test", owner=self.user
        )
        order = Order.objects.create(restaurant=restaurant)
        response = self.client.post("/api/devices/register/", {
            "token": "fcm-token-def",
            "platform": "android",
            "order_id": str(order.id),
        })
        assert response.status_code == 201
        token = DeviceToken.objects.get(token="fcm-token-def")
        assert token.order == order

    def test_register_device_updates_existing(self):
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/devices/register/", {
            "token": "fcm-token-abc",
            "platform": "ios",
        })
        response = self.client.post("/api/devices/register/", {
            "token": "fcm-token-abc",
            "platform": "ios",
        })
        assert response.status_code == 200
        assert DeviceToken.objects.filter(token="fcm-token-abc").count() == 1

    def test_register_device_reactivates_inactive(self):
        self.client.force_authenticate(user=self.user)
        dt = DeviceToken.objects.create(
            user=self.user, token="old-token", platform="ios", is_active=False
        )
        response = self.client.post("/api/devices/register/", {
            "token": "old-token",
            "platform": "ios",
        })
        assert response.status_code == 200
        dt.refresh_from_db()
        assert dt.is_active is True
