import pytest
from rest_framework.test import APIClient
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestCustomerRegister:
    def test_register_success(self, api_client):
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "new@example.com",
            "password": "securepass123",
            "name": "New Customer",
        }, format="json")
        assert resp.status_code == 201
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["customer"]["email"] == "new@example.com"

    def test_register_duplicate_email(self, api_client):
        CustomerFactory(email="taken@example.com")
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "taken@example.com",
            "password": "securepass123",
            "name": "Another",
        }, format="json")
        assert resp.status_code == 400

    def test_register_short_password(self, api_client):
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "new@example.com",
            "password": "short",
            "name": "New Customer",
        }, format="json")
        assert resp.status_code == 400


class TestCustomerLogin:
    def test_login_success(self, api_client):
        CustomerFactory(email="alice@example.com")
        resp = api_client.post("/api/customer/auth/login/", {
            "email": "alice@example.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_wrong_password(self, api_client):
        CustomerFactory(email="alice@example.com")
        resp = api_client.post("/api/customer/auth/login/", {
            "email": "alice@example.com",
            "password": "wrongpass",
        }, format="json")
        assert resp.status_code == 400

    def test_login_nonexistent(self, api_client):
        resp = api_client.post("/api/customer/auth/login/", {
            "email": "nobody@example.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 400


class TestCustomerTokenRefresh:
    def test_refresh_success(self, api_client):
        CustomerFactory(email="alice@example.com")
        login_resp = api_client.post("/api/customer/auth/login/", {
            "email": "alice@example.com",
            "password": "testpass123",
        }, format="json")
        refresh_token = login_resp.data["refresh"]
        resp = api_client.post("/api/customer/auth/refresh/", {
            "refresh": refresh_token,
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data

    def test_refresh_invalid_token(self, api_client):
        resp = api_client.post("/api/customer/auth/refresh/", {
            "refresh": "invalid-token",
        }, format="json")
        assert resp.status_code == 401

    def test_owner_token_rejected(self, api_client):
        """Owner refresh tokens should not work on customer refresh endpoint."""
        from restaurants.tests.factories import UserFactory
        from rest_framework_simplejwt.tokens import RefreshToken
        user = UserFactory()
        owner_refresh = str(RefreshToken.for_user(user))
        resp = api_client.post("/api/customer/auth/refresh/", {
            "refresh": owner_refresh,
        }, format="json")
        assert resp.status_code == 401


class TestCustomerProfile:
    def test_get_profile_success(self, api_client):
        customer = CustomerFactory(email="alice@example.com", name="Alice", phone="555-1234")
        from customers.authentication import CustomerRefreshToken
        refresh = CustomerRefreshToken.for_customer(customer)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = api_client.get("/api/customer/profile/")
        assert resp.status_code == 200
        assert resp.data["email"] == "alice@example.com"
        assert resp.data["name"] == "Alice"
        assert resp.data["phone"] == "555-1234"

    def test_get_profile_unauthenticated(self, api_client):
        resp = api_client.get("/api/customer/profile/")
        assert resp.status_code == 401

    def test_patch_profile_success(self, api_client):
        customer = CustomerFactory(email="alice@example.com", name="Alice")
        from customers.authentication import CustomerRefreshToken
        refresh = CustomerRefreshToken.for_customer(customer)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = api_client.patch("/api/customer/profile/", {
            "name": "Alice Updated",
            "phone": "555-9999",
            "dietary_preferences": ["vegetarian"],
            "allergies": ["peanuts"],
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["name"] == "Alice Updated"
        assert resp.data["phone"] == "555-9999"
        assert resp.data["dietary_preferences"] == ["vegetarian"]
        assert resp.data["allergies"] == ["peanuts"]

    def test_patch_profile_unauthenticated(self, api_client):
        resp = api_client.patch("/api/customer/profile/", {
            "name": "Updated",
        }, format="json")
        assert resp.status_code == 401

    def test_owner_token_rejected_on_profile(self, api_client):
        """Owner access tokens should not work on customer profile endpoint."""
        from restaurants.tests.factories import UserFactory
        from rest_framework_simplejwt.tokens import RefreshToken
        user = UserFactory()
        owner_token = str(RefreshToken.for_user(user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token}")
        resp = api_client.get("/api/customer/profile/")
        assert resp.status_code == 401
