import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from restaurants.models import Restaurant, ConnectedAccount

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-rest", owner=owner)


@pytest.fixture
def api_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.mark.django_db
class TestConnectOnboardView:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_create_onboarding_link(self, mock_link, mock_create, api_client, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        response = api_client.post(f"/api/restaurants/{restaurant.slug}/connect/onboard/")

        assert response.status_code == 200
        assert "url" in response.data

    def test_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.post(f"/api/restaurants/{restaurant.slug}/connect/onboard/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestConnectStatusView:
    def test_status_no_account(self, api_client, restaurant):
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/connect/status/")
        assert response.status_code == 200
        assert response.data["has_account"] is False


@pytest.mark.django_db
class TestConnectDashboardView:
    @patch("restaurants.services.connect_service.stripe.Account.create_login_link")
    def test_dashboard_link(self, mock_login, api_client, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
        )
        mock_login.return_value = MagicMock(url="https://connect.stripe.com/express/abc")

        response = api_client.post(f"/api/restaurants/{restaurant.slug}/connect/dashboard/")
        assert response.status_code == 200
        assert "url" in response.data
