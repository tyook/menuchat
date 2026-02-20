import pytest
from django.utils import timezone
from datetime import timedelta
from restaurants.tests.factories import UserFactory, RestaurantFactory


@pytest.mark.django_db
class TestSubscriptionModel:
    def test_create_subscription_for_restaurant(self):
        restaurant = RestaurantFactory()
        from restaurants.models import Subscription
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() + timedelta(days=14),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
            order_count=0,
        )
        assert sub.plan == "starter"
        assert sub.status == "trialing"
        assert sub.order_count == 0
        assert sub.is_active is True

    def test_subscription_is_active_for_active_status(self):
        restaurant = RestaurantFactory()
        from restaurants.models import Subscription
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=100,
        )
        assert sub.is_active is True

    def test_subscription_inactive_for_canceled(self):
        restaurant = RestaurantFactory()
        from restaurants.models import Subscription
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
            order_count=100,
        )
        assert sub.is_active is False

    def test_subscription_order_limit_from_settings(self):
        restaurant = RestaurantFactory()
        from restaurants.models import Subscription
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=0,
        )
        assert sub.order_limit == 200

    def test_user_stripe_customer_id(self):
        user = UserFactory()
        assert user.stripe_customer_id is None


@pytest.mark.django_db
class TestAutoTrialSubscription:
    def test_creating_restaurant_auto_creates_trial_subscription(self, api_client):
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/",
            {"name": "Trial Place", "slug": "trial-place"},
            format="json",
        )
        assert response.status_code == 201
        from restaurants.models import Restaurant, Subscription
        restaurant = Restaurant.objects.get(slug="trial-place")
        sub = Subscription.objects.get(restaurant=restaurant)
        assert sub.status == "trialing"
        assert sub.plan == "starter"
        assert sub.order_count == 0
        assert sub.trial_end is not None
