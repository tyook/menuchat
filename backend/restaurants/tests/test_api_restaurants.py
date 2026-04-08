import pytest
from rest_framework import status

from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestCreateRestaurant:
    def test_create_restaurant(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "My Pizza Place"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "My Pizza Place"
        assert response.data["slug"] == "my-pizza-place"

    def test_create_restaurant_auto_increments_duplicate_slug(self, api_client):
        RestaurantFactory(slug="taken", name="Taken")
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "Taken"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "taken-2"

    def test_create_restaurant_ignores_slug_in_payload(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "My Place", "slug": "custom-slug"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "my-place"


@pytest.mark.django_db
class TestMyRestaurants:
    def test_list_own_restaurants(self, api_client):
        user = UserFactory()
        RestaurantFactory(owner=user)
        RestaurantFactory(owner=user)
        RestaurantFactory()  # Someone else's
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/restaurants/me/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2


@pytest.mark.django_db
class TestUpdateRestaurant:
    def test_owner_can_update_name_and_slug_follows(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, name="Old Name", slug="old-name")
        api_client.force_authenticate(user=user)
        response = api_client.patch(
            f"/api/restaurants/{restaurant.slug}/",
            {"name": "New Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"
        assert response.data["slug"] == "new-name"


@pytest.mark.django_db
class TestRestaurantSubscriptionInResponse:
    def test_restaurant_detail_includes_subscription(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        from datetime import timedelta

        from django.utils import timezone

        from restaurants.models import Subscription

        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=42,
        )
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/")
        assert response.status_code == 200
        assert "subscription" in response.data
        assert response.data["subscription"]["plan"] == "growth"
        assert response.data["subscription"]["order_count"] == 42
