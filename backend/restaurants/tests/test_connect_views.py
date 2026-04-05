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


@pytest.mark.django_db
class TestConnectServiceCustomURLs:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_custom_return_url_passed_to_stripe(self, mock_link, mock_create, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        from restaurants.services.connect_service import ConnectService
        result = ConnectService.create_onboarding_link(
            restaurant,
            return_url="http://localhost:3000/account/onboarding?stripe_return=true",
            refresh_url="http://localhost:3000/account/onboarding?stripe_refresh=true",
        )

        assert result["url"] == "https://connect.stripe.com/setup/abc"
        call_kwargs = mock_link.call_args[1]
        assert "stripe_return=true" in call_kwargs["return_url"]
        assert "stripe_refresh=true" in call_kwargs["refresh_url"]

    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_default_urls_when_none_provided(self, mock_link, mock_create, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        from restaurants.services.connect_service import ConnectService
        ConnectService.create_onboarding_link(restaurant)

        call_kwargs = mock_link.call_args[1]
        assert "/dashboard/" in call_kwargs["return_url"]
        assert "/dashboard/" in call_kwargs["refresh_url"]


@pytest.mark.django_db
class TestOnboardingConnectInitiateView:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_initiate_with_valid_urls(self, mock_link, mock_create, api_client, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 200
        assert "url" in response.data

    def test_initiate_rejects_invalid_return_url(self, api_client, restaurant):
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "https://evil.com/steal",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_initiate_rejects_invalid_refresh_url(self, api_client, restaurant):
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "https://evil.com/steal",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_initiate_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 401

    def test_initiate_wrong_owner(self, restaurant):
        other_user = User.objects.create_user(email="other@test.com", password="testpass123")
        client = APIClient()
        client.force_authenticate(user=other_user)
        response = client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestOnboardingConnectStatusView:
    def test_status_no_account(self, api_client, restaurant):
        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 200
        assert response.data["has_account"] is False
        assert response.data["onboarding_complete"] is False

    def test_status_with_complete_account(self, api_client, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
            payouts_enabled=True,
        )
        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 200
        assert response.data["onboarding_complete"] is True

    def test_status_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 401

    def test_status_wrong_owner(self, restaurant):
        other_user = User.objects.create_user(email="other@test.com", password="testpass123")
        client = APIClient()
        client.force_authenticate(user=other_user)
        response = client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 404
