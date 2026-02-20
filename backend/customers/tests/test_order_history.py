import pytest

from customers.authentication import CustomerRefreshToken
from customers.tests.factories import CustomerFactory
from orders.tests.factories import OrderFactory

pytestmark = pytest.mark.django_db


class TestCustomerOrderHistory:
    def test_list_own_orders(self, api_client):
        customer = CustomerFactory()
        OrderFactory(customer=customer, customer_name=customer.name)
        OrderFactory(customer=customer, customer_name=customer.name)
        OrderFactory()  # Another customer's order

        refresh = CustomerRefreshToken.for_customer(customer)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = api_client.get("/api/customer/orders/")
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/customer/orders/")
        assert resp.status_code == 401

    def test_owner_token_rejected(self, api_client):
        from rest_framework_simplejwt.tokens import RefreshToken

        from restaurants.tests.factories import UserFactory

        user = UserFactory()
        token = str(RefreshToken.for_user(user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.get("/api/customer/orders/")
        assert resp.status_code == 401
