# Restaurant Payout System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement daily restaurant payouts via Stripe Connect with separate charges and transfers.

**Architecture:** Platform collects diner payments into its Stripe account (no change to existing PaymentIntent flow). A daily Celery Beat job transfers settled funds (T+2) to each restaurant's Stripe Connect Express account. Restaurants onboard via Stripe's hosted flow.

**Tech Stack:** Django 4.2, DRF, PostgreSQL, Redis, Celery + django-celery-beat, Stripe Connect API

**Spec:** `docs/superpowers/specs/2026-03-26-restaurant-payout-design.md`

---

## Chunk 1: Data Models & Migrations

### Task 1: ConnectedAccount model

**Files:**
- Modify: `backend/restaurants/models.py` (after line 168)
- Create: `backend/restaurants/tests/test_models.py`

- [ ] **Step 1: Write failing test for ConnectedAccount model**

```python
# backend/restaurants/tests/test_models.py
import pytest
from django.db import IntegrityError
from restaurants.models import ConnectedAccount, Restaurant, User


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.mark.django_db
class TestConnectedAccount:
    def test_create_connected_account(self, restaurant):
        account = ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
        )
        assert account.stripe_account_id == "acct_test123"
        assert account.onboarding_complete is False
        assert account.payouts_enabled is False
        assert account.charges_enabled is False
        assert account.pending_refund_balance == 0
        assert account.restaurant == restaurant

    def test_one_to_one_constraint(self, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
        )
        with pytest.raises(IntegrityError):
            ConnectedAccount.objects.create(
                restaurant=restaurant,
                stripe_account_id="acct_test456",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_models.py -v`
Expected: FAIL — ConnectedAccount not defined

- [ ] **Step 3: Implement ConnectedAccount model**

Add to `backend/restaurants/models.py` after `MenuItemModifier`:

```python
class ConnectedAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.OneToOneField(
        Restaurant, on_delete=models.CASCADE, related_name="connected_account"
    )
    stripe_account_id = models.CharField(max_length=255, unique=True)
    onboarding_complete = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    charges_enabled = models.BooleanField(default=False)
    pending_refund_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ConnectedAccount({self.restaurant.name}, {self.stripe_account_id})"
```

- [ ] **Step 4: Create migration**

Run: `cd backend && python manage.py makemigrations restaurants`

- [ ] **Step 5: Run migration**

Run: `cd backend && python manage.py migrate`

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/ backend/restaurants/tests/test_models.py
git commit -m "feat: add ConnectedAccount model for Stripe Connect"
```

---

### Task 2: Payout model

**Files:**
- Modify: `backend/restaurants/models.py`
- Modify: `backend/restaurants/tests/test_models.py`

- [ ] **Step 1: Write failing test for Payout model**

Add to `backend/restaurants/tests/test_models.py`:

```python
from restaurants.models import Payout


@pytest.mark.django_db
class TestPayout:
    def test_create_payout(self, restaurant):
        payout = Payout.objects.create(
            restaurant=restaurant,
            stripe_transfer_id="tr_test123",
            amount=150.00,
            currency="usd",
            orders_count=5,
            period_start="2026-03-25",
            period_end="2026-03-25",
        )
        assert payout.status == "pending"
        assert payout.fee_amount == 0
        assert payout.fee_rate == 0
        assert payout.fee_fixed == 0
        assert payout.stripe_payout_id is None

    def test_payout_status_choices(self, restaurant):
        payout = Payout.objects.create(
            restaurant=restaurant,
            stripe_transfer_id="tr_test456",
            amount=100.00,
            currency="usd",
            status="in_transit",
            orders_count=3,
            period_start="2026-03-25",
            period_end="2026-03-25",
        )
        assert payout.status == "in_transit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_models.py::TestPayout -v`
Expected: FAIL — Payout not defined

- [ ] **Step 3: Implement Payout model**

Add to `backend/restaurants/models.py` after `ConnectedAccount`:

```python
class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        IN_TRANSIT = "in_transit"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="payouts"
    )
    stripe_transfer_id = models.CharField(max_length=255, unique=True)
    stripe_payout_id = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fee_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    orders_count = models.PositiveIntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payout({self.restaurant.name}, {self.amount} {self.currency}, {self.status})"
```

- [ ] **Step 4: Create and run migration**

