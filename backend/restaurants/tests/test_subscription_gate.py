from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from orders.llm.base import AgentResponse, ParsedOrder
from orders.services import OrderService
from restaurants.models import Subscription
from restaurants.tests.factories import MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory, MenuVersionFactory, RestaurantFactory


def _setup_restaurant_with_menu():
    """Create a restaurant with a menu item for parsing."""
    restaurant = RestaurantFactory()
    version = MenuVersionFactory(restaurant=restaurant, is_active=True)
    category = MenuCategoryFactory(version=version)
    item = MenuItemFactory(category=category, name="Pizza")
    MenuItemVariantFactory(menu_item=item, label="Large", price=15.00)
    return restaurant


@pytest.mark.django_db
class TestSubscriptionGate:
    @patch("orders.services.OrderService.validate_and_price_order")
    @patch("orders.services.OrderAgent.run")
    def test_parse_order_increments_order_count(self, mock_agent, mock_validate, api_client):
        mock_agent.return_value = AgentResponse(intent="order", order=ParsedOrder(items=[]))
        mock_validate.return_value = {"items": [], "language": "en"}
        restaurant = _setup_restaurant_with_menu()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=5,
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.order_count == 6

    def test_parse_order_blocked_when_subscription_canceled(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
            order_count=0,
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription" in response.data["detail"].lower()

    def test_parse_order_blocked_when_trial_expired(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() - timedelta(days=1),
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() - timedelta(days=1),
            order_count=0,
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("orders.services.OrderService.validate_and_price_order")
    @patch("orders.services.OrderAgent.run")
    def test_parse_order_allowed_when_over_limit_soft_cap(self, mock_agent, mock_validate, api_client):
        """Soft cap: orders continue even when over limit."""
        mock_agent.return_value = AgentResponse(intent="order", order=ParsedOrder(items=[]))
        mock_validate.return_value = {"items": [], "language": "en"}
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=250,  # Over the 200 limit
        )
        response = api_client.post(
            f"/api/order/{restaurant.slug}/parse/",
            {"raw_input": "one large pizza"},
            format="json",
        )
        # Soft cap: should still work
        assert response.status_code == status.HTTP_200_OK

    def test_parse_order_allowed_when_no_subscription_exists(self, api_client):
        """Restaurants without a subscription (legacy) should not be blocked."""
        restaurant = _setup_restaurant_with_menu()
        # No Subscription object created
        with (
            patch("orders.services.OrderAgent.run") as mock_agent,
            patch("orders.services.OrderService.validate_and_price_order") as mock_validate,
        ):
            mock_agent.return_value = AgentResponse(intent="order", order=ParsedOrder(items=[]))
            mock_validate.return_value = {"items": [], "language": "en"}
            response = api_client.post(
                f"/api/order/{restaurant.slug}/parse/",
                {"raw_input": "one large pizza"},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestIsSubscriptionActive:
    def test_active_subscription_returns_true(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        assert OrderService.is_subscription_active(restaurant) is True

    def test_canceled_subscription_returns_false(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        assert OrderService.is_subscription_active(restaurant) is False

    def test_expired_trial_returns_false(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() - timedelta(days=1),
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        assert OrderService.is_subscription_active(restaurant) is False

    def test_active_trial_returns_true(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() + timedelta(days=7),
            current_period_start=timezone.now() - timedelta(days=7),
            current_period_end=timezone.now() + timedelta(days=7),
        )
        assert OrderService.is_subscription_active(restaurant) is True

    def test_no_subscription_returns_true(self):
        restaurant = RestaurantFactory()
        assert OrderService.is_subscription_active(restaurant) is True

    def test_past_due_returns_true(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="past_due",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        assert OrderService.is_subscription_active(restaurant) is True


@pytest.mark.django_db
class TestPublicMenuSubscriptionGate:
    def test_menu_returns_available_true_when_active(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is True
        assert "categories" in response.data

    def test_menu_returns_available_false_when_canceled(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is False
        assert response.data["restaurant_name"] == restaurant.name
        assert "categories" not in response.data

    def test_menu_returns_available_false_when_trial_expired(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() - timedelta(days=1),
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is False

    def test_menu_returns_available_true_when_no_subscription(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is True
        assert "categories" in response.data
