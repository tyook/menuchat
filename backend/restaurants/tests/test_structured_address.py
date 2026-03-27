import pytest
from decimal import Decimal

from rest_framework import status

from restaurants.models import Restaurant
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestStructuredAddressModel:
    """Task 4: Structured address fields on the Restaurant model."""

    def test_new_fields_exist_with_defaults(self):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        assert restaurant.street_address == ""
        assert restaurant.city == ""
        assert restaurant.state == ""
        assert restaurant.zip_code == ""
        assert restaurant.country == "US"
        assert restaurant.google_place_id == ""
        assert restaurant.latitude is None
        assert restaurant.longitude is None

    def test_can_set_structured_address_fields(self):
        user = UserFactory()
        restaurant = RestaurantFactory(
            owner=user,
            street_address="123 Main St",
            city="Springfield",
            state="IL",
            zip_code="62701",
            country="US",
            google_place_id="ChIJd8BlQ2BZwokRAFUEcm_qrcA",
            latitude=Decimal("39.781721"),
            longitude=Decimal("-89.650148"),
        )
        restaurant.refresh_from_db()
        assert restaurant.street_address == "123 Main St"
        assert restaurant.city == "Springfield"
        assert restaurant.state == "IL"
        assert restaurant.zip_code == "62701"
        assert restaurant.country == "US"
        assert restaurant.google_place_id == "ChIJd8BlQ2BZwokRAFUEcm_qrcA"
        assert restaurant.latitude == Decimal("39.781721")
        assert restaurant.longitude == Decimal("-89.650148")

    def test_lat_lng_nullable(self):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        assert restaurant.latitude is None
        assert restaurant.longitude is None

    def test_country_defaults_to_us(self):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        assert restaurant.country == "US"

    def test_old_address_field_removed(self):
        """The old 'address' TextField should no longer exist."""
        field_names = [f.name for f in Restaurant._meta.get_fields()]
        assert "address" not in field_names


@pytest.mark.django_db
class TestStructuredAddressAPI:
    """Task 5: Serializer returns structured address fields via API."""

    def test_create_restaurant_with_structured_address(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {
                "name": "Test Place",
                "slug": "test-place",
                "street_address": "456 Oak Ave",
                "city": "Portland",
                "state": "OR",
                "zip_code": "97201",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["street_address"] == "456 Oak Ave"
        assert response.data["city"] == "Portland"
        assert response.data["state"] == "OR"
        assert response.data["zip_code"] == "97201"
        assert response.data["country"] == "US"

    def test_create_restaurant_without_address_uses_defaults(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "Minimal Place", "slug": "minimal-place"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["street_address"] == ""
        assert response.data["city"] == ""
        assert response.data["state"] == ""
        assert response.data["zip_code"] == ""
        assert response.data["country"] == "US"

    def test_get_restaurant_includes_structured_fields(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(
            owner=user,
            street_address="789 Elm St",
            city="Austin",
            state="TX",
            zip_code="73301",
        )
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["street_address"] == "789 Elm St"
        assert response.data["city"] == "Austin"
        assert response.data["state"] == "TX"
        assert response.data["zip_code"] == "73301"
        assert response.data["country"] == "US"
        assert response.data["latitude"] is None
        assert response.data["longitude"] is None
        assert response.data["google_place_id"] == ""

    def test_address_field_not_in_response(self, api_client):
        """The old 'address' field should not appear in API responses."""
        user = UserFactory()
        RestaurantFactory(owner=user)
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/restaurants/me/")
        assert response.status_code == status.HTTP_200_OK
        first = response.data["results"][0]
        assert "address" not in first
        assert "street_address" in first