Run: `cd backend && python manage.py makemigrations restaurants && python manage.py migrate`

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_models.py::TestPayout -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/ backend/restaurants/tests/test_models.py
git commit -m "feat: add Payout model for restaurant fund transfers"
```

---

### Task 3: Order model changes (payout_status, paid_at, payout FK)

**Files:**
- Modify: `backend/orders/models.py` (add fields after line 64)
- Create: `backend/orders/tests/test_models.py`

- [ ] **Step 1: Write failing test for new Order fields**

```python
# backend/orders/tests/test_models.py
import pytest
from django.utils import timezone
from orders.models import Order
from restaurants.models import Restaurant, User


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.mark.django_db
class TestOrderPayoutFields:
    def test_default_payout_status(self, restaurant):
        order = Order.objects.create(
            restaurant=restaurant,
            raw_input="test order",
            subtotal=10.00,
            tax_rate=0,
            tax_amount=0,
            total_price=10.00,
        )
        assert order.payout_status == "pending"
        assert order.paid_at is None
        assert order.payout is None

    def test_set_paid_at(self, restaurant):
        now = timezone.now()
        order = Order.objects.create(
            restaurant=restaurant,
            raw_input="test order",
            subtotal=10.00,
            tax_rate=0,
            tax_amount=0,
            total_price=10.00,
            paid_at=now,
        )
        assert order.paid_at == now
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_models.py -v`
Expected: FAIL — payout_status field not found

- [ ] **Step 3: Add fields to Order model**

Modify `backend/orders/models.py`. Add after `stripe_payment_method_id` field (around line 64):

```python
    class PayoutStatus(models.TextChoices):
        PENDING = "pending"
        TRANSFERRED = "transferred"
        PAID_OUT = "paid_out"
        FAILED = "failed"

    payout_status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
    )
    payout = models.ForeignKey(
        "restaurants.Payout",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 4: Create migration with default for existing orders**

Run: `cd backend && python manage.py makemigrations orders`

Then edit the generated migration to set `payout_status` default to `"transferred"` for existing rows:

Add a `RunPython` operation after the field additions:

```python
from django.db import migrations

def set_existing_orders_transferred(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.all().update(payout_status="transferred")

# Add to operations list:
migrations.RunPython(set_existing_orders_transferred, migrations.RunPython.noop),
```

- [ ] **Step 5: Run migration**

Run: `cd backend && python manage.py migrate`

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest orders/tests/test_models.py -v`
Expected: PASS

Note: The `test_default_payout_status` test creates a new order, so it gets the model default of `"pending"`. Existing orders in the DB get migrated to `"transferred"`.

- [ ] **Step 7: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/ backend/orders/tests/test_models.py
git commit -m "feat: add payout_status, paid_at, and payout FK to Order model"
```

---

### Task 4: Update paid_at in existing payment handlers

**Files:**
- Modify: `backend/orders/services.py` (lines 412-445 and 510-522)
- Modify: `backend/orders/tests/` (existing payment tests)

- [ ] **Step 1: Write failing test for paid_at being set**

```python
# backend/orders/tests/test_paid_at.py
import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from orders.services import OrderService
from orders.models import Order
from restaurants.models import Restaurant, User


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.fixture
def pending_order(restaurant):
    return Order.objects.create(
        restaurant=restaurant,
        raw_input="test order",
        status="pending_payment",
        payment_status="pending",
        subtotal=10.00,
        tax_rate=0,
        tax_amount=0,
        total_price=10.00,
        stripe_payment_intent_id="pi_test123",
    )


@pytest.mark.django_db
class TestPaidAtTimestamp:
    @patch("orders.services.stripe.PaymentIntent.retrieve")
    def test_confirm_payment_sets_paid_at(self, mock_retrieve, pending_order):
        mock_intent = MagicMock()
        mock_intent.status = "succeeded"
        mock_retrieve.return_value = mock_intent

        OrderService.confirm_payment(pending_order)
        pending_order.refresh_from_db()

        assert pending_order.paid_at is not None
        assert pending_order.payment_status == "paid"

    def test_webhook_payment_succeeded_sets_paid_at(self, pending_order):
        OrderService._handle_payment_succeeded(
            {"id": "pi_test123"}
        )
        pending_order.refresh_from_db()

        assert pending_order.paid_at is not None
        assert pending_order.payment_status == "paid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_paid_at.py -v`
Expected: FAIL — paid_at is None after confirm/webhook

- [ ] **Step 3: Update confirm_payment to set paid_at**

In `backend/orders/services.py`, in `confirm_payment()` (around line 433-435), the existing code uses a queryset `.update()` call:
```python
Order.objects.filter(id=order.id, payment_status="pending").update(status="confirmed", payment_status="paid")
```

Add `paid_at=timezone.now()` to the `.update()` kwargs:
```python
Order.objects.filter(id=order.id, payment_status="pending").update(
    status="confirmed", payment_status="paid", paid_at=timezone.now()
)
```

Add `from django.utils import timezone` at top of file if not already imported.

- [ ] **Step 4: Update _handle_payment_succeeded to set paid_at**

In `backend/orders/services.py`, in `_handle_payment_succeeded()` (around line 515), where `Order.objects.filter(...).update(...)` is called, add `paid_at=timezone.now()` to the update kwargs.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest orders/tests/test_paid_at.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orders/services.py backend/orders/tests/test_paid_at.py
git commit -m "feat: set paid_at timestamp when order payment succeeds"
```

---

## Chunk 2: Celery Infrastructure

### Task 5: Install Celery dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add celery and django-celery-beat to dependencies**

In `backend/pyproject.toml`, add to `[project.dependencies]`:

```toml
celery[redis] = ">=5.3.0,<6.0.0"
django-celery-beat = ">=2.6.0,<3.0.0"
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && pip install -e .`

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "feat: add celery and django-celery-beat dependencies"
```

---

### Task 6: Celery app configuration

**Files:**
- Create: `backend/config/celery.py`
- Modify: `backend/config/__init__.py`
- Modify: `backend/config/settings.py`

- [ ] **Step 1: Create Celery app**

```python
# backend/config/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "daily-restaurant-payouts": {
        "task": "restaurants.tasks.process_daily_payouts",
        "schedule": crontab(hour=2, minute=0),
    },
}
```

- [ ] **Step 2: Update config/__init__.py to load Celery**

```python
# backend/config/__init__.py
from .celery import app as celery_app

__all__ = ("celery_app",)
```

- [ ] **Step 3: Add Celery settings to settings.py**

Add to `backend/config/settings.py` after the Stripe config section:

```python
# Celery
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Payout configuration
PAYOUT_CONFIG = {
    "settlement_days": 2,
    "job_run_hour_utc": 2,
    "default_fee_rate": 0,
    "default_fee_fixed_cents": 0,
}

STRIPE_CONNECT_WEBHOOK_SECRET = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET", "")
```

Add `"django_celery_beat"` to `INSTALLED_APPS`.

- [ ] **Step 4: Run django-celery-beat migrations**

Run: `cd backend && python manage.py migrate`

- [ ] **Step 5: Verify Celery app loads**

Run: `cd backend && python -c "from config.celery import app; print(app)"`
Expected: `<Celery config at 0x...>`

- [ ] **Step 6: Commit**

```bash
git add backend/config/celery.py backend/config/__init__.py backend/config/settings.py
git commit -m "feat: configure Celery app with Beat schedule for daily payouts"
```

---

### Task 7: Docker Compose services for Celery

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add celery-worker and celery-beat services**

Add after the `backend` service in `docker-compose.yml`:

```yaml
  celery-worker:
    build:
      context: ./backend
    command: celery -A config worker --loglevel=info
    volumes:
      - ./backend:/app
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery-beat:
    build:
      context: ./backend
    command: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - ./backend:/app
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 2: Verify docker-compose config is valid**

Run: `docker compose config --quiet`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add celery worker and beat services to docker-compose"
```

---

## Chunk 3: Stripe Connect Onboarding

### Task 8: Connect onboarding service methods

**Files:**
- Create: `backend/restaurants/services/connect_service.py`
- Create: `backend/restaurants/tests/test_connect_service.py`

Note: The existing `restaurants/services.py` is a single file. We'll create a `services/` package to keep payout logic separate. First, restructure:

- [ ] **Step 1: Convert services.py to a package**

```bash
cd backend/restaurants
mkdir services
mv services.py services/restaurant_service.py
touch services/__init__.py
```

In `backend/restaurants/services/__init__.py`:
```python
from .restaurant_service import RestaurantService

__all__ = ["RestaurantService"]
```

Verify nothing breaks: `cd backend && python -m pytest -x --timeout=30`

- [ ] **Step 2: Commit the restructure**

```bash
git add backend/restaurants/services/ backend/restaurants/
git commit -m "refactor: convert restaurants/services.py to package"
```

- [ ] **Step 3: Write failing tests for ConnectService**

```python
# backend/restaurants/tests/test_connect_service.py
import pytest
from unittest.mock import patch, MagicMock
from restaurants.services.connect_service import ConnectService
from restaurants.models import ConnectedAccount, Restaurant, User


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.mark.django_db
class TestConnectServiceOnboard:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_create_connect_account(self, mock_link, mock_create, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        result = ConnectService.create_onboarding_link(restaurant)

        assert result["url"] == "https://connect.stripe.com/setup/abc"
        account = ConnectedAccount.objects.get(restaurant=restaurant)
        assert account.stripe_account_id == "acct_test123"

    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_returns_new_link_if_account_exists(self, mock_link, mock_create, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant, stripe_account_id="acct_existing"
        )
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/new")

        result = ConnectService.create_onboarding_link(restaurant)

        assert result["url"] == "https://connect.stripe.com/setup/new"
        mock_create.assert_not_called()


@pytest.mark.django_db
class TestConnectServiceStatus:
    def test_status_no_account(self, restaurant):
        result = ConnectService.get_connect_status(restaurant)
        assert result["has_account"] is False
        assert result["payouts_enabled"] is False

    def test_status_with_account(self, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
            payouts_enabled=True,
            charges_enabled=True,
        )
        result = ConnectService.get_connect_status(restaurant)
        assert result["has_account"] is True
        assert result["payouts_enabled"] is True


@pytest.mark.django_db
class TestConnectServiceDashboard:
    @patch("restaurants.services.connect_service.stripe.Account.create_login_link")
    def test_create_dashboard_link(self, mock_login_link, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
        )
        mock_login_link.return_value = MagicMock(url="https://connect.stripe.com/express/abc")

        result = ConnectService.create_dashboard_link(restaurant)
        assert result["url"] == "https://connect.stripe.com/express/abc"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd backend && python -m pytest restaurants/tests/test_connect_service.py -v`
Expected: FAIL — ConnectService not defined

- [ ] **Step 5: Implement ConnectService**

```python
# backend/restaurants/services/connect_service.py
import stripe
from django.conf import settings
from rest_framework.exceptions import NotFound

from restaurants.models import ConnectedAccount

stripe.api_key = settings.STRIPE_SECRET_KEY


class ConnectService:
    @staticmethod
    def create_onboarding_link(restaurant):
        try:
            account = restaurant.connected_account
        except ConnectedAccount.DoesNotExist:
            stripe_account = stripe.Account.create(
                type="express",
                metadata={"restaurant_id": str(restaurant.id)},
            )
            account = ConnectedAccount.objects.create(
                restaurant=restaurant,
                stripe_account_id=stripe_account.id,
            )

        account_link = stripe.AccountLink.create(
            account=account.stripe_account_id,
            refresh_url=f"{settings.FRONTEND_URL}/dashboard/{restaurant.slug}/connect/refresh",
            return_url=f"{settings.FRONTEND_URL}/dashboard/{restaurant.slug}/connect/complete",
            type="account_onboarding",
        )
        return {"url": account_link.url}

    @staticmethod
    def get_connect_status(restaurant):
        try:
            account = restaurant.connected_account
            return {
                "has_account": True,
                "onboarding_complete": account.onboarding_complete,
                "payouts_enabled": account.payouts_enabled,
                "charges_enabled": account.charges_enabled,
            }
        except ConnectedAccount.DoesNotExist:
            return {
                "has_account": False,
                "onboarding_complete": False,
                "payouts_enabled": False,
                "charges_enabled": False,
            }

    @staticmethod
    def create_dashboard_link(restaurant):
        try:
            account = restaurant.connected_account
        except ConnectedAccount.DoesNotExist:
            raise NotFound("No connected account found. Complete onboarding first.")

        if not account.onboarding_complete:
            raise NotFound("Onboarding not complete.")

        login_link = stripe.Account.create_login_link(
            account.stripe_account_id,
        )
        return {"url": login_link.url}
```

- [ ] **Step 6: Export from __init__.py**

Add to `backend/restaurants/services/__init__.py`:

```python
from .connect_service import ConnectService

__all__ = ["RestaurantService", "ConnectService"]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_connect_service.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/restaurants/services/ backend/restaurants/tests/test_connect_service.py
git commit -m "feat: add ConnectService for Stripe Connect onboarding"
```

---

### Task 9: Connect onboarding API endpoints

**Files:**
- Modify: `backend/restaurants/views.py` (add views after line 225)
- Modify: `backend/restaurants/urls.py` (add URL patterns)
- Create: `backend/restaurants/tests/test_connect_views.py`

- [ ] **Step 1: Write failing test for onboarding endpoints**

```python
# backend/restaurants/tests/test_connect_views.py
import pytest
from unittest.mock import patch, MagicMock
from django.test import override_settings
from rest_framework.test import APIClient
from restaurants.models import Restaurant, User, ConnectedAccount


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest restaurants/tests/test_connect_views.py -v`
Expected: FAIL — 404 (routes don't exist)

- [ ] **Step 3: Implement views**

Add to `backend/restaurants/views.py`:

```python
from restaurants.services import ConnectService


class ConnectOnboardView(RestaurantMixin, APIView):
    def post(self, request, slug):
        restaurant = self.get_restaurant()
        result = ConnectService.create_onboarding_link(restaurant)
        return Response(result)


class ConnectStatusView(RestaurantMixin, APIView):
    def get(self, request, slug):
        restaurant = self.get_restaurant()
        result = ConnectService.get_connect_status(restaurant)
        return Response(result)


class ConnectDashboardView(RestaurantMixin, APIView):
    def post(self, request, slug):
        restaurant = self.get_restaurant()
        result = ConnectService.create_dashboard_link(restaurant)
        return Response(result)
```

- [ ] **Step 4: Add URL patterns**

Add to `backend/restaurants/urls.py` after the subscription URLs:

```python
from restaurants.views import ConnectOnboardView, ConnectStatusView, ConnectDashboardView

# Connect (payout onboarding)
path("restaurants/<slug:slug>/connect/onboard/", ConnectOnboardView.as_view(), name="connect-onboard"),
path("restaurants/<slug:slug>/connect/status/", ConnectStatusView.as_view(), name="connect-status"),
path("restaurants/<slug:slug>/connect/dashboard/", ConnectDashboardView.as_view(), name="connect-dashboard"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_connect_views.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/views.py backend/restaurants/urls.py backend/restaurants/tests/test_connect_views.py
git commit -m "feat: add Connect onboarding API endpoints"
```

---

## Chunk 4: Daily Payout Job

### Task 10: Payout service

**Files:**
- Create: `backend/restaurants/services/payout_service.py`
- Create: `backend/restaurants/tests/test_payout_service.py`

- [ ] **Step 1: Write failing tests for PayoutService**

```python
# backend/restaurants/tests/test_payout_service.py
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone
from restaurants.services.payout_service import PayoutService
from restaurants.models import ConnectedAccount, Payout, Restaurant, User
from orders.models import Order


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.fixture
def connected_account(restaurant):
    return ConnectedAccount.objects.create(
        restaurant=restaurant,
        stripe_account_id="acct_test123",
        onboarding_complete=True,
        payouts_enabled=True,
        charges_enabled=True,
    )


@pytest.fixture
def settled_paid_order(restaurant):
    """An order paid 3 days ago (past T+2 window)."""
    return Order.objects.create(
        restaurant=restaurant,
        raw_input="test order",
        status="confirmed",
        payment_status="paid",
        payout_status="pending",
        subtotal=Decimal("10.00"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total_price=Decimal("10.00"),
        paid_at=timezone.now() - timedelta(days=3),
    )


@pytest.mark.django_db
class TestPayoutServiceProcessRestaurant:
    @patch("restaurants.services.payout_service.stripe.Transfer.create")
    def test_creates_transfer_for_settled_orders(
        self, mock_transfer, connected_account, settled_paid_order
    ):
        mock_transfer.return_value = MagicMock(id="tr_test123")

        PayoutService.process_restaurant_payout(connected_account.restaurant)

        mock_transfer.assert_called_once()
        call_kwargs = mock_transfer.call_args[1]
        assert call_kwargs["amount"] == 1000  # $10.00 in cents
        assert call_kwargs["destination"] == "acct_test123"

        payout = Payout.objects.get(restaurant=connected_account.restaurant)
        assert payout.amount == Decimal("10.00")
        assert payout.status == "pending"
        assert payout.stripe_transfer_id == "tr_test123"

        settled_paid_order.refresh_from_db()
        assert settled_paid_order.payout_status == "transferred"
        assert settled_paid_order.payout == payout

    def test_skips_restaurant_without_connected_account(self, restaurant):
        # No connected account — should not raise
        PayoutService.process_restaurant_payout(restaurant)
        assert Payout.objects.count() == 0

    def test_skips_unsettled_orders(self, connected_account, restaurant):
        # Order paid 1 day ago — within T+2 window
        Order.objects.create(
            restaurant=restaurant,
            raw_input="test order",
            status="confirmed",
            payment_status="paid",
            payout_status="pending",
            subtotal=Decimal("10.00"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total_price=Decimal("10.00"),
            paid_at=timezone.now() - timedelta(days=1),
        )
        PayoutService.process_restaurant_payout(restaurant)
        assert Payout.objects.count() == 0

    @patch("restaurants.services.payout_service.stripe.Transfer.create")
    def test_deducts_pending_refund_balance(
        self, mock_transfer, connected_account, settled_paid_order
    ):
        connected_account.pending_refund_balance = Decimal("3.00")
        connected_account.save()
        mock_transfer.return_value = MagicMock(id="tr_test456")

        PayoutService.process_restaurant_payout(connected_account.restaurant)

        call_kwargs = mock_transfer.call_args[1]
        assert call_kwargs["amount"] == 700  # $10.00 - $3.00 refund = $7.00

        connected_account.refresh_from_db()
        assert connected_account.pending_refund_balance == Decimal("0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest restaurants/tests/test_payout_service.py -v`
Expected: FAIL — PayoutService not defined

- [ ] **Step 3: Implement PayoutService**

```python
# backend/restaurants/services/payout_service.py
import logging
from datetime import timedelta
from decimal import Decimal

import redis
import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from orders.models import Order
from restaurants.models import ConnectedAccount, Payout

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.CELERY_BROKER_URL)


class PayoutService:
    @staticmethod
    def process_restaurant_payout(restaurant):
        try:
            account = restaurant.connected_account
        except ConnectedAccount.DoesNotExist:
            return

        if not account.payouts_enabled:
            return

        # Acquire lock to prevent concurrent processing for this restaurant
        lock_key = f"payout-lock-{restaurant.id}"
        lock = redis_client.lock(lock_key, timeout=300)  # 5 min timeout
        if not lock.acquire(blocking=False):
            logger.warning(f"Payout lock already held for restaurant {restaurant.id}, skipping")
            return

        try:
            PayoutService._process_payout(restaurant, account)
        finally:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    @staticmethod
    def _process_payout(restaurant, account):
        """Internal method — called with lock held."""
        settlement_days = settings.PAYOUT_CONFIG["settlement_days"]
        cutoff = timezone.now() - timedelta(days=settlement_days)

        eligible_orders = Order.objects.filter(
            restaurant=restaurant,
            payment_status="paid",
            payout_status="pending",
            paid_at__lte=cutoff,
        )

        total = eligible_orders.aggregate(total=Sum("total_price"))["total"]
        if not total or total <= 0:
            return

        # Deduct pending refund balance
        refund_deduction = min(account.pending_refund_balance, total)
        transfer_amount = total - refund_deduction

        if transfer_amount <= 0:
            # Refund balance exceeds total — reduce balance, skip transfer
            account.pending_refund_balance -= total
            account.save(update_fields=["pending_refund_balance"])
            return

        transfer_amount_cents = int(transfer_amount * 100)
        today = timezone.now().date().isoformat()
        order_ids = list(eligible_orders.values_list("id", flat=True))

        try:
            with transaction.atomic():
                payout = Payout.objects.create(
                    restaurant=restaurant,
                    stripe_transfer_id="pending",
                    amount=transfer_amount,
                    currency=restaurant.currency.lower(),
                    orders_count=len(order_ids),
                    period_start=eligible_orders.order_by("paid_at").first().paid_at.date(),
                    period_end=eligible_orders.order_by("-paid_at").first().paid_at.date(),
                    fee_amount=Decimal("0"),
                )

                transfer = stripe.Transfer.create(
                    amount=transfer_amount_cents,
                    currency=restaurant.currency.lower(),
                    destination=account.stripe_account_id,
                    idempotency_key=f"payout-{restaurant.id}-{today}",
                    metadata={
                        "restaurant_id": str(restaurant.id),
                        "payout_id": str(payout.id),
                    },
                )

                payout.stripe_transfer_id = transfer.id
                payout.save(update_fields=["stripe_transfer_id"])

                eligible_orders.update(
                    payout_status="transferred",
                    payout=payout,
                )

                if refund_deduction > 0:
                    account.pending_refund_balance -= refund_deduction
                    account.save(update_fields=["pending_refund_balance"])

        except stripe.error.StripeError as e:
            logger.error(
                f"Payout failed for restaurant {restaurant.id}: {e}",
                exc_info=True,
            )
            if payout and payout.pk:
                payout.status = "failed"
                payout.save(update_fields=["status"])

    @staticmethod
    def process_all_payouts():
        accounts = ConnectedAccount.objects.filter(
            payouts_enabled=True
        ).select_related("restaurant")

        for account in accounts:
            try:
                PayoutService.process_restaurant_payout(account.restaurant)
            except Exception as e:
                logger.error(
                    f"Unexpected error processing payout for restaurant {account.restaurant.id}: {e}",
                    exc_info=True,
                )
```

- [ ] **Step 4: Export from __init__.py**

Add to `backend/restaurants/services/__init__.py`:

```python
from .payout_service import PayoutService
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_payout_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/services/ backend/restaurants/tests/test_payout_service.py
git commit -m "feat: add PayoutService for daily restaurant fund transfers"
```

---

### Task 11: Celery task

**Files:**
- Create: `backend/restaurants/tasks.py`
- Create: `backend/restaurants/tests/test_tasks.py`

- [ ] **Step 1: Write failing test for the Celery task**

```python
# backend/restaurants/tests/test_tasks.py
import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestProcessDailyPayoutsTask:
    @patch("restaurants.services.payout_service.PayoutService.process_all_payouts")
    def test_task_calls_process_all_payouts(self, mock_process):
        from restaurants.tasks import process_daily_payouts

        process_daily_payouts()
        mock_process.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_tasks.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the Celery task**

```python
# backend/restaurants/tasks.py
import logging
from config.celery import app
from restaurants.services.payout_service import PayoutService

logger = logging.getLogger(__name__)


@app.task(name="restaurants.tasks.process_daily_payouts")
def process_daily_payouts():
    logger.info("Starting daily payout processing")
    PayoutService.process_all_payouts()
    logger.info("Daily payout processing complete")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/tasks.py backend/restaurants/tests/test_tasks.py
git commit -m "feat: add Celery task for daily payout processing"
```

---

## Chunk 5: Webhook Handlers

### Task 12: Connect webhook handler for account.updated

**Files:**
- Modify: `backend/orders/services.py`
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/urls.py`
- Create: `backend/orders/tests/test_connect_webhooks.py`

- [ ] **Step 1: Write failing test for account.updated webhook**

```python
# backend/orders/tests/test_connect_webhooks.py
import pytest
from unittest.mock import patch, MagicMock
from restaurants.models import ConnectedAccount, Restaurant, User


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.fixture
def connected_account(restaurant):
    return ConnectedAccount.objects.create(
        restaurant=restaurant,
        stripe_account_id="acct_test123",
        onboarding_complete=False,
        payouts_enabled=False,
        charges_enabled=False,
    )


@pytest.mark.django_db
class TestAccountUpdatedWebhook:
    def test_updates_connected_account(self, connected_account):
        from orders.services import OrderService

        event_data = {
            "type": "account.updated",
            "account": "acct_test123",
            "data": {
                "object": {
                    "id": "acct_test123",
                    "payouts_enabled": True,
                    "charges_enabled": True,
                    "details_submitted": True,
                }
            },
        }

        OrderService._handle_account_updated(event_data["data"])

        connected_account.refresh_from_db()
        assert connected_account.payouts_enabled is True
        assert connected_account.charges_enabled is True
        assert connected_account.onboarding_complete is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_connect_webhooks.py -v`
Expected: FAIL — _handle_account_updated not defined

- [ ] **Step 3: Add _handle_account_updated to OrderService**

Add to `backend/orders/services.py`:

```python
    @staticmethod
    def _handle_account_updated(data):
        from restaurants.models import ConnectedAccount

        account_obj = data["object"]
        account_id = account_obj["id"]

        try:
            account = ConnectedAccount.objects.get(stripe_account_id=account_id)
            account.payouts_enabled = account_obj.get("payouts_enabled", False)
            account.charges_enabled = account_obj.get("charges_enabled", False)
            account.onboarding_complete = account_obj.get("details_submitted", False)
            account.save(update_fields=[
                "payouts_enabled", "charges_enabled", "onboarding_complete", "updated_at"
            ])
        except ConnectedAccount.DoesNotExist:
            logger.warning(f"ConnectedAccount not found for {account_id}")
```

- [ ] **Step 4: Add handle_stripe_connect_webhook method**

Add to `backend/orders/services.py`:

```python
    CONNECT_EVENT_HANDLERS = {
        "account.updated": "_handle_account_updated",
        "payout.paid": "_handle_payout_paid",
        "payout.failed": "_handle_payout_failed",
    }

    @staticmethod
    def handle_stripe_connect_webhook(payload, sig_header):
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_CONNECT_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            raise ValidationError("Invalid webhook signature")

        handler_name = OrderService.CONNECT_EVENT_HANDLERS.get(event["type"])
        if handler_name:
            handler = getattr(OrderService, handler_name)
            # Connect events: pass event["data"] with "account" injected
            # so handlers can identify the connected account
            data = event["data"]
            data["account"] = event.get("account")
            handler(data)

        return {"status": "ok"}
```

Also add `transfer.created` and `transfer.failed` to the existing `EVENT_HANDLERS` dict:

```python
    "transfer.created": "_handle_transfer_created",
    "transfer.failed": "_handle_transfer_failed",
```

- [ ] **Step 5: Add StripeConnectWebhookView**

Add to `backend/orders/views.py`:

```python
class StripeConnectWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        result = OrderService.handle_stripe_connect_webhook(
            request.body, request.META.get("HTTP_STRIPE_SIGNATURE", "")
        )
        return Response(result)
```

- [ ] **Step 6: Add URL pattern**

Add to `backend/orders/urls.py`:

```python
from orders.views import StripeConnectWebhookView

path("webhooks/stripe-connect/", StripeConnectWebhookView.as_view(), name="stripe-connect-webhook"),
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && python -m pytest orders/tests/test_connect_webhooks.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/orders/services.py backend/orders/views.py backend/orders/urls.py backend/orders/tests/test_connect_webhooks.py
git commit -m "feat: add Connect webhook endpoint and account.updated handler"
```

---

### Task 13: Transfer and payout webhook handlers

**Files:**
- Modify: `backend/orders/services.py`
- Modify: `backend/orders/tests/test_connect_webhooks.py`

- [ ] **Step 1: Write failing tests for transfer/payout webhooks**

Add to `backend/orders/tests/test_connect_webhooks.py`:

```python
from decimal import Decimal
from restaurants.models import Payout


@pytest.fixture
def payout(restaurant):
    return Payout.objects.create(
        restaurant=restaurant,
        stripe_transfer_id="tr_test123",
        amount=Decimal("50.00"),
        currency="usd",
        status="pending",
        orders_count=3,
        period_start="2026-03-25",
        period_end="2026-03-25",
    )


@pytest.mark.django_db
class TestTransferCreatedWebhook:
    def test_sets_payout_in_transit(self, payout):
        from orders.services import OrderService

        OrderService._handle_transfer_created(
            {"object": {"id": "tr_test123"}}
        )
        payout.refresh_from_db()
        assert payout.status == "in_transit"


@pytest.mark.django_db
class TestTransferFailedWebhook:
    def test_sets_payout_failed(self, payout):
        from orders.services import OrderService

        OrderService._handle_transfer_failed(
            {"object": {"id": "tr_test123"}}
        )
        payout.refresh_from_db()
        assert payout.status == "failed"


@pytest.mark.django_db
class TestPayoutPaidWebhook:
    def test_sets_payout_completed(self, payout, connected_account):
        from orders.services import OrderService

        payout.status = "in_transit"
        payout.save()

        OrderService._handle_payout_paid({
            "object": {
                "id": "po_test123",
                "destination": "ba_xxx",
                "amount": 5000,
                "currency": "usd",
            },
            "account": "acct_test123",
        })
        payout.refresh_from_db()
        assert payout.status == "completed"
        assert payout.stripe_payout_id == "po_test123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest orders/tests/test_connect_webhooks.py -k "transfer or payout_paid" -v`
Expected: FAIL — handler methods not defined

- [ ] **Step 3: Implement transfer handlers**

Add to `backend/orders/services.py` in `OrderService`:

```python
    @staticmethod
    def _handle_transfer_created(data):
        from restaurants.models import Payout

        transfer_id = data["object"]["id"]
        Payout.objects.filter(stripe_transfer_id=transfer_id).update(
            status="in_transit"
        )

    @staticmethod
    def _handle_transfer_failed(data):
        from restaurants.models import Payout

        transfer_id = data["object"]["id"]
        payout = Payout.objects.filter(stripe_transfer_id=transfer_id).first()
        if payout:
            payout.status = "failed"
            payout.save(update_fields=["status"])
            # Revert orders so they're picked up in next payout run
            payout.orders.update(payout_status="pending", payout=None)

    @staticmethod
    def _handle_payout_paid(data):
        from restaurants.models import ConnectedAccount, Payout

        payout_obj = data["object"]
        stripe_payout_id = payout_obj["id"]
        amount_cents = payout_obj["amount"]
        account_id = data.get("account") or payout_obj.get("account")

        try:
            account = ConnectedAccount.objects.get(stripe_account_id=account_id)
        except ConnectedAccount.DoesNotExist:
            logger.warning(f"ConnectedAccount not found for payout event: {account_id}")
            return

        # Match by connected account + in_transit status + amount
        payout = Payout.objects.filter(
            restaurant=account.restaurant,
            status="in_transit",
            amount=Decimal(amount_cents) / 100,
        ).order_by("created_at").first()

        if payout:
            payout.status = "completed"
            payout.stripe_payout_id = stripe_payout_id
            payout.save(update_fields=["status", "stripe_payout_id"])
            payout.orders.update(payout_status="paid_out")

    @staticmethod
    def _handle_payout_failed(data):
        from restaurants.models import ConnectedAccount, Payout

        payout_obj = data["object"]
        account_id = data.get("account") or payout_obj.get("account")
        amount_cents = payout_obj["amount"]

        try:
            account = ConnectedAccount.objects.get(stripe_account_id=account_id)
        except ConnectedAccount.DoesNotExist:
            return

        payout = Payout.objects.filter(
            restaurant=account.restaurant,
            status="in_transit",
            amount=Decimal(amount_cents) / 100,
        ).order_by("created_at").first()

        if payout:
            payout.status = "failed"
            payout.save(update_fields=["status"])
```

Don't forget to add `from decimal import Decimal` to the imports if not present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest orders/tests/test_connect_webhooks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/services.py backend/orders/tests/test_connect_webhooks.py
git commit -m "feat: add transfer and payout webhook handlers"
```

---

## Chunk 6: Payout Dashboard API & Serializers

### Task 14: Payout serializers

**Files:**
- Create: `backend/restaurants/serializers/payout_serializers.py`

Note: Similar to services, if `serializers.py` is a single file, convert to a package first.

- [ ] **Step 1: Convert serializers.py to package**

```bash
cd backend/restaurants
mkdir serializers
mv serializers.py serializers/restaurant_serializers.py
touch serializers/__init__.py
```

In `backend/restaurants/serializers/__init__.py`:
```python
from .restaurant_serializers import *
```

Verify nothing breaks: `cd backend && python -m pytest -x --timeout=30`

- [ ] **Step 2: Commit restructure**

```bash
git add backend/restaurants/serializers/
git commit -m "refactor: convert restaurants/serializers.py to package"
```

- [ ] **Step 3: Create payout serializers**

```python
# backend/restaurants/serializers/payout_serializers.py
from rest_framework import serializers
from restaurants.models import Payout


class PayoutListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            "id", "amount", "currency", "status", "orders_count",
            "fee_amount", "period_start", "period_end", "created_at",
        ]


class PayoutDetailSerializer(serializers.ModelSerializer):
    orders = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id", "stripe_transfer_id", "stripe_payout_id",
            "amount", "currency", "status", "fee_amount", "fee_rate",
            "fee_fixed", "orders_count", "period_start", "period_end",
            "created_at", "orders",
        ]

    def get_orders(self, obj):
        from orders.serializers import OrderResponseSerializer

        return OrderResponseSerializer(obj.orders.all(), many=True).data
