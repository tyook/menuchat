import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status

from integrations.models import POSConnection
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestSquareOAuth:
    @pytest.fixture
    def owner_setup(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="oauth-test")
        api_client.force_authenticate(user=user)
        return {"user": user, "restaurant": restaurant, "client": api_client}

    @patch("integrations.views.django_settings")
    def test_initiate_square_connect(self, mock_settings, owner_setup):
        mock_settings.POS_SQUARE_CLIENT_ID = "sq_client_123"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        response = owner_setup["client"].post(
            "/api/restaurants/oauth-test/pos/connect/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "auth_url" in response.data
        assert "square" in response.data["auth_url"].lower()

    @patch("integrations.views.SquareClient")
    def test_square_oauth_callback_success(self, mock_square_class, api_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {
            "access_token": "sq_access_123",
            "refresh_token": "sq_refresh_456",
            "expires_at": "2026-04-27T00:00:00Z",
        }
        mock_client.o_auth.obtain_token.return_value = mock_result
        mock_square_class.return_value = mock_client

        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="oauth-cb-test")

        # Simulate the callback with HMAC-signed state
        from integrations.views import _sign_oauth_state
        signed_state = _sign_oauth_state(f"{restaurant.slug}:{user.id}")
        response = api_client.get(
            "/api/integrations/oauth/square/callback/",
            {"code": "auth_code_123", "state": signed_state},
        )
        assert response.status_code == status.HTTP_302_FOUND

        connection = POSConnection.objects.get(restaurant=restaurant)
        assert connection.pos_type == "square"
        assert connection.is_active is True
