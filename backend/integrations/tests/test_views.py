import pytest
from rest_framework import status

from integrations.models import POSConnection
from integrations.tests.factories import POSConnectionFactory
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.fixture
def owner_setup(api_client):
    """Shared fixture for tests needing an authenticated restaurant owner."""
    user = UserFactory()
    restaurant = RestaurantFactory(owner=user, slug="test-resto")
    api_client.force_authenticate(user=user)
    return {"user": user, "restaurant": restaurant, "client": api_client}


@pytest.mark.django_db
class TestPOSConnectionAPI:

    def test_get_connection_when_none_exists(self, owner_setup):
        response = owner_setup["client"].get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "none"
        assert response.data["is_connected"] is False

    def test_get_existing_connection(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert response.data["is_connected"] is True

    def test_update_payment_mode(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].patch(
            "/api/restaurants/test-resto/pos/connection/",
            {"payment_mode": "pos_collected"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "pos_collected"

    def test_delete_connection(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].delete(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not POSConnection.objects.filter(
            restaurant=owner_setup["restaurant"]
        ).exists()

    def test_unauthenticated_access_denied(self, api_client):
        RestaurantFactory(slug="test-resto")
        response = api_client.get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPOSVendorSelectAPI:

    def test_select_square_creates_connection(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert response.data["is_connected"] is False
        conn = POSConnection.objects.get(restaurant=owner_setup["restaurant"])
        assert conn.pos_type == "square"
        assert conn.is_active is False

    def test_select_none_creates_connection(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "none"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "none"

    def test_select_vendor_updates_existing(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="none",
            is_active=False,
            oauth_access_token="",
            oauth_refresh_token="",
        )
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert POSConnection.objects.filter(
            restaurant=owner_setup["restaurant"]
        ).count() == 1

    def test_select_invalid_vendor_rejected(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "toast"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_select_vendor_unauthenticated(self, api_client):
        RestaurantFactory(slug="test-resto")
        response = api_client.post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_select_vendor_wrong_owner(self, api_client):
        other_user = UserFactory()
        RestaurantFactory(owner=other_user, slug="not-mine")
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/not-mine/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_select_vendor_missing_pos_type(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_select_vendor_on_already_connected_disconnects(self, owner_setup):
        """Selecting a new vendor on an active connection sets is_active=False."""
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
            is_active=True,
            oauth_access_token="",
            oauth_refresh_token="",
        )
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        conn = POSConnection.objects.get(restaurant=owner_setup["restaurant"])
        assert conn.is_active is False
        assert response.data["is_connected"] is False
