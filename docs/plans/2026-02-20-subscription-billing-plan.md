# Subscription Billing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Stripe-based subscription billing for restaurant owners with tiered plans (Starter/Growth/Pro), free trial, order usage tracking, and a billing management UI.

**Architecture:** Restaurant owners subscribe via Stripe Checkout. Stripe manages recurring billing, trials, and payment collection. Our backend tracks subscription status and order usage per billing period. A middleware gate checks subscription status before allowing AI order parsing. The frontend adds a billing page to the admin dashboard.

**Tech Stack:** Django REST Framework, Stripe Subscriptions API (Checkout Sessions, Customer Portal, Webhooks), Next.js + shadcn/ui, React Query hooks.

---

## Prerequisites

Before starting, create three Stripe Products + Prices in the Stripe Dashboard (or via API):
- **Starter**: $49/mo (price ID → `STRIPE_PRICE_STARTER_MONTHLY`)
- **Growth**: $99/mo (price ID → `STRIPE_PRICE_GROWTH_MONTHLY`)
- **Pro**: $199/mo (price ID → `STRIPE_PRICE_PRO_MONTHLY`)
- Annual variants: $480/yr, $984/yr, $1992/yr

Add to `.env`:
```
STRIPE_PRICE_STARTER_MONTHLY=price_xxx
STRIPE_PRICE_GROWTH_MONTHLY=price_xxx
STRIPE_PRICE_PRO_MONTHLY=price_xxx
STRIPE_PRICE_STARTER_ANNUAL=price_xxx
STRIPE_PRICE_GROWTH_ANNUAL=price_xxx
STRIPE_PRICE_PRO_ANNUAL=price_xxx
```

---

### Task 1: Add Subscription Settings to Django Config

**Files:**
- Modify: `backend/config/settings.py`

**Step 1: Add Stripe subscription price settings**

Add after the existing Stripe settings block (after line 128 in `backend/config/settings.py`):

```python
# ---------------------------------------------------------------------------
# Stripe Subscription Plans
# ---------------------------------------------------------------------------
STRIPE_PRICE_STARTER_MONTHLY = config("STRIPE_PRICE_STARTER_MONTHLY", default="")
STRIPE_PRICE_GROWTH_MONTHLY = config("STRIPE_PRICE_GROWTH_MONTHLY", default="")
STRIPE_PRICE_PRO_MONTHLY = config("STRIPE_PRICE_PRO_MONTHLY", default="")
STRIPE_PRICE_STARTER_ANNUAL = config("STRIPE_PRICE_STARTER_ANNUAL", default="")
STRIPE_PRICE_GROWTH_ANNUAL = config("STRIPE_PRICE_GROWTH_ANNUAL", default="")
STRIPE_PRICE_PRO_ANNUAL = config("STRIPE_PRICE_PRO_ANNUAL", default="")

SUBSCRIPTION_PLANS = {
    "starter": {
        "name": "Starter",
        "order_limit": 200,
        "overage_rate_cents": 20,  # $0.20
        "monthly_price_id": STRIPE_PRICE_STARTER_MONTHLY,
        "annual_price_id": STRIPE_PRICE_STARTER_ANNUAL,
    },
    "growth": {
        "name": "Growth",
        "order_limit": 600,
        "overage_rate_cents": 15,  # $0.15
        "monthly_price_id": STRIPE_PRICE_GROWTH_MONTHLY,
        "annual_price_id": STRIPE_PRICE_GROWTH_ANNUAL,
    },
    "pro": {
        "name": "Pro",
        "order_limit": 1500,
        "overage_rate_cents": 10,  # $0.10
        "monthly_price_id": STRIPE_PRICE_PRO_MONTHLY,
        "annual_price_id": STRIPE_PRICE_PRO_ANNUAL,
    },
}

# Free trial settings
FREE_TRIAL_DAYS = 14
FREE_TRIAL_ORDER_LIMIT = 200

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")
```

**Step 2: Commit**

```bash
git add backend/config/settings.py
git commit -m "feat: add subscription plan settings and Stripe price IDs"
```

---

### Task 2: Create Subscription Model

**Files:**
- Modify: `backend/restaurants/models.py` (add Subscription model after Restaurant, add `stripe_customer_id` to User)
- Create: `backend/restaurants/migrations/` (auto-generated)

**Step 1: Write the failing test**

Create `backend/restaurants/tests/test_subscription_model.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_model.py -v
```

Expected: FAIL — `Subscription` model does not exist.

**Step 3: Write the Subscription model**

Add to `backend/restaurants/models.py` after the `Restaurant` class (after line 45):