```

- [ ] **Step 4: Export from __init__.py**

Add to `backend/restaurants/serializers/__init__.py`:
```python
from .payout_serializers import PayoutListSerializer, PayoutDetailSerializer
```

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/serializers/
git commit -m "feat: add payout serializers"
```

---

### Task 15: Payout list and detail endpoints

**Files:**
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`
- Create: `backend/restaurants/tests/test_payout_views.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/restaurants/tests/test_payout_views.py
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from restaurants.models import Restaurant, User, Payout, ConnectedAccount


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


@pytest.fixture
def payout(restaurant):
    return Payout.objects.create(
        restaurant=restaurant,
        stripe_transfer_id="tr_test123",
        amount=Decimal("150.00"),
        currency="usd",
        status="completed",
        orders_count=5,
        period_start="2026-03-25",
        period_end="2026-03-25",
    )


@pytest.mark.django_db
class TestPayoutListView:
    def test_list_payouts(self, api_client, restaurant, payout):
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/payouts/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["amount"] == "150.00"

    def test_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.get(f"/api/restaurants/{restaurant.slug}/payouts/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestPayoutDetailView:
    def test_get_payout_detail(self, api_client, restaurant, payout):
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/payouts/{payout.id}/")
        assert response.status_code == 200
        assert response.data["stripe_transfer_id"] == "tr_test123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest restaurants/tests/test_payout_views.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement views**

Add to `backend/restaurants/views.py`:

```python
from rest_framework.pagination import PageNumberPagination
from restaurants.serializers import PayoutListSerializer, PayoutDetailSerializer
from restaurants.models import Payout


class PayoutPagination(PageNumberPagination):
    page_size = 20


class PayoutListView(RestaurantMixin, APIView):
    def get(self, request, slug):
        restaurant = self.get_restaurant()
        payouts = Payout.objects.filter(restaurant=restaurant)
        paginator = PayoutPagination()
        page = paginator.paginate_queryset(payouts, request)
        serializer = PayoutListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PayoutDetailView(RestaurantMixin, APIView):
    def get(self, request, slug, payout_id):
        restaurant = self.get_restaurant()
        try:
            payout = Payout.objects.get(id=payout_id, restaurant=restaurant)
        except Payout.DoesNotExist:
            raise NotFound("Payout not found")
        serializer = PayoutDetailSerializer(payout)
        return Response(serializer.data)
```

- [ ] **Step 4: Add URL patterns**

Add to `backend/restaurants/urls.py`:

```python
from restaurants.views import PayoutListView, PayoutDetailView

path("restaurants/<slug:slug>/payouts/", PayoutListView.as_view(), name="payout-list"),
path("restaurants/<slug:slug>/payouts/<uuid:payout_id>/", PayoutDetailView.as_view(), name="payout-detail"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_payout_views.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/views.py backend/restaurants/urls.py backend/restaurants/tests/test_payout_views.py
git commit -m "feat: add payout list and detail API endpoints"
```

---

## Chunk 7: Integration Test & Final Verification

### Task 16: End-to-end payout flow test

**Files:**
- Create: `backend/restaurants/tests/test_payout_integration.py`

- [ ] **Step 1: Write integration test covering the full flow**

```python
# backend/restaurants/tests/test_payout_integration.py
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone
from orders.models import Order
from restaurants.models import ConnectedAccount, Payout, Restaurant, User
from restaurants.services.payout_service import PayoutService
from orders.services import OrderService


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Integration Test", slug="integration-test", owner=owner)


@pytest.fixture
def connected_account(restaurant):
    return ConnectedAccount.objects.create(
        restaurant=restaurant,
        stripe_account_id="acct_integ123",
        onboarding_complete=True,
        payouts_enabled=True,
        charges_enabled=True,
    )


@pytest.mark.django_db
class TestFullPayoutFlow:
    @patch("restaurants.services.payout_service.stripe.Transfer.create")
    def test_full_flow_order_to_payout(self, mock_transfer, connected_account, restaurant):
        """Test: order paid → T+2 passes → daily job transfers → webhook completes."""
        # 1. Create paid orders (3 days ago = past T+2)
        for i in range(3):
            Order.objects.create(
                restaurant=restaurant,
                raw_input="test order",
                status="confirmed",
                payment_status="paid",
                payout_status="pending",
                subtotal=Decimal("20.00"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total_price=Decimal("20.00"),
                paid_at=timezone.now() - timedelta(days=3),
            )

        # 2. Run payout job
        mock_transfer.return_value = MagicMock(id="tr_integ123")
        PayoutService.process_restaurant_payout(restaurant)

        # 3. Verify payout created
        payout = Payout.objects.get(restaurant=restaurant)
        assert payout.amount == Decimal("60.00")
        assert payout.orders_count == 3
        assert payout.status == "pending"

        # 4. All orders marked as transferred
        assert Order.objects.filter(
            restaurant=restaurant, payout_status="transferred"
        ).count() == 3

        # 5. Simulate transfer.created webhook
        OrderService._handle_transfer_created(
            {"object": {"id": "tr_integ123"}}
        )
        payout.refresh_from_db()
        assert payout.status == "in_transit"

        # 6. Simulate payout.paid webhook
        OrderService._handle_payout_paid({
            "object": {"id": "po_integ123", "amount": 6000, "currency": "usd"},
            "account": "acct_integ123",
        })
        payout.refresh_from_db()
        assert payout.status == "completed"
        assert payout.stripe_payout_id == "po_integ123"

        # 7. All orders marked as paid_out
        assert Order.objects.filter(
            restaurant=restaurant, payout_status="paid_out"
        ).count() == 3
```

- [ ] **Step 2: Run the integration test**

Run: `cd backend && python -m pytest restaurants/tests/test_payout_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/restaurants/tests/test_payout_integration.py
git commit -m "test: add end-to-end payout flow integration test"
```

---

### Task 17: Payout email notifications

**Files:**
- Create: `backend/restaurants/notifications.py`
- Create: `backend/restaurants/tests/test_notifications.py`

- [ ] **Step 1: Write failing test for payout notifications**

```python
# backend/restaurants/tests/test_notifications.py
import pytest
from decimal import Decimal
from django.core import mail
from restaurants.models import Restaurant, User
from restaurants.notifications import send_payout_completed_email, send_payout_failed_email


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.mark.django_db
class TestPayoutNotifications:
    def test_send_payout_completed_email(self, restaurant):
        send_payout_completed_email(restaurant, Decimal("150.00"))
        assert len(mail.outbox) == 1
        assert "150.00" in mail.outbox[0].body
        assert mail.outbox[0].to == ["owner@test.com"]

    def test_send_payout_failed_email(self, restaurant):
        send_payout_failed_email(restaurant, Decimal("150.00"))
        assert len(mail.outbox) == 1
        assert "failed" in mail.outbox[0].subject.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_notifications.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement notifications**

```python
# backend/restaurants/notifications.py
from django.core.mail import send_mail
from django.conf import settings


def send_payout_completed_email(restaurant, amount):
    send_mail(
        subject=f"Payout of ${amount} deposited — {restaurant.name}",
        message=(
            f"Your daily payout of ${amount} has been deposited to your bank account.\n\n"
            f"View details in your Stripe Dashboard."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurant.owner.email],
        fail_silently=True,
    )


def send_payout_failed_email(restaurant, amount):
    send_mail(
        subject=f"Payout of ${amount} failed — {restaurant.name}",
        message=(
            f"Your payout of ${amount} failed. Please check your bank details "
            f"in the Stripe Dashboard and contact support if the issue persists."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurant.owner.email],
        fail_silently=True,
    )
```

- [ ] **Step 4: Wire notifications into webhook handlers**

In `backend/orders/services.py`, update `_handle_payout_paid` to call:
```python
from restaurants.notifications import send_payout_completed_email
send_payout_completed_email(account.restaurant, payout.amount)
```

And `_handle_payout_failed` / `_handle_transfer_failed` to call:
```python
from restaurants.notifications import send_payout_failed_email
send_payout_failed_email(account.restaurant, payout.amount)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest restaurants/tests/test_notifications.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/notifications.py backend/restaurants/tests/test_notifications.py backend/orders/services.py
git commit -m "feat: add payout email notifications"
```

---

### Task 18: Final verification and cleanup

- [ ] **Step 1: Verify all migrations are clean**

Run: `cd backend && python manage.py showmigrations`
Expected: All migrations applied

- [ ] **Step 2: Run full test suite one final time**

Run: `cd backend && python -m pytest -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Verify docker-compose works**

Run: `docker compose build && docker compose up -d && docker compose ps`
Expected: All services running (including celery-worker and celery-beat)

- [ ] **Step 4: Stop docker services**

Run: `docker compose down`