```python
class Subscription(models.Model):
    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        PRO = "pro", "Pro"

    class Status(models.TextChoices):
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        INCOMPLETE = "incomplete", "Incomplete"

    restaurant = models.OneToOneField(
        Restaurant, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.STARTER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIALING)
    stripe_subscription_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    stripe_customer_id = models.CharField(
        max_length=255, blank=True, null=True,
    )
    trial_end = models.DateTimeField(blank=True, null=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    order_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self):
        """Subscription allows usage if trialing, active, or past_due."""
        return self.status in ("trialing", "active", "past_due")

    @property
    def order_limit(self):
        """Get order limit from settings based on plan."""
        from django.conf import settings
        plan_config = settings.SUBSCRIPTION_PLANS.get(self.plan, {})
        return plan_config.get("order_limit", 0)

    @property
    def overage_count(self):
        """Number of orders exceeding the plan limit."""
        return max(0, self.order_count - self.order_limit)

    def __str__(self):
        return f"{self.restaurant.name} - {self.plan} ({self.status})"
```

Also add `stripe_customer_id` to the `User` model (after `phone` field, line 16):

```python
stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
```

**Step 4: Make and run migrations**

```bash
cd backend && python manage.py makemigrations restaurants
cd backend && python manage.py migrate
```

**Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_model.py -v
```

Expected: All PASS.

**Step 6: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/ backend/restaurants/tests/test_subscription_model.py
git commit -m "feat: add Subscription model and User.stripe_customer_id"
```

---

### Task 3: Auto-Create Trial Subscription on Restaurant Creation

**Files:**
- Modify: `backend/restaurants/serializers.py` (update `RestaurantSerializer.create`)
- Test: `backend/restaurants/tests/test_subscription_model.py`

**Step 1: Write the failing test**

Add to `backend/restaurants/tests/test_subscription_model.py`:

```python
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
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_model.py::TestAutoTrialSubscription -v
```

Expected: FAIL — no Subscription created.

**Step 3: Update RestaurantSerializer.create**

In `backend/restaurants/serializers.py`, update the `create` method of `RestaurantSerializer` (currently lines 53-62):

```python
def create(self, validated_data):
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings

    validated_data["owner"] = self.context["request"].user
    restaurant = Restaurant.objects.create(**validated_data)
    # Auto-create owner staff record
    RestaurantStaff.objects.create(
        user=self.context["request"].user,
        restaurant=restaurant,
        role="owner",
    )
    # Auto-create trial subscription
    from restaurants.models import Subscription
    trial_end = timezone.now() + timedelta(days=settings.FREE_TRIAL_DAYS)
    Subscription.objects.create(
        restaurant=restaurant,
        plan="starter",
        status="trialing",
        trial_end=trial_end,
        current_period_start=timezone.now(),
        current_period_end=trial_end,
        order_count=0,
    )
    return restaurant
```

**Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_model.py -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/restaurants/serializers.py backend/restaurants/tests/test_subscription_model.py
git commit -m "feat: auto-create trial subscription on restaurant creation"
```

---

### Task 4: Subscription Serializer and API Endpoints

**Files:**
- Modify: `backend/restaurants/serializers.py` (add SubscriptionSerializer)
- Modify: `backend/restaurants/views.py` (add SubscriptionDetailView, CreateCheckoutSessionView, CreateBillingPortalView, CancelSubscriptionView)
- Modify: `backend/restaurants/urls.py` (add new routes)
- Test: `backend/restaurants/tests/test_subscription_api.py`

**Step 1: Write the failing tests**

Create `backend/restaurants/tests/test_subscription_api.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status
from restaurants.tests.factories import UserFactory, RestaurantFactory
from restaurants.models import Subscription
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestSubscriptionDetail:
    def test_owner_can_view_subscription(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() + timedelta(days=14),
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/subscription/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == "starter"
        assert response.data["status"] == "trialing"
        assert "order_count" in response.data
        assert "order_limit" in response.data
        assert "is_active" in response.data

    def test_unauthenticated_cannot_view(self, api_client):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/subscription/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_owner_cannot_view(self, api_client):
        other_user = UserFactory()
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/subscription/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCreateCheckoutSession:
    @patch("stripe.checkout.Session.create")
    @patch("stripe.Customer.create")
    def test_create_checkout_session(self, mock_stripe_customer, mock_checkout, api_client):
        mock_stripe_customer.return_value = MagicMock(id="cus_test123")
        mock_checkout.return_value = MagicMock(url="https://checkout.stripe.com/test")
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/checkout/",
            {"plan": "growth", "interval": "monthly"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "checkout_url" in response.data


@pytest.mark.django_db
class TestCreateBillingPortal:
    @patch("stripe.billing_portal.Session.create")
    def test_create_portal_session(self, mock_portal, api_client):
        mock_portal.return_value = MagicMock(url="https://billing.stripe.com/test")
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="active",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/portal/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "portal_url" in response.data


@pytest.mark.django_db
class TestCancelSubscription:
    @patch("stripe.Subscription.modify")
    def test_cancel_subscription_at_period_end(self, mock_modify, api_client):
        mock_modify.return_value = MagicMock(
            cancel_at_period_end=True,
            status="active",
        )
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="growth", status="active",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/cancel/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["cancel_at_period_end"] is True
        mock_modify.assert_called_once_with("sub_test123", cancel_at_period_end=True)

    def test_cancel_requires_active_subscription(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="starter", status="trialing",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
            # No stripe_subscription_id — trial without Stripe sub
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/cancel/",
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("stripe.Subscription.modify")
    def test_reactivate_subscription(self, mock_modify, api_client):
        mock_modify.return_value = MagicMock(
            cancel_at_period_end=False,
            status="active",
        )
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        Subscription.objects.create(
            restaurant=restaurant, plan="growth", status="active",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            cancel_at_period_end=True,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/subscription/reactivate/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["cancel_at_period_end"] is False
        mock_modify.assert_called_once_with("sub_test123", cancel_at_period_end=False)
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_api.py -v
```

Expected: FAIL — views and serializer don't exist.

**Step 3: Add SubscriptionSerializer**

Add to `backend/restaurants/serializers.py`:

```python
from restaurants.models import Restaurant, RestaurantStaff, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier, Subscription

class SubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    order_limit = serializers.IntegerField(read_only=True)
    overage_count = serializers.IntegerField(read_only=True)
    plan_name = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "plan", "plan_name", "status", "trial_end",
            "current_period_start", "current_period_end",
            "cancel_at_period_end", "order_count", "order_limit",
            "overage_count", "is_active",
        ]

    def get_plan_name(self, obj):
        from django.conf import settings
        plan_config = settings.SUBSCRIPTION_PLANS.get(obj.plan, {})
        return plan_config.get("name", obj.plan.title())
```

**Step 4: Add Subscription Views**

Add to `backend/restaurants/views.py`:

```python
import stripe
from django.conf import settings
from restaurants.serializers import SubscriptionSerializer
from restaurants.models import Subscription


class SubscriptionDetailView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/subscription/ - View subscription details."""

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SubscriptionSerializer(subscription).data)


class CreateCheckoutSessionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/checkout/ - Create Stripe Checkout session."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        plan = request.data.get("plan", "starter")
        interval = request.data.get("interval", "monthly")

        plan_config = settings.SUBSCRIPTION_PLANS.get(plan)
        if not plan_config:
            return Response(
                {"detail": "Invalid plan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price_key = "monthly_price_id" if interval == "monthly" else "annual_price_id"
        price_id = plan_config.get(price_key)
        if not price_id:
            return Response(
                {"detail": "Price not configured."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Get or create Stripe Customer for the restaurant owner
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email=request.user.email,
                name=f"{request.user.first_name} {request.user.last_name}".strip(),
                metadata={
                    "restaurant_id": str(restaurant.id),
                    "restaurant_slug": restaurant.slug,
                },
            )
            subscription.stripe_customer_id = customer.id
            subscription.save(update_fields=["stripe_customer_id"])

        checkout_session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.FRONTEND_URL}/admin/{restaurant.slug}/billing?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/admin/{restaurant.slug}/billing",
            metadata={
                "restaurant_id": str(restaurant.id),
                "plan": plan,
            },
            subscription_data={
                "metadata": {
                    "restaurant_id": str(restaurant.id),
                    "plan": plan,
                },
            },
        )

        return Response({"checkout_url": checkout_session.url})


class CreateBillingPortalView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/portal/ - Open Stripe Billing Portal."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_customer_id:
            return Response(
                {"detail": "No billing account found. Please subscribe first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/admin/{restaurant.slug}/billing",
        )

        return Response({"portal_url": portal_session.url})


class CancelSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/cancel/ - Cancel subscription at period end."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_subscription_id:
            return Response(
                {"detail": "No active paid subscription to cancel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )

        subscription.cancel_at_period_end = True
        subscription.save(update_fields=["cancel_at_period_end"])

        return Response(SubscriptionSerializer(subscription).data)


class ReactivateSubscriptionView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/subscription/reactivate/ - Undo pending cancellation."""

    def post(self, request, slug):
        restaurant = self.get_restaurant()

        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response(
                {"detail": "No subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_subscription_id:
            return Response(
                {"detail": "No active subscription to reactivate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY

        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["cancel_at_period_end"])

        return Response(SubscriptionSerializer(subscription).data)
```

**Step 5: Add URL routes**

Add to `backend/restaurants/urls.py` (add imports and paths):

```python
from restaurants.views import (
    RegisterView, LoginView,
    MyRestaurantsView, CreateRestaurantView, RestaurantDetailView,
    MenuCategoryListCreateView, MenuCategoryDetailView,
    MenuItemListCreateView, MenuItemDetailView,
    FullMenuView,
    SubscriptionDetailView, CreateCheckoutSessionView, CreateBillingPortalView,
    CancelSubscriptionView, ReactivateSubscriptionView,
)

# Add to urlpatterns:
    # Subscription
    path(
        "restaurants/<slug:slug>/subscription/",
        SubscriptionDetailView.as_view(),
        name="subscription-detail",
    ),
    path(
        "restaurants/<slug:slug>/subscription/checkout/",
        CreateCheckoutSessionView.as_view(),
        name="subscription-checkout",
    ),
    path(
        "restaurants/<slug:slug>/subscription/portal/",
        CreateBillingPortalView.as_view(),
        name="subscription-portal",
    ),
    path(
        "restaurants/<slug:slug>/subscription/cancel/",
        CancelSubscriptionView.as_view(),
        name="subscription-cancel",
    ),
    path(
        "restaurants/<slug:slug>/subscription/reactivate/",
        ReactivateSubscriptionView.as_view(),
        name="subscription-reactivate",
    ),
```

**Step 6: Run tests to verify they pass**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_api.py -v
```

Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/restaurants/serializers.py backend/restaurants/views.py backend/restaurants/urls.py backend/restaurants/tests/test_subscription_api.py
git commit -m "feat: add subscription API endpoints (detail, checkout, portal, cancel, reactivate)"
```

---

### Task 5: Subscription Webhook Handler

**Files:**
- Modify: `backend/orders/views.py` (extend StripeWebhookView to handle subscription events)
- Test: `backend/restaurants/tests/test_subscription_webhooks.py`

**Step 1: Write the failing tests**

Create `backend/restaurants/tests/test_subscription_webhooks.py`:

```python
import pytest
import json
from unittest.mock import patch, MagicMock
from rest_framework import status
from restaurants.tests.factories import RestaurantFactory
from restaurants.models import Subscription
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestSubscriptionWebhooks:
    @patch("stripe.Webhook.construct_event")
    def test_checkout_completed_activates_subscription(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )

        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "subscription": "sub_new123",
                    "customer": "cus_test123",
                    "metadata": {
                        "restaurant_id": str(restaurant.id),
                        "plan": "growth",
                    },
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.stripe_subscription_id == "sub_new123"
        assert sub.plan == "growth"
        assert sub.status == "active"

    @patch("stripe.Webhook.construct_event")
    def test_subscription_updated_changes_status(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_growth_monthly",
                                    "metadata": {},
                                }
                            }
                        ]
                    },
                    "metadata": {"plan": "growth"},
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.status == "past_due"

    @patch("stripe.Webhook.construct_event")
    def test_subscription_deleted_marks_canceled(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.status == "canceled"
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_webhooks.py -v
```

**Step 3: Extend StripeWebhookView**

In `backend/orders/views.py`, add subscription event handling inside the `StripeWebhookView.post` method. After the existing `payment_intent.payment_failed` handler (after line 471), add:

```python
        elif event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            if session.get("mode") == "subscription":
                from restaurants.models import Subscription
                restaurant_id = session.get("metadata", {}).get("restaurant_id")
                plan = session.get("metadata", {}).get("plan", "starter")
                if restaurant_id:
                    try:
                        sub = Subscription.objects.get(restaurant_id=restaurant_id)
                        sub.stripe_subscription_id = session["subscription"]
                        sub.stripe_customer_id = session.get("customer", sub.stripe_customer_id)
                        sub.plan = plan
                        sub.status = "active"
                        sub.order_count = 0  # Reset for new billing period
                        sub.save(update_fields=[
                            "stripe_subscription_id", "stripe_customer_id",
                            "plan", "status", "order_count",
                        ])
                    except Subscription.DoesNotExist:
                        pass

        elif event["type"] == "customer.subscription.updated":
            sub_data = event["data"]["object"]
            from restaurants.models import Subscription
            try:
                sub = Subscription.objects.get(
                    stripe_subscription_id=sub_data["id"]
                )
                sub.status = sub_data["status"]
                sub.cancel_at_period_end = sub_data.get("cancel_at_period_end", False)

                from datetime import datetime, timezone as tz
                if sub_data.get("current_period_start"):
                    sub.current_period_start = datetime.fromtimestamp(
                        sub_data["current_period_start"], tz=tz.utc
                    )
                if sub_data.get("current_period_end"):
                    sub.current_period_end = datetime.fromtimestamp(
                        sub_data["current_period_end"], tz=tz.utc
                    )

                # Update plan from metadata if present
                plan = sub_data.get("metadata", {}).get("plan")
                if plan and plan in ("starter", "growth", "pro"):
                    sub.plan = plan

                sub.save()
            except Subscription.DoesNotExist:
                pass

        elif event["type"] == "customer.subscription.deleted":
            sub_data = event["data"]["object"]
            from restaurants.models import Subscription
            try:
                sub = Subscription.objects.get(
                    stripe_subscription_id=sub_data["id"]
                )
                sub.status = "canceled"
                sub.save(update_fields=["status"])
            except Subscription.DoesNotExist:
                pass

        elif event["type"] == "invoice.paid":
            # Reset order count at start of new billing period
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")
            if subscription_id:
                from restaurants.models import Subscription
                try:
                    sub = Subscription.objects.get(
                        stripe_subscription_id=subscription_id
                    )
                    sub.order_count = 0
                    sub.save(update_fields=["order_count"])
                except Subscription.DoesNotExist:
                    pass
```

**Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_webhooks.py -v
```

Expected: All PASS.

**Step 5: Commit**

```bash
git add backend/orders/views.py backend/restaurants/tests/test_subscription_webhooks.py
git commit -m "feat: handle subscription webhook events (checkout, update, delete, invoice)"
```

---

### Task 6: Order Count Tracking and Subscription Gate

**Files:**
- Modify: `backend/orders/views.py` (increment order_count in ParseOrderView, add subscription check)
- Test: `backend/restaurants/tests/test_subscription_gate.py`

**Step 1: Write the failing tests**

Create `backend/restaurants/tests/test_subscription_gate.py`:

```python
import pytest
from unittest.mock import patch
from rest_framework import status
from restaurants.tests.factories import RestaurantFactory, MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory
from restaurants.models import Subscription
from django.utils import timezone
from datetime import timedelta


def _setup_restaurant_with_menu():
    """Create a restaurant with a menu item for parsing."""
    restaurant = RestaurantFactory()
    category = MenuCategoryFactory(restaurant=restaurant)
    item = MenuItemFactory(category=category, name="Pizza")
    MenuItemVariantFactory(menu_item=item, label="Large", price=15.00)
    return restaurant


@pytest.mark.django_db
class TestSubscriptionGate:
    @patch("orders.views.OrderParsingAgent.run")
    def test_parse_order_increments_order_count(self, mock_agent, api_client):
        mock_agent.return_value = {"items": [], "language": "en"}
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

    @patch("orders.views.OrderParsingAgent.run")
    def test_parse_order_allowed_when_over_limit_soft_cap(self, mock_agent, api_client):
        """Soft cap: orders continue even when over limit."""
        mock_agent.return_value = {"items": [], "language": "en"}
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
        """Restaurants without a subscription (legacy) should not be blocked.
        They just won't have usage tracking."""
        # NOTE: This test documents graceful handling for legacy restaurants.
        # In practice, all new restaurants get a trial subscription.
        # We allow access to avoid breaking existing restaurants.
        restaurant = _setup_restaurant_with_menu()
        # No Subscription object created
        with patch("orders.views.OrderParsingAgent.run") as mock_agent:
            mock_agent.return_value = {"items": [], "language": "en"}
            response = api_client.post(
                f"/api/order/{restaurant.slug}/parse/",
                {"raw_input": "one large pizza"},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK
```

**Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_gate.py -v
```

**Step 3: Update ParseOrderView to check subscription and increment count**

In `backend/orders/views.py`, update `ParseOrderView.post` (currently starting at line 49):

```python
class ParseOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return Response(
                {"detail": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check subscription status
        from restaurants.models import Subscription
        from django.utils import timezone
        try:
            subscription = restaurant.subscription
            # Block if canceled or incomplete
            if not subscription.is_active:
                return Response(
                    {"detail": "Subscription is not active. Please subscribe to continue."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Block if trial expired
            if (
                subscription.status == "trialing"
                and subscription.trial_end
                and subscription.trial_end < timezone.now()
            ):
                return Response(
                    {"detail": "Free trial has expired. Please subscribe to continue."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Subscription.DoesNotExist:
            subscription = None  # Legacy restaurant, allow access

        serializer = ParseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_input = serializer.validated_data["raw_input"]
        menu_context = build_menu_context(restaurant)
        parsed = OrderParsingAgent.run(
            raw_input=raw_input,
            menu_context=menu_context,
        )
        result = validate_and_price_order(restaurant, parsed)

        # Increment order count (soft cap — always increment, never block)
        if subscription:
            Subscription.objects.filter(id=subscription.id).update(
                order_count=models.F("order_count") + 1
            )

        return Response(result)
```

Also add `from django.db import models` to the imports at the top of `backend/orders/views.py` if not already present.

**Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest restaurants/tests/test_subscription_gate.py -v
```

Expected: All PASS.

**Step 5: Run full test suite to verify no regressions**

```bash
cd backend && python -m pytest -v
```

**Step 6: Commit**

```bash
git add backend/orders/views.py backend/restaurants/tests/test_subscription_gate.py
git commit -m "feat: add subscription gate to ParseOrderView with order count tracking"
```

---

### Task 7: Include Subscription in Restaurant API Response

**Files:**
- Modify: `backend/restaurants/serializers.py` (add subscription data to RestaurantSerializer)
- Modify: `backend/restaurants/tests/test_api_restaurants.py`

**Step 1: Write the failing test**

Add to `backend/restaurants/tests/test_api_restaurants.py`:

```python
@pytest.mark.django_db
class TestRestaurantSubscriptionInResponse:
    def test_restaurant_detail_includes_subscription(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user)
        from restaurants.models import Subscription
        from django.utils import timezone
        from datetime import timedelta
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
```

**Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest restaurants/tests/test_api_restaurants.py::TestRestaurantSubscriptionInResponse -v
```

**Step 3: Add subscription to RestaurantSerializer**

Update `RestaurantSerializer` in `backend/restaurants/serializers.py`:

```python
class RestaurantSerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer(read_only=True)

    class Meta:
        model = Restaurant
        fields = [
            "id", "name", "slug", "phone", "address", "homepage",
            "logo_url", "tax_rate", "created_at", "subscription",
        ]
        read_only_fields = ["id", "created_at", "subscription"]
```

**Step 4: Run tests**

```bash
cd backend && python -m pytest restaurants/tests/test_api_restaurants.py -v
```

**Step 5: Commit**

```bash
git add backend/restaurants/serializers.py backend/restaurants/tests/test_api_restaurants.py
git commit -m "feat: include subscription data in restaurant API response"
```

---

### Task 8: Frontend - TypeScript Types and API Functions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

**Step 1: Add subscription types**

Add to `frontend/src/types/index.ts`:

```typescript
// Subscription types
export interface Subscription {
  plan: "starter" | "growth" | "pro";
  plan_name: string;
  status: "trialing" | "active" | "past_due" | "canceled" | "incomplete";
  trial_end: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  order_count: number;
  order_limit: number;
  overage_count: number;
  is_active: boolean;
}
```

Update the `Restaurant` interface to include subscription:

```typescript
export interface Restaurant {
  id: string;
  name: string;
  slug: string;
  phone: string;
  address: string;
  homepage: string;
  logo_url: string;
  tax_rate: string;
  created_at: string;
  subscription?: Subscription;
}
```

**Step 2: Add API functions**

Add to `frontend/src/lib/api.ts`:

```typescript
import type { Subscription } from "@/types";

export async function fetchSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(`/api/restaurants/${slug}/subscription/`);
}

export async function createCheckoutSession(
  slug: string,
  plan: string,
  interval: "monthly" | "annual"
): Promise<{ checkout_url: string }> {
  return apiFetch<{ checkout_url: string }>(
    `/api/restaurants/${slug}/subscription/checkout/`,
    {
      method: "POST",
      body: JSON.stringify({ plan, interval }),
    }
  );
}

export async function createBillingPortal(
  slug: string
): Promise<{ portal_url: string }> {
  return apiFetch<{ portal_url: string }>(
    `/api/restaurants/${slug}/subscription/portal/`,
    { method: "POST" }
  );
}

export async function cancelSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/cancel/`,
    { method: "POST" }
  );
}

export async function reactivateSubscription(slug: string): Promise<Subscription> {
  return apiFetch<Subscription>(
    `/api/restaurants/${slug}/subscription/reactivate/`,
    { method: "POST" }
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat: add subscription types and API functions to frontend"
```

---

### Task 9: Frontend - Subscription Hooks

**Files:**
- Create: `frontend/src/hooks/use-subscription.ts`

**Step 1: Create subscription hooks**

```typescript
// frontend/src/hooks/use-subscription.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSubscription,
  createCheckoutSession,
  createBillingPortal,
  cancelSubscription,
  reactivateSubscription,
} from "@/lib/api";

export function useSubscription(slug: string) {
  return useQuery({
    queryKey: ["subscription", slug],
    queryFn: () => fetchSubscription(slug),
    enabled: !!slug,
  });
}

export function useCreateCheckout(slug: string) {
  return useMutation({
    mutationFn: ({ plan, interval }: { plan: string; interval: "monthly" | "annual" }) =>
      createCheckoutSession(slug, plan, interval),
    onSuccess: (data) => {
      window.location.href = data.checkout_url;
    },
  });
}

export function useCreateBillingPortal(slug: string) {
  return useMutation({
    mutationFn: () => createBillingPortal(slug),
    onSuccess: (data) => {
      window.location.href = data.portal_url;
    },
  });
}

export function useCancelSubscription(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelSubscription(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription", slug] });
    },
  });
}

export function useReactivateSubscription(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => reactivateSubscription(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["subscription", slug] });
    },
  });
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/use-subscription.ts
git commit -m "feat: add subscription React Query hooks"
```

---

### Task 10: Frontend - Billing Page

**Files:**
- Create: `frontend/src/app/admin/[slug]/billing/page.tsx`

**Step 1: Create the billing page**

```tsx
"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  useSubscription,
  useCreateCheckout,
  useCreateBillingPortal,
  useCancelSubscription,
  useReactivateSubscription,
} from "@/hooks/use-subscription";

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    monthlyPrice: 49,
    annualPrice: 40,
    orderLimit: 200,
    overage: "$0.20",
    description: "For small cafes (~7 orders/day)",
  },
  {
    id: "growth",
    name: "Growth",
    monthlyPrice: 99,
    annualPrice: 82,
    orderLimit: 600,
    overage: "$0.15",
    description: "For typical independents (~20 orders/day)",
  },
  {
    id: "pro",
    name: "Pro",
    monthlyPrice: 199,
    annualPrice: 166,
    orderLimit: 1500,
    overage: "$0.10",
    description: "For busy restaurants (~50 orders/day)",
  },
];

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "active" ? "default" :
    status === "trialing" ? "secondary" :
    status === "past_due" ? "destructive" :
    "outline";

  return <Badge variant={variant}>{status.replace("_", " ")}</Badge>;
}

export default function BillingPage() {
  const params = useParams<{ slug: string }>();
  const { data: subscription, isLoading } = useSubscription(params.slug);
  const createCheckout = useCreateCheckout(params.slug);
  const createPortal = useCreateBillingPortal(params.slug);
  const cancelSub = useCancelSubscription(params.slug);
  const reactivateSub = useReactivateSubscription(params.slug);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const usagePercent = subscription
    ? Math.round((subscription.order_count / subscription.order_limit) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:underline"
        >
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold mb-6">Billing & Subscription</h1>

        {/* Current Plan */}
        {subscription && (
          <Card className="p-6 mb-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-lg font-semibold">Current Plan</h2>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-2xl font-bold">
                    {subscription.plan_name}
                  </span>
                  <StatusBadge status={subscription.status} />
                  {subscription.cancel_at_period_end && (
                    <Badge variant="outline">Cancels at period end</Badge>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                {subscription.stripe_subscription_id && (
                  <Button
                    variant="outline"
                    onClick={() => createPortal.mutate()}
                    disabled={createPortal.isPending}
                  >
                    {createPortal.isPending ? "Loading..." : "Manage Billing"}
                  </Button>
                )}
                {subscription.stripe_subscription_id &&
                  subscription.is_active &&
                  !subscription.cancel_at_period_end && (
                    <Button
                      variant="destructive"
                      onClick={() => {
                        if (confirm("Cancel your subscription? You'll retain access until the end of your billing period.")) {
                          cancelSub.mutate();
                        }
                      }}
                      disabled={cancelSub.isPending}
                    >
                      {cancelSub.isPending ? "Canceling..." : "Cancel Subscription"}
                    </Button>
                  )}
                {subscription.cancel_at_period_end && (
                  <Button
                    variant="default"
                    onClick={() => reactivateSub.mutate()}
                    disabled={reactivateSub.isPending}
                  >
                    {reactivateSub.isPending ? "Reactivating..." : "Reactivate Subscription"}
                  </Button>
                )}
              </div>
            </div>

            {/* Usage */}
            <div className="mt-4">
              <div className="flex justify-between text-sm mb-1">
                <span>
                  Orders this period: {subscription.order_count} / {subscription.order_limit}
                </span>
                <span>{usagePercent}%</span>
              </div>
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    usagePercent >= 100
                      ? "bg-destructive"
                      : usagePercent >= 80
                      ? "bg-yellow-500"
                      : "bg-primary"
                  }`}
                  style={{ width: `${Math.min(usagePercent, 100)}%` }}
                />
              </div>
              {subscription.overage_count > 0 && (
                <p className="text-sm text-muted-foreground mt-1">
                  {subscription.overage_count} overage orders this period
                </p>
              )}
            </div>

            {/* Trial info */}
            {subscription.status === "trialing" && subscription.trial_end && (
              <p className="text-sm text-muted-foreground mt-4">
                Trial ends: {new Date(subscription.trial_end).toLocaleDateString()}
              </p>
            )}

            {/* Period info */}
            {subscription.current_period_end && subscription.status !== "trialing" && (
              <p className="text-sm text-muted-foreground mt-2">
                Current period ends: {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}
          </Card>
        )}

        {/* Plan Selection */}
        <h2 className="text-lg font-semibold mb-4">
          {subscription?.status === "trialing" || subscription?.status === "canceled"
            ? "Choose a Plan"
            : "Change Plan"}
        </h2>
        <div className="grid md:grid-cols-3 gap-4">
          {PLANS.map((plan) => {
            const isCurrent = subscription?.plan === plan.id && subscription?.is_active;
            return (
              <Card
                key={plan.id}
                className={`p-6 ${isCurrent ? "border-primary border-2" : ""}`}
              >
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mb-3">
                  {plan.description}
                </p>
                <div className="mb-4">
                  <span className="text-3xl font-bold">${plan.monthlyPrice}</span>
                  <span className="text-muted-foreground">/mo</span>
                  <p className="text-xs text-muted-foreground mt-1">
                    or ${plan.annualPrice}/mo billed annually
                  </p>
                </div>
                <ul className="text-sm space-y-1 mb-4">
                  <li>{plan.orderLimit.toLocaleString()} orders/month</li>
                  <li>{plan.overage}/order overage</li>
                  <li>All features included</li>
                </ul>
                {isCurrent ? (
                  <Button variant="outline" className="w-full" disabled>
                    Current Plan
                  </Button>
                ) : (
                  <div className="space-y-2">
                    <Button
                      className="w-full"
                      onClick={() =>
                        createCheckout.mutate({
                          plan: plan.id,
                          interval: "monthly",
                        })
                      }
                      disabled={createCheckout.isPending}
                    >
                      {createCheckout.isPending ? "Loading..." : `$${plan.monthlyPrice}/mo`}
                    </Button>
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() =>
                        createCheckout.mutate({
                          plan: plan.id,
                          interval: "annual",
                        })
                      }
                      disabled={createCheckout.isPending}
                    >
                      {createCheckout.isPending ? "Loading..." : `$${plan.annualPrice}/mo annual`}
                    </Button>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/admin/\[slug\]/billing/page.tsx
git commit -m "feat: add billing page with plan selection and usage display"
```

---

### Task 11: Frontend - Add Billing Link to Admin Dashboard

**Files:**
- Modify: `frontend/src/app/admin/page.tsx`

**Step 1: Add billing button to restaurant cards**

In `frontend/src/app/admin/page.tsx`, add a "Billing" link in the restaurant card buttons (after the Settings link, around line 169):

```tsx
<Link href={`/admin/${r.slug}/billing`}>
  <Button variant="outline" size="sm">Billing</Button>
</Link>
```

Also add a subscription status badge to each restaurant card. After the slug line (line 160), add:

```tsx
{r.subscription && (
  <div className="flex items-center gap-2 mt-1">
    <span className="text-xs px-2 py-0.5 rounded-full bg-muted">
      {r.subscription.plan_name}
    </span>
    <span className={`text-xs px-2 py-0.5 rounded-full ${
      r.subscription.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
    }`}>
      {r.subscription.status.replace("_", " ")}
    </span>
  </div>
)}
```

**Step 2: Commit**

```bash
git add frontend/src/app/admin/page.tsx
git commit -m "feat: add billing link and subscription badge to admin dashboard"
```

---

### Task 12: Frontend Build Verification

**Step 1: Run the frontend build**

```bash
cd frontend && npm run build
```

Fix any TypeScript errors that surface.

**Step 2: Run the backend tests**

```bash
cd backend && python -m pytest -v
```

Fix any failing tests.

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve build and test issues"
```

---

## Summary of All Tasks

| # | Task | Files |
|---|------|-------|
| 1 | Settings config | `config/settings.py` |
| 2 | Subscription model | `restaurants/models.py`, migration, tests |
| 3 | Auto-create trial | `restaurants/serializers.py`, tests |
| 4 | API endpoints | `restaurants/views.py`, `urls.py`, `serializers.py`, tests |
| 5 | Webhook handler | `orders/views.py`, tests |
| 6 | Subscription gate | `orders/views.py`, tests |
| 7 | Restaurant API response | `restaurants/serializers.py`, tests |
| 8 | Frontend types + API | `types/index.ts`, `lib/api.ts` |
| 9 | Frontend hooks | `hooks/use-subscription.ts` |
| 10 | Billing page | `admin/[slug]/billing/page.tsx` |
| 11 | Dashboard link | `admin/page.tsx` |
| 12 | Build verification | All |
