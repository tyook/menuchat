# Payment Model (Upfront vs Tab) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow restaurant owners to choose between "pay upfront" (current default) and "open tab" payment models, where tab mode lets customers order multiple times per table and pay once.

**Architecture:** New `Tab` and `TabPayment` models in the orders app group multiple orders per table. A `payment_model` field on `Restaurant` controls which flow is used. Dedicated tab endpoints handle order placement, tab retrieval, closing, and split payments. The existing upfront flow is completely untouched.

**Tech Stack:** Django 5, Django REST Framework, PostgreSQL (partial unique index), Stripe PaymentIntents, Django Channels (WebSocket), Next.js 14, Zustand, React Query, Stripe Elements, TypeScript

**Spec:** `docs/superpowers/specs/2026-04-08-payment-model-design.md`

---

## Chunk 1: Backend Models & Migrations

### Task 1: Add `payment_model` field to Restaurant

**Files:**
- Modify: `backend/restaurants/models.py:7-34` (Restaurant class)
- Test: `backend/restaurants/tests/test_models_payment_model.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/restaurants/tests/test_models_payment_model.py
from decimal import Decimal

import pytest

from restaurants.models import Restaurant
from restaurants.tests.factories import UserFactory


@pytest.mark.django_db
class TestRestaurantPaymentModel:
    def test_default_payment_model_is_upfront(self):
        owner = UserFactory()
        restaurant = Restaurant.objects.create(name="Test", slug="test", owner=owner)
        assert restaurant.payment_model == "upfront"

    def test_can_set_payment_model_to_tab(self):
        owner = UserFactory()
        restaurant = Restaurant.objects.create(
            name="Tab Test", slug="tab-test", owner=owner, payment_model="tab"
        )
        assert restaurant.payment_model == "tab"

    def test_payment_model_choices_are_valid(self):
        owner = UserFactory()
        restaurant = Restaurant.objects.create(name="Test", slug="test-valid", owner=owner)
        restaurant.payment_model = "upfront"
        restaurant.full_clean()
        restaurant.payment_model = "tab"
        restaurant.full_clean()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_models_payment_model.py -v`
Expected: FAIL — `Restaurant` has no field `payment_model`

- [ ] **Step 3: Add `payment_model` field to Restaurant model**

In `backend/restaurants/models.py`, add after `estimated_minutes_per_order` (line 30):

```python
    payment_model = models.CharField(
        max_length=20,
        choices=[("upfront", "Pay Upfront"), ("tab", "Open Tab")],
        default="upfront",
    )
```

- [ ] **Step 4: Generate migration**

Run: `cd backend && python manage.py makemigrations restaurants -n add_payment_model`
Expected: Creates `backend/restaurants/migrations/0016_add_payment_model.py`

- [ ] **Step 5: Run migration and tests**

Run: `cd backend && python manage.py migrate && python -m pytest restaurants/tests/test_models_payment_model.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/0016_add_payment_model.py backend/restaurants/tests/test_models_payment_model.py
git commit -m "feat: add payment_model field to Restaurant"
```

---

### Task 2: Create Tab model

**Files:**
- Modify: `backend/orders/models.py` (add Tab class)
- Test: `backend/orders/tests/test_models_tab.py` (new)
- Create: `backend/orders/tests/factories.py` (add TabFactory)

- [ ] **Step 1: Write the failing test**

```python
# backend/orders/tests/test_models_tab.py
import pytest
from django.db import IntegrityError
from django.utils import timezone

from orders.models import Tab
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestTabModel:
    def test_create_tab(self):
        restaurant = RestaurantFactory()
        tab = Tab.objects.create(
            restaurant=restaurant,
            table_identifier="A3",
        )
        assert tab.status == "open"
        assert tab.table_identifier == "A3"
        assert tab.opened_at is not None
        assert tab.closed_at is None
        assert str(tab.id)

    def test_only_one_open_tab_per_table(self):
        restaurant = RestaurantFactory()
        Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        with pytest.raises(IntegrityError):
            Tab.objects.create(restaurant=restaurant, table_identifier="A3")

    def test_can_open_new_tab_after_closing(self):
        restaurant = RestaurantFactory()
        tab1 = Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        tab1.status = "closed"
        tab1.closed_at = timezone.now()
        tab1.save()
        tab2 = Tab.objects.create(restaurant=restaurant, table_identifier="A3")
        assert tab2.status == "open"
        assert tab2.id != tab1.id

    def test_tab_totals_computed_from_orders(self):
        """Tab totals are @property computed from linked orders — tested in Task 4."""
        restaurant = RestaurantFactory()
        tab = Tab.objects.create(restaurant=restaurant, table_identifier="B1")
        assert tab.subtotal == 0
        assert tab.tax_amount == 0
        assert tab.total == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_models_tab.py -v`
Expected: FAIL — `Tab` does not exist in `orders.models`

- [ ] **Step 3: Create Tab model**

In `backend/orders/models.py`, add `from decimal import Decimal` to imports, then add before the `Order` class:

```python
class Tab(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSING = "closing", "Closing"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="tabs"
    )
    table_identifier = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "table_identifier"],
                condition=models.Q(status="open"),
                name="unique_open_tab_per_table",
            )
        ]

    def __str__(self):
        return f"Tab {self.table_identifier} ({self.status}) - {self.restaurant.name}"

    @property
    def subtotal(self):
        if self.orders.exists():
            return sum(order.subtotal for order in self.orders.all())
        return Decimal("0.00")

    @property
    def tax_amount(self):
        if self.orders.exists():
            return sum(order.tax_amount for order in self.orders.all())
        return Decimal("0.00")

    @property
    def total(self):
        if self.orders.exists():
            return sum(order.total_price for order in self.orders.all())
        return Decimal("0.00")

    @property
    def amount_paid(self):
        if hasattr(self, "payments") and self.payments.exists():
            return sum(p.amount for p in self.payments.filter(payment_status="paid"))
        return Decimal("0.00")

    @property
    def amount_remaining(self):
        return self.total - self.amount_paid
```

- [ ] **Step 4: Add TabFactory**

In `backend/orders/tests/factories.py`, add:

```python
from orders.models import Order, OrderItem, Tab

class TabFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tab

    restaurant = factory.SubFactory(RestaurantFactory)
    table_identifier = factory.Sequence(lambda n: f"T{n}")
```

- [ ] **Step 5: Generate migration**

Run: `cd backend && python manage.py makemigrations orders -n add_tab_model`
Expected: Creates `backend/orders/migrations/0007_add_tab_model.py`

- [ ] **Step 6: Run migration and tests**

Run: `cd backend && python manage.py migrate && python -m pytest orders/tests/test_models_tab.py -v`
Expected: All 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/0007_add_tab_model.py backend/orders/tests/test_models_tab.py backend/orders/tests/factories.py
git commit -m "feat: add Tab model with partial unique constraint"
```

---

### Task 3: Add `tab` FK and `deferred` payment status to Order

**Files:**
- Modify: `backend/orders/models.py:46-56` (payment_status choices), add FK after line 87
- Test: `backend/orders/tests/test_models_tab.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `backend/orders/tests/test_models_tab.py`:

```python
from orders.models import Order, Tab
from orders.tests.factories import OrderFactory, TabFactory


@pytest.mark.django_db
class TestOrderTabRelation:
    def test_order_can_have_tab(self):
        tab = TabFactory()
        order = OrderFactory(restaurant=tab.restaurant, tab=tab)
        assert order.tab == tab
        assert order in tab.orders.all()

    def test_order_tab_is_optional(self):
        order = OrderFactory()
        assert order.tab is None

    def test_deferred_payment_status(self):
        tab = TabFactory()
        order = OrderFactory(
            restaurant=tab.restaurant,
            tab=tab,
            payment_status="deferred",
            status="confirmed",
        )
        order.full_clean()
        assert order.payment_status == "deferred"

    def test_tab_totals_with_orders(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=10, tax_amount=1, total_price=11)
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=20, tax_amount=2, total_price=22)
        assert tab.subtotal == 30
        assert tab.tax_amount == 3
        assert tab.total == 33
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_models_tab.py::TestOrderTabRelation -v`
Expected: FAIL — Order has no `tab` field, `deferred` not a valid choice

- [ ] **Step 3: Add tab FK and deferred status to Order model**

In `backend/orders/models.py`:

1. Add `"deferred"` to payment_status choices (after `"pos_collected"` on line 51):
```python
            ("deferred", "Deferred"),
```

2. Add `tab` FK after `paid_at` field (around line 87):
```python
    tab = models.ForeignKey(
        Tab, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
```

- [ ] **Step 4: Update OrderFactory**

In `backend/orders/tests/factories.py`, add `tab = None` to `OrderFactory`:

```python
class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    restaurant = factory.SubFactory(RestaurantFactory)
    raw_input = "Test order input"
    parsed_json = factory.LazyFunction(dict)
    total_price = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    user = None
    customer_name = ""
    customer_phone = ""
    tab = None
```

- [ ] **Step 5: Generate migration**

Run: `cd backend && python manage.py makemigrations orders -n add_order_tab_fk_and_deferred`
Expected: Creates `backend/orders/migrations/0008_add_order_tab_fk_and_deferred.py`

- [ ] **Step 6: Run migration and tests**

Run: `cd backend && python manage.py migrate && python -m pytest orders/tests/test_models_tab.py -v`
Expected: All 8 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/0008_add_order_tab_fk_and_deferred.py backend/orders/tests/test_models_tab.py backend/orders/tests/factories.py
git commit -m "feat: add tab FK and deferred payment status to Order"
```

---

### Task 4: Create TabPayment model

**Files:**
- Modify: `backend/orders/models.py` (add TabPayment class after Tab)
- Test: `backend/orders/tests/test_models_tab.py` (extend)
- Modify: `backend/orders/tests/factories.py` (add TabPaymentFactory)

- [ ] **Step 1: Write the failing test**

Append to `backend/orders/tests/test_models_tab.py`:

```python
from decimal import Decimal

from orders.models import TabPayment


@pytest.mark.django_db
class TestTabPaymentModel:
    def test_create_full_payment(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=20, tax_amount=2, total_price=22)
        payment = TabPayment.objects.create(
            tab=tab,
            type="full",
            amount=Decimal("22.00"),
            tax_amount=Decimal("2.00"),
        )
        assert payment.payment_status == "pending"
        assert payment.paid_at is None

    def test_create_split_even_payment(self):
        tab = TabFactory()
        payment = TabPayment.objects.create(
            tab=tab,
            type="split_even",
            amount=Decimal("11.00"),
            tax_amount=Decimal("1.00"),
            split_count=2,
        )
        assert payment.type == "split_even"
        assert payment.split_count == 2

    def test_tab_amount_paid_tracks_payments(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=40, tax_amount=4, total_price=44)
        TabPayment.objects.create(
            tab=tab, type="split_even", amount=Decimal("22.00"),
            tax_amount=Decimal("2.00"), payment_status="paid",
        )
        assert tab.amount_paid == Decimal("22.00")
        assert tab.amount_remaining == Decimal("22.00")

    def test_tab_fully_paid(self):
        tab = TabFactory()
        OrderFactory(restaurant=tab.restaurant, tab=tab, subtotal=20, tax_amount=2, total_price=22)
        TabPayment.objects.create(
            tab=tab, type="full", amount=Decimal("22.00"),
            tax_amount=Decimal("2.00"), payment_status="paid",
        )
        assert tab.amount_remaining == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_models_tab.py::TestTabPaymentModel -v`
Expected: FAIL — `TabPayment` does not exist

- [ ] **Step 3: Create TabPayment model**

In `backend/orders/models.py`, add after the `Tab` class:

```python
class TabPayment(models.Model):
    class Type(models.TextChoices):
        FULL = "full", "Full"
        SPLIT_EVEN = "split_even", "Split Even"
        PAY_BY_ITEM = "pay_by_item", "Pay By Item"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tab = models.ForeignKey(Tab, on_delete=models.CASCADE, related_name="payments")
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    items = models.ManyToManyField("OrderItem", blank=True, related_name="tab_payments")
    split_count = models.PositiveIntegerField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TabPayment {self.type} ${self.amount} ({self.payment_status})"
```

- [ ] **Step 4: Add TabPaymentFactory**

In `backend/orders/tests/factories.py`, add:

```python
from orders.models import Order, OrderItem, Tab, TabPayment

class TabPaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TabPayment

    tab = factory.SubFactory(TabFactory)
    type = "full"
    amount = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
    tax_amount = factory.Faker("pydecimal", left_digits=1, right_digits=2, positive=True)
```

- [ ] **Step 5: Generate migration**

Run: `cd backend && python manage.py makemigrations orders -n add_tab_payment_model`
Expected: Creates `backend/orders/migrations/0009_add_tab_payment_model.py`

- [ ] **Step 6: Run migration and ALL model tests**

Run: `cd backend && python manage.py migrate && python -m pytest orders/tests/test_models_tab.py -v`
Expected: All 12 tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/0009_add_tab_payment_model.py backend/orders/tests/test_models_tab.py backend/orders/tests/factories.py
git commit -m "feat: add TabPayment model with split payment support"
```

---

## Chunk 2: Backend Service Layer & Tab Endpoints

### Task 5: Add `get_payment_config` helper and Tab service methods

**Files:**
- Create: `backend/orders/tab_service.py`
- Test: `backend/orders/tests/test_tab_service.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/orders/tests/test_tab_service.py
from decimal import Decimal
from unittest.mock import patch

import pytest

from orders.models import Tab
from orders.tab_service import TabService
from orders.tests.factories import OrderFactory, TabFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestGetPaymentConfig:
    def test_default_config_no_pos(self):
        restaurant = RestaurantFactory()
        config = TabService.get_payment_config(restaurant)
        assert config == {"payment_mode": "stripe", "payment_model": "upfront"}

    def test_tab_mode_no_pos(self):
        restaurant = RestaurantFactory(payment_model="tab")
        config = TabService.get_payment_config(restaurant)
        assert config == {"payment_mode": "stripe", "payment_model": "tab"}

    @patch("orders.tab_service.POSConnection")
    def test_pos_collected_with_tab(self, mock_pos_cls):
        restaurant = RestaurantFactory(payment_model="tab")
        mock_pos_cls.objects.get.return_value = type("POSConn", (), {"payment_mode": "pos_collected"})()
        config = TabService.get_payment_config(restaurant)
        assert config == {"payment_mode": "pos_collected", "payment_model": "tab"}


@pytest.mark.django_db
class TestGetOrCreateTab:
    def test_creates_new_tab(self):
        restaurant = RestaurantFactory()
        tab = TabService.get_or_create_tab(restaurant, "A3")
        assert tab.table_identifier == "A3"
        assert tab.status == "open"
        assert Tab.objects.count() == 1

    def test_returns_existing_open_tab(self):
        restaurant = RestaurantFactory()
        tab1 = TabService.get_or_create_tab(restaurant, "A3")
        tab2 = TabService.get_or_create_tab(restaurant, "A3")
        assert tab1.id == tab2.id
        assert Tab.objects.count() == 1

    def test_different_tables_get_different_tabs(self):
        restaurant = RestaurantFactory()
        tab1 = TabService.get_or_create_tab(restaurant, "A3")
        tab2 = TabService.get_or_create_tab(restaurant, "B1")
        assert tab1.id != tab2.id

    def test_rejects_order_on_closing_tab(self):
        tab = TabFactory(status="closing")
        with pytest.raises(ValueError, match="closing"):
            TabService.get_or_create_tab(tab.restaurant, tab.table_identifier)


@pytest.mark.django_db
class TestCloseTab:
    def test_close_tab_sets_status_to_closing(self):
        tab = TabFactory()
        TabService.close_tab(tab)
        tab.refresh_from_db()
        assert tab.status == "closing"

    def test_close_already_closing_tab_is_noop(self):
        tab = TabFactory(status="closing")
        TabService.close_tab(tab)
        tab.refresh_from_db()
        assert tab.status == "closing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_tab_service.py -v`
Expected: FAIL — `orders.tab_service` does not exist

- [ ] **Step 3: Create TabService**

```python
# backend/orders/tab_service.py
from django.db import transaction
from django.utils import timezone

from integrations.models import POSConnection
from orders.models import Tab, TabPayment


class TabService:
    @staticmethod
    def get_payment_config(restaurant):
        """Resolve both payment_mode and payment_model for a restaurant."""
        try:
            pos = POSConnection.objects.get(restaurant=restaurant, is_active=True)
            payment_mode = pos.payment_mode
        except POSConnection.DoesNotExist:
            payment_mode = "stripe"
        return {
            "payment_mode": payment_mode,
            "payment_model": restaurant.payment_model,
        }

    @staticmethod
    def get_or_create_tab(restaurant, table_identifier):
        """Get the open tab for a table, or create one. Raises ValueError if tab is closing."""
        with transaction.atomic():
            existing = (
                Tab.objects.select_for_update()
                .filter(
                    restaurant=restaurant,
                    table_identifier=table_identifier,
                    status__in=["open", "closing"],
                )
                .first()
            )
            if existing:
                if existing.status == "closing":
                    raise ValueError("Tab is closing — no new orders allowed")
                return existing
            return Tab.objects.create(
                restaurant=restaurant,
                table_identifier=table_identifier,
            )

    @staticmethod
    def get_open_tab(restaurant, table_identifier):
        """Get the open or closing tab for a table, or None."""
        return Tab.objects.filter(
            restaurant=restaurant,
            table_identifier=table_identifier,
            status__in=["open", "closing"],
        ).first()

    @staticmethod
    def close_tab(tab):
        """Initiate closing a tab."""
        if tab.status == "open":
            tab.status = "closing"
            tab.save(update_fields=["status"])

    @staticmethod
    def finalize_tab(tab):
        """Close a tab after all payments are collected."""
        tab.status = "closed"
        tab.closed_at = timezone.now()
        tab.save(update_fields=["status", "closed_at"])
        tab.orders.filter(payment_status="deferred").update(
            payment_status="paid",
            paid_at=timezone.now(),
        )

    @staticmethod
    def force_close_unpaid(tab):
        """Staff force-closes a tab without payment."""
        tab.status = "closed"
        tab.closed_at = timezone.now()
        tab.save(update_fields=["status", "closed_at"])
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest orders/tests/test_tab_service.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/tab_service.py backend/orders/tests/test_tab_service.py
git commit -m "feat: add TabService with get_payment_config and tab lifecycle"
```

---

### Task 6: Tab serializers

**Files:**
- Modify: `backend/orders/serializers.py` (add tab serializers)
- Test: `backend/orders/tests/test_serializers_tab.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/orders/tests/test_serializers_tab.py
from decimal import Decimal

import pytest

from orders.serializers import TabOrderSerializer, TabResponseSerializer, TabPaymentRequestSerializer
from orders.tests.factories import OrderFactory, TabFactory, TabPaymentFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
)


@pytest.mark.django_db
class TestTabResponseSerializer:
    def test_serializes_tab_with_orders(self):
        tab = TabFactory()
        version = MenuVersionFactory(restaurant=tab.restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        OrderFactory(
            restaurant=tab.restaurant, tab=tab,
            subtotal=Decimal("10.00"), tax_amount=Decimal("0.89"), total_price=Decimal("10.89"),
        )
        data = TabResponseSerializer(tab).data
        assert data["table_identifier"] == tab.table_identifier
        assert data["status"] == "open"
        assert len(data["orders"]) == 1
        assert data["subtotal"] == "10.00"
        assert data["total"] == "10.89"
        assert data["amount_paid"] == "0.00"
        assert data["amount_remaining"] == "10.89"


@pytest.mark.django_db
class TestTabPaymentRequestSerializer:
    def test_valid_full_payment(self):
        tab = TabFactory()
        serializer = TabPaymentRequestSerializer(data={
            "tab_id": str(tab.id),
            "type": "full",
        })
        assert serializer.is_valid(), serializer.errors

    def test_split_even_requires_split_count(self):
        tab = TabFactory()
        serializer = TabPaymentRequestSerializer(data={
            "tab_id": str(tab.id),
            "type": "split_even",
        })
        assert not serializer.is_valid()
        assert "split_count" in serializer.errors

    def test_pay_by_item_requires_item_ids(self):
        tab = TabFactory()
        serializer = TabPaymentRequestSerializer(data={
            "tab_id": str(tab.id),
            "type": "pay_by_item",
        })
        assert not serializer.is_valid()
        assert "item_ids" in serializer.errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_serializers_tab.py -v`
Expected: FAIL — serializers don't exist

- [ ] **Step 3: Create tab serializers**

First, add a `line_total` field to the existing `OrderItemResponseSerializer` in `backend/orders/serializers.py`. This computed field is needed by the tab UI to display item-level prices:

```python
# In OrderItemResponseSerializer, add:
line_total = serializers.SerializerMethodField()

def get_line_total(self, obj):
    base = obj.variant.price * obj.quantity
    modifier_total = sum(m.price_adjustment for m in obj.modifiers.all()) * obj.quantity
    return f"{base + modifier_total:.2f}"
```

Then add the new tab serializers:

```python
from orders.models import Tab, TabPayment


class TabOrderSerializer(serializers.Serializer):
    """Lightweight order representation for tab view."""
    id = serializers.UUIDField()
    status = serializers.CharField()
    items = OrderItemResponseSerializer(many=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    created_at = serializers.DateTimeField()


class TabResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    table_identifier = serializers.CharField()
    status = serializers.CharField()
    orders = TabOrderSerializer(many=True)
    subtotal = serializers.SerializerMethodField()
    tax_amount = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()
    opened_at = serializers.DateTimeField()

    def get_subtotal(self, tab):
        return f"{tab.subtotal:.2f}"

    def get_tax_amount(self, tab):
        return f"{tab.tax_amount:.2f}"

    def get_total(self, tab):
        return f"{tab.total:.2f}"

    def get_amount_paid(self, tab):
        return f"{tab.amount_paid:.2f}"

    def get_amount_remaining(self, tab):
        return f"{tab.amount_remaining:.2f}"


class TabPaymentRequestSerializer(serializers.Serializer):
    tab_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=TabPayment.Type.choices)
    split_count = serializers.IntegerField(required=False, min_value=2)
    item_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, data):
        if data["type"] == "split_even" and not data.get("split_count"):
            raise serializers.ValidationError({"split_count": "Required for split_even."})
        if data["type"] == "pay_by_item" and not data.get("item_ids"):
            raise serializers.ValidationError({"item_ids": "Required for pay_by_item."})
        return data
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest orders/tests/test_serializers_tab.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/serializers.py backend/orders/tests/test_serializers_tab.py
git commit -m "feat: add tab serializers for API responses and payment requests"
```

---

### Task 7: Tab API views — GET tab, POST tab/order, POST tab/close

**Files:**
- Create: `backend/orders/tab_views.py`
- Modify: `backend/orders/urls.py` (add tab URL patterns)
- Test: `backend/orders/tests/test_api_tab.py` (new)

Note: the `api_client` fixture is provided by `backend/conftest.py` (project-wide).

- [ ] **Step 1: Write the failing tests**

```python
# backend/orders/tests/test_api_tab.py
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from orders.models import Order, Tab
from orders.tests.factories import OrderFactory, TabFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
    RestaurantStaffFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestGetTab:
    def test_get_open_tab(self):
        restaurant = RestaurantFactory(slug="tab-get-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3")
        OrderFactory(
            restaurant=restaurant, tab=tab,
            subtotal=Decimal("10.00"), tax_amount=Decimal("0.89"),
            total_price=Decimal("10.89"), status="confirmed",
        )
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get("/api/order/tab-get-test/tab/", {"table": "A3"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["table_identifier"] == "A3"
        assert response.data["status"] == "open"
        assert len(response.data["orders"]) == 1
        assert response.data["total"] == "10.89"

    def test_get_tab_no_tab_returns_404(self):
        RestaurantFactory(slug="tab-get-empty", payment_model="tab")
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get("/api/order/tab-get-empty/tab/", {"table": "A3"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_tab_requires_table_param(self):
        RestaurantFactory(slug="tab-get-no-table", payment_model="tab")
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get("/api/order/tab-get-no-table/tab/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTabOrder:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="tab-order-test", payment_model="tab")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular",
            price=Decimal("10.00"), is_default=True,
        )
        return {"restaurant": restaurant, "item": item, "variant": variant}

    def test_place_order_on_tab(self, api_client, menu_setup):
        response = api_client.post(
            "/api/order/tab-order-test/tab/order/",
            {
                "items": [{
                    "menu_item_id": menu_setup["item"].id,
                    "variant_id": menu_setup["variant"].id,
                    "quantity": 1,
                }],
                "raw_input": "One burger",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "confirmed"
        assert response.data["payment_status"] == "deferred"
        assert "tab" in response.data

        # Verify tab was created
        tab = Tab.objects.get(id=response.data["tab"]["id"])
        assert tab.table_identifier == "A3"
        assert tab.orders.count() == 1

    def test_second_order_uses_same_tab(self, api_client, menu_setup):
        payload = {
            "items": [{
                "menu_item_id": menu_setup["item"].id,
                "variant_id": menu_setup["variant"].id,
                "quantity": 1,
            }],
            "raw_input": "One burger",
            "table_identifier": "A3",
            "language": "en",
        }
        r1 = api_client.post("/api/order/tab-order-test/tab/order/", payload, format="json")
        r2 = api_client.post("/api/order/tab-order-test/tab/order/", payload, format="json")
        assert r1.data["tab"]["id"] == r2.data["tab"]["id"]
        tab = Tab.objects.get(id=r1.data["tab"]["id"])
        assert tab.orders.count() == 2

    def test_tab_order_rejected_for_upfront_restaurant(self, api_client):
        restaurant = RestaurantFactory(slug="upfront-test", payment_model="upfront")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price=Decimal("10.00"))
        response = api_client.post(
            "/api/order/upfront-test/tab/order/",
            {
                "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
                "raw_input": "test",
                "table_identifier": "A1",
                "language": "en",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTabClose:
    def test_customer_can_close_tab(self, api_client):
        restaurant = RestaurantFactory(slug="tab-close-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3")
        response = api_client.post(
            "/api/order/tab-close-test/tab/close/",
            {"table_identifier": "A3"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        tab.refresh_from_db()
        assert tab.status == "closing"

    def test_staff_can_close_tab(self, api_client):
        restaurant = RestaurantFactory(slug="tab-staff-close")
        staff_user = UserFactory()
        RestaurantStaffFactory(user=staff_user, restaurant=restaurant, role="manager")
        tab = TabFactory(restaurant=restaurant, table_identifier="B1")
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(f"/api/kitchen/tab/{tab.id}/close/")
        assert response.status_code == status.HTTP_200_OK
        tab.refresh_from_db()
        assert tab.status == "closing"

    def test_non_staff_cannot_use_kitchen_close(self, api_client):
        restaurant = RestaurantFactory(slug="tab-nostaff-close")
        tab = TabFactory(restaurant=restaurant)
        outsider = UserFactory()
        api_client.force_authenticate(user=outsider)
        response = api_client.post(f"/api/kitchen/tab/{tab.id}/close/")
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest orders/tests/test_api_tab.py -v`
Expected: FAIL — views and URLs don't exist

- [ ] **Step 3: Create tab views**

```python
# backend/orders/tab_views.py
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Tab
from orders.serializers import (
    ConfirmOrderSerializer,
    OrderResponseSerializer,
    TabResponseSerializer,
)
from orders.services import OrderService
from orders.tab_service import TabService
from restaurants.models import Restaurant, RestaurantStaff


class TabDetailView(APIView):
    """GET /api/order/{slug}/tab/?table={id}"""
    permission_classes = [AllowAny]

    def get(self, request, slug):
        table = request.query_params.get("table")
        if not table:
            return Response(
                {"error": "table query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)

        tab = TabService.get_open_tab(restaurant, table)
        if not tab:
            return Response(
                {"error": "No open tab for this table"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TabResponseSerializer(tab).data)


class TabOrderView(APIView):
    """POST /api/order/{slug}/tab/order/ — place an order on a tab"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if restaurant.payment_model != "tab":
            return Response(
                {"error": "This restaurant does not use tab mode"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ConfirmOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        table_identifier = data.get("table_identifier", "")
        if not table_identifier:
            return Response(
                {"error": "table_identifier is required for tab orders"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tab = TabService.get_or_create_tab(restaurant, table_identifier)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Validate and price items (reuse existing service)
        # Note: signature is validate_and_price_items(restaurant, items_data) -> (validated_items, pricing)
        validated_items, pricing = OrderService.validate_and_price_items(restaurant, data["items"])
        if not validated_items:
            return Response(
                {"error": "No valid items in order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = OrderService.resolve_user_from_request(request)

        order = OrderService.create_order(
            restaurant,
            validated_items,
            pricing,
            user=user,
            order_status="confirmed",
            payment_status="deferred",
            raw_input=data.get("raw_input", ""),
            language=data.get("language", ""),
            table_identifier=table_identifier,
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            customer_allergies=data.get("allergies", []),
            tab=tab,
        )

        response_data = OrderResponseSerializer(order).data
        response_data["tab"] = TabResponseSerializer(tab).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class TabCloseView(APIView):
    """POST /api/order/{slug}/tab/close/ — customer initiates tab close"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)

        table_identifier = request.data.get("table_identifier")
        if not table_identifier:
            return Response(
                {"error": "table_identifier is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tab = TabService.get_open_tab(restaurant, table_identifier)
        if not tab:
            return Response(
                {"error": "No open tab for this table"},
                status=status.HTTP_404_NOT_FOUND,
            )

        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)


class KitchenTabCloseView(APIView):
    """POST /api/kitchen/tab/{tab_id}/close/ — staff initiates tab close"""
    permission_classes = [IsAuthenticated]

    def post(self, request, tab_id):
        try:
            tab = Tab.objects.select_related("restaurant").get(id=tab_id)
        except Tab.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        user = request.user
        restaurant = tab.restaurant
        is_staff = (
            restaurant.owner == user
            or RestaurantStaff.objects.filter(user=user, restaurant=restaurant).exists()
        )
        if not is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)
```

- [ ] **Step 4: Add URL patterns**

In `backend/orders/urls.py`, add the imports and paths:

```python
from orders.tab_views import (
    KitchenTabCloseView,
    TabCloseView,
    TabDetailView,
    TabOrderView,
)
```

Add to `urlpatterns`:
```python
    path("order/<slug:slug>/tab/", TabDetailView.as_view(), name="tab-detail"),
    path("order/<slug:slug>/tab/order/", TabOrderView.as_view(), name="tab-order"),
    path("order/<slug:slug>/tab/close/", TabCloseView.as_view(), name="tab-close"),
    path("kitchen/tab/<uuid:tab_id>/close/", KitchenTabCloseView.as_view(), name="kitchen-tab-close"),
```

- [ ] **Step 5: Update OrderService.create_order to accept `tab` parameter**

In `backend/orders/services.py`, find the `create_order` method and add `tab=None` to its parameters. When creating the Order, pass `tab=tab`. This is a small modification — find the method signature and the `Order.objects.create()` call and add the `tab` field.

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest orders/tests/test_api_tab.py -v`
Expected: All 8 tests PASS

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `cd backend && python -m pytest -v`
Expected: All existing tests still PASS

- [ ] **Step 8: Commit**

```bash
git add backend/orders/tab_views.py backend/orders/urls.py backend/orders/services.py backend/orders/tests/test_api_tab.py
git commit -m "feat: add tab API views for order placement, retrieval, and closing"
```

---

### Task 8: Tab payment endpoints and Stripe integration

**Files:**
- Create: `backend/orders/tab_payment_service.py`
- Modify: `backend/orders/tab_views.py` (add payment views)
- Modify: `backend/orders/urls.py` (add payment URLs)
- Test: `backend/orders/tests/test_api_tab_payment.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# backend/orders/tests/test_api_tab_payment.py
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from orders.models import Tab, TabPayment
from orders.tests.factories import OrderFactory, TabFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestTabPayFull:
    @patch("orders.tab_payment_service.stripe")
    def test_create_full_tab_payment(self, mock_stripe, api_client):
        restaurant = RestaurantFactory(slug="tab-pay-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        OrderFactory(
            restaurant=restaurant, tab=tab,
            subtotal=Decimal("20.00"), tax_amount=Decimal("1.78"),
            total_price=Decimal("21.78"), status="confirmed", payment_status="deferred",
        )
        mock_intent = MagicMock()
        mock_intent.id = "pi_tab_123"
        mock_intent.client_secret = "pi_tab_123_secret"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        response = api_client.post(
            "/api/order/tab-pay-test/tab/pay/",
            {"tab_id": str(tab.id), "type": "full"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["client_secret"] == "pi_tab_123_secret"
        assert response.data["payment_id"]

        payment = TabPayment.objects.get(id=response.data["payment_id"])
        assert payment.amount == Decimal("21.78")
        assert payment.stripe_payment_intent_id == "pi_tab_123"


@pytest.mark.django_db
class TestTabPaySplitEven:
    @patch("orders.tab_payment_service.stripe")
    def test_create_split_even_payment(self, mock_stripe, api_client):
        restaurant = RestaurantFactory(slug="tab-split-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        OrderFactory(
            restaurant=restaurant, tab=tab,
            subtotal=Decimal("40.00"), tax_amount=Decimal("3.55"),
            total_price=Decimal("43.55"), status="confirmed", payment_status="deferred",
        )
        mock_intent = MagicMock()
        mock_intent.id = "pi_split_1"
        mock_intent.client_secret = "pi_split_1_secret"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        response = api_client.post(
            "/api/order/tab-split-test/tab/pay/",
            {"tab_id": str(tab.id), "type": "split_even", "split_count": 2},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        payment = TabPayment.objects.get(id=response.data["payment_id"])
        # 43.55 / 2 = 21.775 -> 21.78 (first payer)
        assert payment.amount == Decimal("21.78")
        assert payment.split_count == 2


@pytest.mark.django_db
class TestTabPayRejectsOpenTab:
    def test_cannot_pay_open_tab(self, api_client):
        restaurant = RestaurantFactory(slug="tab-pay-open", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3")  # status=open
        response = api_client.post(
            "/api/order/tab-pay-open/tab/pay/",
            {"tab_id": str(tab.id), "type": "full"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTabConfirmPayment:
    @patch("orders.tab_payment_service.stripe")
    def test_confirm_tab_payment(self, mock_stripe, api_client):
        restaurant = RestaurantFactory(slug="tab-confirm-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        OrderFactory(
            restaurant=restaurant, tab=tab,
            subtotal=Decimal("20.00"), tax_amount=Decimal("1.78"),
            total_price=Decimal("21.78"), status="confirmed", payment_status="deferred",
        )
        payment = TabPayment.objects.create(
            tab=tab, type="full", amount=Decimal("21.78"), tax_amount=Decimal("1.78"),
            stripe_payment_intent_id="pi_tab_confirm",
        )
        mock_intent = MagicMock()
        mock_intent.status = "succeeded"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent

        response = api_client.post(
            f"/api/order/tab-confirm-test/tab/confirm-payment/{payment.id}/",
        )
        assert response.status_code == status.HTTP_200_OK

        payment.refresh_from_db()
        assert payment.payment_status == "paid"
        assert payment.paid_at is not None

        # Tab should be fully paid and closed
        tab.refresh_from_db()
        assert tab.status == "closed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest orders/tests/test_api_tab_payment.py -v`
Expected: FAIL — payment service and views don't exist

- [ ] **Step 3: Create tab payment service**

```python
# backend/orders/tab_payment_service.py
import math
from decimal import ROUND_HALF_UP, Decimal

import stripe
from django.conf import settings
from django.utils import timezone

from orders.models import Tab, TabPayment
from orders.tab_service import TabService


class TabPaymentService:
    @staticmethod
    def create_payment(tab, payment_type, split_count=None, item_ids=None, user=None):
        """Create a TabPayment and Stripe PaymentIntent."""
        if tab.status != "closing":
            raise ValueError("Tab must be in 'closing' status to accept payments")

        amount = TabPaymentService._calculate_amount(tab, payment_type, split_count, item_ids)
        tax_portion = TabPaymentService._calculate_tax_portion(tab, amount)

        payment = TabPayment.objects.create(
            tab=tab,
            type=payment_type,
            amount=amount,
            tax_amount=tax_portion,
            split_count=split_count,
        )

        if item_ids:
            from orders.models import OrderItem
            payment.items.set(OrderItem.objects.filter(id__in=item_ids))

        # Create Stripe PaymentIntent
        stripe.api_key = settings.STRIPE_SECRET_KEY
        restaurant = tab.restaurant
        intent_params = {
            "amount": int(amount * 100),
            "currency": restaurant.currency.lower(),
            "automatic_payment_methods": {"enabled": True},
            "metadata": {
                "tab_id": str(tab.id),
                "tab_payment_id": str(payment.id),
                "restaurant_id": str(restaurant.id),
            },
        }

        # Use connected account if available
        from restaurants.models import ConnectedAccount
        try:
            connected = ConnectedAccount.objects.get(
                restaurant=restaurant, onboarding_complete=True
            )
            intent_params["transfer_data"] = {"destination": connected.stripe_account_id}
        except ConnectedAccount.DoesNotExist:
            pass

        intent = stripe.PaymentIntent.create(**intent_params)
        payment.stripe_payment_intent_id = intent.id
        payment.save(update_fields=["stripe_payment_intent_id"])

        return payment, intent.client_secret

    @staticmethod
    def confirm_payment(payment):
        """Verify payment with Stripe and finalize."""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)

        if intent.status == "succeeded":
            payment.payment_status = "paid"
            payment.paid_at = timezone.now()
            payment.save(update_fields=["payment_status", "paid_at"])

            # Check if tab is fully paid
            tab = payment.tab
            if tab.amount_remaining <= 0:
                TabService.finalize_tab(tab)
            return True

        if intent.status in ("canceled", "requires_payment_method"):
            payment.payment_status = "failed"
            payment.save(update_fields=["payment_status"])

        return False

    @staticmethod
    def _calculate_amount(tab, payment_type, split_count=None, item_ids=None):
        remaining = tab.amount_remaining
        if payment_type == "full":
            return remaining
        elif payment_type == "split_even":
            # Calculate this person's share
            existing_paid = tab.payments.filter(
                type="split_even", split_count=split_count
            ).exclude(payment_status="failed").count()
            is_last = (existing_paid + 1) == split_count
            if is_last:
                # Last payer covers remainder
                return remaining
            per_person = (tab.total / split_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return per_person
        elif payment_type == "pay_by_item":
            from orders.models import OrderItem
            items = OrderItem.objects.filter(id__in=item_ids)
            item_total = sum(
                (i.variant.price + sum(m.price_adjustment for m in i.modifiers.all())) * i.quantity
                for i in items
            )
            # Add proportional tax
            if tab.subtotal > 0:
                tax_ratio = tab.tax_amount / tab.subtotal
                tax = (item_total * tax_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                return item_total + tax
            return item_total
        raise ValueError(f"Unknown payment type: {payment_type}")

    @staticmethod
    def _calculate_tax_portion(tab, amount):
        if tab.total > 0:
            ratio = tab.tax_amount / tab.total
            return (amount * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")
```

- [ ] **Step 4: Add payment views to tab_views.py**

Append to `backend/orders/tab_views.py`:

```python
from orders.serializers import TabPaymentRequestSerializer
from orders.tab_payment_service import TabPaymentService


class TabPayView(APIView):
    """POST /api/order/{slug}/tab/pay/ — create a tab payment"""
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = Restaurant.objects.filter(slug=slug).first()
        if not restaurant:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TabPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            tab = Tab.objects.get(id=data["tab_id"], restaurant=restaurant)
        except Tab.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            payment, client_secret = TabPaymentService.create_payment(
                tab=tab,
                payment_type=data["type"],
                split_count=data.get("split_count"),
                item_ids=data.get("item_ids"),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"payment_id": str(payment.id), "client_secret": client_secret},
            status=status.HTTP_201_CREATED,
        )


class TabConfirmPaymentView(APIView):
    """POST /api/order/{slug}/tab/confirm-payment/{payment_id}/"""
    permission_classes = [AllowAny]

    def post(self, request, slug, payment_id):
        from orders.models import TabPayment

        try:
            payment = TabPayment.objects.select_related("tab", "tab__restaurant").get(
                id=payment_id, tab__restaurant__slug=slug,
            )
        except TabPayment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        succeeded = TabPaymentService.confirm_payment(payment)
        if succeeded:
            return Response(TabResponseSerializer(payment.tab).data)
        return Response(
            {"error": "Payment not yet confirmed", "payment_status": payment.payment_status},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )
```

- [ ] **Step 5: Add payment URL patterns**

In `backend/orders/urls.py`, add imports and paths:

```python
from orders.tab_views import (
    KitchenTabCloseView,
    TabCloseView,
    TabConfirmPaymentView,
    TabDetailView,
    TabOrderView,
    TabPayView,
)
```

Add to `urlpatterns`:
```python
    path("order/<slug:slug>/tab/pay/", TabPayView.as_view(), name="tab-pay"),
    path(
        "order/<slug:slug>/tab/confirm-payment/<uuid:payment_id>/",
        TabConfirmPaymentView.as_view(),
        name="tab-confirm-payment",
    ),
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest orders/tests/test_api_tab_payment.py -v`
Expected: All 4 tests PASS

- [ ] **Step 7: Run full test suite**

Run: `cd backend && python -m pytest -v`
Expected: No regressions

- [ ] **Step 8: Commit**

```bash
git add backend/orders/tab_payment_service.py backend/orders/tab_views.py backend/orders/urls.py backend/orders/tests/test_api_tab_payment.py
git commit -m "feat: add tab payment endpoints with Stripe integration and split support"
```

---

### Task 9: Webhook handling for tab payments

**Files:**
- Modify: `backend/orders/services.py:543-572` (webhook dispatch + tab handler)
- Test: `backend/orders/tests/test_api_tab.py` (extend with webhook test)

- [ ] **Step 1: Write the failing test**

Add to `backend/orders/tests/test_api_tab_payment.py`:

```python
@pytest.mark.django_db
class TestTabPaymentWebhook:
    @patch("orders.services.stripe.Webhook.construct_event")
    def test_tab_payment_succeeded_webhook(self, mock_construct, api_client):
        restaurant = RestaurantFactory(slug="tab-webhook-test")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        order = OrderFactory(
            restaurant=restaurant, tab=tab,
            subtotal=Decimal("20.00"), tax_amount=Decimal("1.78"),
            total_price=Decimal("21.78"), status="confirmed", payment_status="deferred",
        )
        payment = TabPayment.objects.create(
            tab=tab, type="full", amount=Decimal("21.78"), tax_amount=Decimal("1.78"),
            stripe_payment_intent_id="pi_tab_webhook_test", payment_status="pending",
        )

        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_tab_webhook_test"}},
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        payment.refresh_from_db()
        assert payment.payment_status == "paid"

        tab.refresh_from_db()
        assert tab.status == "closed"

        order.refresh_from_db()
        assert order.payment_status == "paid"
        assert order.paid_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_api_tab_payment.py::TestTabPaymentWebhook -v`
Expected: FAIL — webhook doesn't know about TabPayment

- [ ] **Step 3: Update webhook handler**

In `backend/orders/services.py`, modify `_handle_payment_succeeded` (around line 543):

```python
    @staticmethod
    def _handle_payment_succeeded(intent):
        from orders.models import TabPayment

        # Try Order first (existing behavior)
        try:
            order = Order.objects.get(stripe_payment_intent_id=intent["id"])
            # ... existing order payment logic unchanged ...
        except Order.DoesNotExist:
            pass
        else:
            return

        # Try TabPayment
        try:
            tab_payment = TabPayment.objects.select_related("tab").get(
                stripe_payment_intent_id=intent["id"]
            )
        except TabPayment.DoesNotExist:
            return

        from orders.tab_payment_service import TabPaymentService
        tab_payment.payment_status = "paid"
        tab_payment.paid_at = timezone.now()
        tab_payment.save(update_fields=["payment_status", "paid_at"])

        tab = tab_payment.tab
        if tab.amount_remaining <= 0:
            TabService.finalize_tab(tab)
```

Add the import at top of services.py:
```python
from orders.tab_service import TabService
```

Also add a similar fallthrough in `_handle_payment_failed`:

```python
    @staticmethod
    def _handle_payment_failed(intent):
        from orders.models import TabPayment

        try:
            order = Order.objects.get(stripe_payment_intent_id=intent["id"])
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
        except Order.DoesNotExist:
            try:
                tab_payment = TabPayment.objects.get(stripe_payment_intent_id=intent["id"])
                tab_payment.payment_status = "failed"
                tab_payment.save(update_fields=["payment_status"])
            except TabPayment.DoesNotExist:
                pass
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest orders/tests/test_api_tab_payment.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run full test suite (check webhook regressions)**

Run: `cd backend && python -m pytest orders/tests/test_api_orders.py::TestStripeWebhook -v`
Expected: All existing webhook tests still PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orders/services.py backend/orders/tests/test_api_tab_payment.py
git commit -m "feat: add tab payment webhook handling with Order/TabPayment fallthrough"
```

---

### Task 10: Update PublicMenuView to include `payment_model`

**Files:**
- Modify: `backend/orders/views.py` (PublicMenuView response)
- Modify: `backend/orders/tests/test_api_menu_public.py` (add test)

- [ ] **Step 1: Write the failing test**

Add to `backend/orders/tests/test_api_menu_public.py`:

```python
@pytest.mark.django_db
class TestPublicMenuPaymentModel:
    def test_menu_includes_payment_model(self, api_client):
        restaurant = RestaurantFactory(slug="menu-pm-test", payment_model="tab")
        MenuVersionFactory(restaurant=restaurant, is_active=True)
        response = api_client.get("/api/order/menu-pm-test/menu/")
        assert response.status_code == 200
        assert response.data["payment_model"] == "tab"

    def test_menu_default_payment_model_is_upfront(self, api_client):
        restaurant = RestaurantFactory(slug="menu-pm-default")
        MenuVersionFactory(restaurant=restaurant, is_active=True)
        response = api_client.get("/api/order/menu-pm-default/menu/")
        assert response.status_code == 200
        assert response.data["payment_model"] == "upfront"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest orders/tests/test_api_menu_public.py::TestPublicMenuPaymentModel -v`
Expected: FAIL — `payment_model` not in response

- [ ] **Step 3: Add `payment_model` to public menu response**

The `PublicMenuView` delegates to `OrderService.get_public_menu(slug)` which builds the response dict. In `backend/orders/services.py`, find the `get_public_menu` method's return dict (around line 808) and add `payment_model` alongside `payment_mode`:

```python
return {
    "restaurant_name": restaurant.name,
    "tax_rate": str(restaurant.tax_rate),
    "categories": PublicMenuCategorySerializer(categories, many=True).data,
    "payment_mode": payment_mode,
    "payment_model": restaurant.payment_model,  # ADD THIS LINE
}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest orders/tests/test_api_menu_public.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/views.py backend/orders/tests/test_api_menu_public.py
git commit -m "feat: include payment_model in public menu response"
```

---

## Chunk 3: Frontend — Types, Store, and API

### Task 11: Update TypeScript types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add tab types**

Add to `frontend/src/types/index.ts`:

```typescript
// After PublicMenu interface (~line 93)
export interface PublicMenu {
  restaurant_name: string;
  tax_rate: string;
  payment_mode: "stripe" | "pos_collected";
  payment_model: "upfront" | "tab";  // ADD THIS LINE
  categories: MenuCategory[];
}

// Add new interfaces at end of file:
export interface TabOrder {
  id: string;
  status: string;
  items: OrderItem[];
  subtotal: string;
  tax_amount: string;
  total_price: string;
  created_at: string;
}

export interface TabResponse {
  id: string;
  table_identifier: string;
  status: "open" | "closing" | "closed";
  orders: TabOrder[];
  subtotal: string;
  tax_amount: string;
  total: string;
  amount_paid: string;
  amount_remaining: string;
  opened_at: string;
}

export interface TabOrderResponse extends OrderResponse {
  tab: TabResponse;
}

export interface TabPaymentResponse {
  payment_id: string;
  client_secret: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add tab TypeScript types"
```

---

### Task 12: Add tab API functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add tab API functions**

Add to `frontend/src/lib/api.ts`:

```typescript
import type {
  TabResponse,
  TabOrderResponse,
  TabPaymentResponse,
  ConfirmOrderItem,
} from "@/types";

export async function fetchTab(
  slug: string,
  tableIdentifier: string
): Promise<TabResponse | null> {
  try {
    return await apiFetch<TabResponse>(
      `${API}/order/${slug}/tab/?table=${encodeURIComponent(tableIdentifier)}`
    );
  } catch {
    return null;
  }
}

export async function createTabOrder(
  slug: string,
  items: ConfirmOrderItem[],
  rawInput: string,
  tableIdentifier: string,
  language: string,
  customerName?: string,
  customerPhone?: string,
  allergies?: string[]
): Promise<TabOrderResponse> {
  return apiFetch<TabOrderResponse>(`${API}/order/${slug}/tab/order/`, {
    method: "POST",
    body: JSON.stringify({
      items,
      raw_input: rawInput,
      table_identifier: tableIdentifier,
      language,
      customer_name: customerName || "",
      customer_phone: customerPhone || "",
      allergies: allergies || [],
    }),
  });
}

export async function closeTab(
  slug: string,
  tableIdentifier: string
): Promise<TabResponse> {
  return apiFetch<TabResponse>(`${API}/order/${slug}/tab/close/`, {
    method: "POST",
    body: JSON.stringify({ table_identifier: tableIdentifier }),
  });
}

export async function createTabPayment(
  slug: string,
  tabId: string,
  type: "full" | "split_even" | "pay_by_item",
  splitCount?: number,
  itemIds?: number[]
): Promise<TabPaymentResponse> {
  return apiFetch<TabPaymentResponse>(`${API}/order/${slug}/tab/pay/`, {
    method: "POST",
    body: JSON.stringify({
      tab_id: tabId,
      type,
      split_count: splitCount,
      item_ids: itemIds,
    }),
  });
}

export async function confirmTabPayment(
  slug: string,
  paymentId: string
): Promise<TabResponse> {
  return apiFetch<TabResponse>(
    `${API}/order/${slug}/tab/confirm-payment/${paymentId}/`,
    { method: "POST" }
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add tab API client functions"
```

---

### Task 13: Update order store for tab mode

**Files:**
- Modify: `frontend/src/stores/order-store.ts`

- [ ] **Step 1: Update store**

In `frontend/src/stores/order-store.ts`:

1. Update the `OrderStep` type (line 4):
```typescript
type OrderStep = "welcome" | "ordering" | "cart" | "payment" | "submitted" | "tab_review";
```

2. Add tab fields to the `OrderState` interface (after `paymentMode`):
```typescript
  paymentModel: "upfront" | "tab";
  tabId: string | null;
  tabOrders: TabOrder[];
  tabTotal: string;
  tabAmountPaid: string;
  tabAmountRemaining: string;
  tabPaymentId: string | null;
```

3. Add tab setters to the interface:
```typescript
  setPaymentModel: (model: "upfront" | "tab") => void;
  setTabId: (id: string | null) => void;
  setTabData: (tab: TabResponse) => void;
  setTabPaymentId: (id: string | null) => void;
```

4. Add initial state values:
```typescript
  paymentModel: "upfront",
  tabId: null,
  tabOrders: [],
  tabTotal: "0.00",
  tabAmountPaid: "0.00",
  tabAmountRemaining: "0.00",
  tabPaymentId: null,
```

5. Add setter implementations:
```typescript
  setPaymentModel: (model) => set({ paymentModel: model }),
  setTabId: (id) => set({ tabId: id }),
  setTabData: (tab) => set({
    tabId: tab.id,
    tabOrders: tab.orders,
    tabTotal: tab.total,
    tabAmountPaid: tab.amount_paid,
    tabAmountRemaining: tab.amount_remaining,
  }),
  setTabPaymentId: (id) => set({ tabPaymentId: id }),
```

6. Update the `reset` function to include tab fields.

- [ ] **Step 2: Add import for TabOrder and TabResponse types**

```typescript
import type { TabOrder, TabResponse } from "@/types";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/order-store.ts
git commit -m "feat: add tab state to order store"
```

---

## Chunk 4: Frontend — New Components

### Task 14: TabStatusBar component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/TabStatusBar.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/app/order/[slug]/components/TabStatusBar.tsx
"use client";

import { useOrderStore } from "@/stores/order-store";

export default function TabStatusBar() {
  const { paymentModel, tabTotal, tabOrders, setStep } = useOrderStore();

  if (paymentModel !== "tab" || tabOrders.length === 0) return null;

  return (
    <div className="sticky top-0 z-40 flex items-center justify-between bg-zinc-800 px-4 py-2 text-sm text-zinc-200">
      <span>
        Tab open &middot; {tabOrders.length} order{tabOrders.length !== 1 ? "s" : ""} &middot; ${tabTotal}
      </span>
      <button
        onClick={() => setStep("tab_review")}
        className="rounded-md bg-white/10 px-3 py-1 text-xs font-medium hover:bg-white/20"
      >
        View Tab
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/TabStatusBar.tsx
git commit -m "feat: add TabStatusBar component"
```

---

### Task 15: TabReviewStep component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/TabReviewStep.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/app/order/[slug]/components/TabReviewStep.tsx
"use client";

import { useState } from "react";
import { useOrderStore } from "@/stores/order-store";
import { closeTab } from "@/lib/api";
import SplitEvenModal from "./SplitEvenModal";
import PayByItemModal from "./PayByItemModal";

interface TabReviewStepProps {
  slug: string;
}

export default function TabReviewStep({ slug }: TabReviewStepProps) {
  const {
    tabId,
    tabOrders,
    tabTotal,
    tabAmountPaid,
    tabAmountRemaining,
    tableIdentifier,
    setStep,
    setTabData,
  } = useOrderStore();

  const [showSplitModal, setShowSplitModal] = useState(false);
  const [showItemModal, setShowItemModal] = useState(false);
  const [closing, setClosing] = useState(false);

  const handleCloseAndPay = async (payType: "full" | "split_even" | "pay_by_item") => {
    if (!tabId) return;

    setClosing(true);
    try {
      const tab = await closeTab(slug, tableIdentifier);
      setTabData(tab);

      if (payType === "split_even") {
        setShowSplitModal(true);
      } else if (payType === "pay_by_item") {
        setShowItemModal(true);
      } else {
        setStep("payment");
      }
    } catch {
      setClosing(false);
    }
  };

  const isClosing = parseFloat(tabAmountPaid) > 0;

  return (
    <div className="flex flex-col gap-6 p-4">
      <h2 className="text-xl font-bold text-white">Your Tab</h2>

      {/* Orders list */}
      <div className="flex flex-col gap-4">
        {tabOrders.map((order, idx) => (
          <div key={order.id} className="rounded-lg bg-zinc-800 p-4">
            <div className="mb-2 text-sm font-medium text-zinc-400">
              Order {idx + 1}
            </div>
            {order.items.map((item) => (
              <div key={item.id} className="flex justify-between text-sm text-zinc-200">
                <span>
                  {item.quantity}x {item.name}
                </span>
                <span>${item.line_total}</span>
              </div>
            ))}
            <div className="mt-2 border-t border-zinc-700 pt-2 text-right text-sm text-zinc-300">
              ${order.total_price}
            </div>
          </div>
        ))}
      </div>

      {/* Totals */}
      <div className="rounded-lg bg-zinc-800 p-4">
        <div className="flex justify-between text-zinc-300">
          <span>Total</span>
          <span className="text-lg font-bold text-white">${tabTotal}</span>
        </div>
        {isClosing && (
          <>
            <div className="flex justify-between text-sm text-green-400">
              <span>Paid</span>
              <span>${tabAmountPaid}</span>
            </div>
            <div className="flex justify-between text-sm text-zinc-300">
              <span>Remaining</span>
              <span>${tabAmountRemaining}</span>
            </div>
          </>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex flex-col gap-3">
        <button
          onClick={() => handleCloseAndPay("full")}
          disabled={closing}
          className="w-full rounded-xl bg-white py-3 text-center font-semibold text-black"
        >
          Pay Full Amount (${tabAmountRemaining || tabTotal})
        </button>
        <button
          onClick={() => handleCloseAndPay("split_even")}
          disabled={closing}
          className="w-full rounded-xl bg-zinc-700 py-3 text-center font-semibold text-white"
        >
          Split Evenly
        </button>
        <button
          onClick={() => handleCloseAndPay("pay_by_item")}
          disabled={closing}
          className="w-full rounded-xl bg-zinc-700 py-3 text-center font-semibold text-white"
        >
          Pay By Item
        </button>
        <button
          onClick={() => setStep("ordering")}
          className="w-full py-3 text-center text-sm text-zinc-400"
        >
          Order More
        </button>
      </div>

      {showSplitModal && (
        <SplitEvenModal
          slug={slug}
          onClose={() => setShowSplitModal(false)}
        />
      )}
      {showItemModal && (
        <PayByItemModal
          slug={slug}
          onClose={() => setShowItemModal(false)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/TabReviewStep.tsx
git commit -m "feat: add TabReviewStep component"
```

---

### Task 16: SplitEvenModal component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/SplitEvenModal.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/app/order/[slug]/components/SplitEvenModal.tsx
"use client";

import { useState } from "react";
import { useOrderStore } from "@/stores/order-store";
import { createTabPayment } from "@/lib/api";

interface SplitEvenModalProps {
  slug: string;
  onClose: () => void;
}

export default function SplitEvenModal({ slug, onClose }: SplitEvenModalProps) {
  const { tabId, tabTotal, tabAmountRemaining } = useOrderStore();
  const [splitCount, setSplitCount] = useState(2);
  const [loading, setLoading] = useState(false);

  const remaining = parseFloat(tabAmountRemaining || tabTotal);
  const perPerson = (remaining / splitCount).toFixed(2);

  const handlePay = async () => {
    if (!tabId) return;
    setLoading(true);
    try {
      const { client_secret, payment_id } = await createTabPayment(
        slug,
        tabId,
        "split_even",
        splitCount
      );
      // Store client_secret and payment_id for PaymentStep
      useOrderStore.getState().setClientSecret(client_secret);
      useOrderStore.getState().setTabPaymentId(payment_id);
      useOrderStore.getState().setStep("payment");
      onClose();
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60">
      <div className="w-full max-w-md rounded-t-2xl bg-zinc-900 p-6">
        <h3 className="mb-4 text-lg font-bold text-white">Split Evenly</h3>

        <div className="mb-4 flex items-center justify-between">
          <span className="text-zinc-300">Number of people</span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSplitCount(Math.max(2, splitCount - 1))}
              className="h-8 w-8 rounded-full bg-zinc-700 text-white"
            >
              -
            </button>
            <span className="min-w-[2rem] text-center text-lg font-bold text-white">
              {splitCount}
            </span>
            <button
              onClick={() => setSplitCount(splitCount + 1)}
              className="h-8 w-8 rounded-full bg-zinc-700 text-white"
            >
              +
            </button>
          </div>
        </div>

        <div className="mb-6 rounded-lg bg-zinc-800 p-4 text-center">
          <div className="text-sm text-zinc-400">Your share</div>
          <div className="text-2xl font-bold text-white">${perPerson}</div>
        </div>

        <button
          onClick={handlePay}
          disabled={loading}
          className="mb-3 w-full rounded-xl bg-white py-3 text-center font-semibold text-black"
        >
          {loading ? "Processing..." : `Pay $${perPerson}`}
        </button>
        <button
          onClick={onClose}
          className="w-full py-3 text-center text-sm text-zinc-400"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/SplitEvenModal.tsx
git commit -m "feat: add SplitEvenModal component"
```

---

### Task 17: PayByItemModal component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/PayByItemModal.tsx`

- [ ] **Step 1: Create component**

```tsx
// frontend/src/app/order/[slug]/components/PayByItemModal.tsx
"use client";

import { useState } from "react";
import { useOrderStore } from "@/stores/order-store";
import { createTabPayment } from "@/lib/api";

interface PayByItemModalProps {
  slug: string;
  onClose: () => void;
}

export default function PayByItemModal({ slug, onClose }: PayByItemModalProps) {
  const { tabId, tabOrders } = useOrderStore();
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);

  const allItems = tabOrders.flatMap((order) =>
    order.items.map((item) => ({ ...item, orderId: order.id }))
  );

  const toggleItem = (itemId: number) => {
    const next = new Set(selectedItems);
    if (next.has(itemId)) {
      next.delete(itemId);
    } else {
      next.add(itemId);
    }
    setSelectedItems(next);
  };

  const selectedTotal = allItems
    .filter((item) => selectedItems.has(item.id))
    .reduce((sum, item) => sum + parseFloat(item.line_total), 0)
    .toFixed(2);

  const handlePay = async () => {
    if (!tabId || selectedItems.size === 0) return;
    setLoading(true);
    try {
      const { client_secret, payment_id } = await createTabPayment(
        slug,
        tabId,
        "pay_by_item",
        undefined,
        Array.from(selectedItems)
      );
      useOrderStore.getState().setClientSecret(client_secret);
      useOrderStore.getState().setTabPaymentId(payment_id);
      useOrderStore.getState().setStep("payment");
      onClose();
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60">
      <div className="max-h-[80vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-zinc-900 p-6">
        <h3 className="mb-4 text-lg font-bold text-white">Select Your Items</h3>

        <div className="mb-4 flex flex-col gap-2">
          {allItems.map((item) => (
            <label
              key={item.id}
              className="flex cursor-pointer items-center gap-3 rounded-lg bg-zinc-800 p-3"
            >
              <input
                type="checkbox"
                checked={selectedItems.has(item.id)}
                onChange={() => toggleItem(item.id)}
                className="h-5 w-5 rounded border-zinc-600"
              />
              <span className="flex-1 text-sm text-zinc-200">
                {item.quantity}x {item.name}
              </span>
              <span className="text-sm text-zinc-300">${item.line_total}</span>
            </label>
          ))}
        </div>

        <div className="mb-4 rounded-lg bg-zinc-800 p-4 text-center">
          <div className="text-sm text-zinc-400">Your total</div>
          <div className="text-2xl font-bold text-white">${selectedTotal}</div>
        </div>

        <button
          onClick={handlePay}
          disabled={loading || selectedItems.size === 0}
          className="mb-3 w-full rounded-xl bg-white py-3 text-center font-semibold text-black disabled:opacity-50"
        >
          {loading ? "Processing..." : `Pay $${selectedTotal}`}
        </button>
        <button
          onClick={onClose}
          className="w-full py-3 text-center text-sm text-zinc-400"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/PayByItemModal.tsx
git commit -m "feat: add PayByItemModal component"
```

---

## Chunk 5: Frontend — Modify Existing Components & Integration

### Task 18: Add `use-tab` query hook and update WelcomeStep

**Files:**
- Create: `frontend/src/hooks/use-tab.ts`
- Modify: `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`

- [ ] **Step 1: Create the tab query hook**

Per frontend guidelines, never call `apiFetch` directly in components. Create:

```tsx
// frontend/src/hooks/use-tab.ts
import { useQuery } from "@tanstack/react-query";
import { fetchTab } from "@/lib/api";

export function useTab(slug: string, tableIdentifier: string, enabled = true) {
  return useQuery({
    queryKey: ["tab", slug, tableIdentifier],
    queryFn: () => fetchTab(slug, tableIdentifier),
    enabled: enabled && !!slug && !!tableIdentifier,
  });
}
```

- [ ] **Step 2: Update WelcomeStep**

Modify the component to use the `useTab` hook to check for an existing tab:

```tsx
import { useTab } from "@/hooks/use-tab";

// Inside component:
const { paymentModel, tableIdentifier, setStep, setTabData } = useOrderStore();
const { data: existingTab } = useTab(slug, tableIdentifier, paymentModel === "tab");

useEffect(() => {
  if (existingTab) {
    setTabData(existingTab);
  }
}, [existingTab, setTabData]);
```

In the JSX, add a conditional block before the "Start ordering" button:
```tsx
{existingTab && (
  <div className="rounded-lg bg-zinc-800 p-4 text-center">
    <p className="mb-2 text-zinc-300">
      You have an open tab (${existingTab.total})
    </p>
    <button
      onClick={() => setStep("ordering")}
      className="w-full rounded-xl bg-white py-3 font-semibold text-black"
    >
      Continue Ordering
    </button>
    <button
      onClick={() => setStep("tab_review")}
      className="mt-2 w-full py-2 text-sm text-zinc-400"
    >
      View Tab & Pay
    </button>
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-tab.ts frontend/src/app/order/[slug]/components/WelcomeStep.tsx
git commit -m "feat: add useTab hook and WelcomeStep open tab detection"
```

---

### Task 19: Update CartBottomBar for tab mode

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/CartBottomBar.tsx`

- [ ] **Step 1: Update CartBottomBar**

The button text and behavior should change in tab mode:
- Upfront: "Review Order" -> goes to cart -> payment
- Tab: "Place Order" -> creates tab order -> goes to submitted

In `CartBottomBar.tsx`, read `paymentModel` from store and change the button label:

```tsx
const { parsedItems, totalPrice, setStep, paymentModel } = useOrderStore();

// In the button:
<button onClick={() => setStep("cart")}>
  {paymentModel === "tab" ? "Place Order" : "Review Order"} ({parsedItems.length} items - ${totalPrice})
</button>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/CartBottomBar.tsx
git commit -m "feat: CartBottomBar shows 'Place Order' in tab mode"
```

---

### Task 20: Update SubmittedStep for tab mode

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`

- [ ] **Step 1: Update SubmittedStep**

In tab mode, show "Order More" and "View Tab & Pay" buttons instead of only the order status.

Add to the component:
```tsx
const { paymentModel, setStep } = useOrderStore();
```

In the JSX, add a conditional block for tab mode after the order confirmation content:
```tsx
{paymentModel === "tab" && (
  <div className="flex flex-col gap-3 mt-6">
    <button
      onClick={() => setStep("ordering")}
      className="w-full rounded-xl bg-zinc-700 py-3 text-center font-semibold text-white"
    >
      Order More
    </button>
    <button
      onClick={() => setStep("tab_review")}
      className="w-full rounded-xl bg-white py-3 text-center font-semibold text-black"
    >
      View Tab & Pay
    </button>
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/SubmittedStep.tsx
git commit -m "feat: SubmittedStep shows tab actions in tab mode"
```

---

### Task 21: Update PaymentStep for tab payments

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/PaymentStep.tsx`

- [ ] **Step 1: Update PaymentStep**

The PaymentStep needs a code path for tab payments. When `paymentModel === "tab"`, after Stripe payment succeeds, call `confirmTabPayment` instead of `confirmPayment`, then navigate to a closed-tab confirmation.

Add to the PaymentForm's `handleSubmit`:
```tsx
const { paymentModel } = useOrderStore();

// After stripe.confirmPayment succeeds:
if (paymentModel === "tab") {
  // Tab payment uses the payment_id stored in the store (set by SplitEvenModal/PayByItemModal/TabReviewStep)
  const tabPaymentId = useOrderStore.getState().tabPaymentId;
  if (tabPaymentId) {
    await confirmTabPayment(slug, tabPaymentId);
  }
  setStep("submitted");
} else {
  await confirmPayment(slug, orderId!);
  setStep("submitted");
}
```

Note: `tabPaymentId` was already added to the store in Task 13. SplitEvenModal and PayByItemModal already store it in Tasks 16 and 17.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/components/PaymentStep.tsx
git commit -m "feat: PaymentStep supports tab payment confirmation"
```

---

### Task 22: Wire up TabReviewStep and TabStatusBar in main page

**Files:**
- Modify: `frontend/src/app/order/[slug]/page.tsx`

- [ ] **Step 1: Update page.tsx**

Add the `tab_review` step to the step rendering and include `TabStatusBar`:

```tsx
import TabReviewStep from "./components/TabReviewStep";
import TabStatusBar from "./components/TabStatusBar";
```

In the step render switch, add:
```tsx
case "tab_review":
  return <TabReviewStep slug={slug} />;
```

Add `<TabStatusBar />` at the top of the layout (before step content) so it appears during ordering and submitted steps.

Also, update the menu fetch effect to set `paymentModel` from the response:
```tsx
const { setPaymentModel } = useOrderStore();
// After fetching menu:
setPaymentModel(menu.payment_model);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/order/[slug]/page.tsx
git commit -m "feat: wire up TabReviewStep and TabStatusBar in order page"
```

---

### Task 23: Update tab order creation hook

**Files:**
- Create: `frontend/src/hooks/use-tab-order.ts`

- [ ] **Step 1: Create the hook**

```tsx
// frontend/src/hooks/use-tab-order.ts
import { useMutation } from "@tanstack/react-query";
import { createTabOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";
import type { ConfirmOrderItem } from "@/types";

export function useTabOrder(slug: string) {
  const { setStep, setOrderId, setTabData, setError } = useOrderStore();

  return useMutation({
    mutationFn: (params: {
      items: ConfirmOrderItem[];
      rawInput: string;
      tableIdentifier: string;
      language: string;
      customerName?: string;
      customerPhone?: string;
      allergies?: string[];
    }) =>
      createTabOrder(
        slug,
        params.items,
        params.rawInput,
        params.tableIdentifier,
        params.language,
        params.customerName,
        params.customerPhone,
        params.allergies
      ),
    onSuccess: (data) => {
      setOrderId(data.id);
      setTabData(data.tab);
      setStep("submitted");
    },
    onError: (error: Error) => {
      setError(error.message);
    },
  });
}
```

- [ ] **Step 2: Wire it into the cart/checkout flow**

The cart confirmation component (where "Place Order" is handled) should use `useTabOrder` when `paymentModel === "tab"` instead of `useConfirmOrder` or `createPayment`. Find the component that handles the cart "confirm" action and add a conditional:

```tsx
const { paymentModel } = useOrderStore();
const tabOrder = useTabOrder(slug);
const confirmOrder = useConfirmOrder(slug); // existing

const handleConfirm = () => {
  if (paymentModel === "tab") {
    tabOrder.mutate({ items, rawInput, tableIdentifier, language, customerName, customerPhone, allergies });
  } else {
    confirmOrder.mutate(/* existing args */);
  }
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-tab-order.ts frontend/src/app/order/[slug]/components/
git commit -m "feat: add useTabOrder hook and wire into cart flow"
```

---

### Task 24: Add restaurant settings UI for payment model

**Files:**
- Find and modify the restaurant settings/edit component in the frontend
- This allows restaurant owners to toggle between `upfront` and `tab`

- [ ] **Step 1: Find the restaurant settings component**

Search for the restaurant edit/settings page in the frontend (`frontend/src/app/` directory). Look for components that render the RestaurantSerializer fields.

- [ ] **Step 2: Add payment model toggle**

Add a section to the restaurant settings form:

```tsx
<div className="flex flex-col gap-2">
  <label className="text-sm font-medium text-zinc-300">Payment Model</label>
  <select
    value={restaurant.payment_model}
    onChange={(e) => updateRestaurant({ payment_model: e.target.value })}
    className="rounded-lg bg-zinc-800 p-2 text-white"
  >
    <option value="upfront">Pay Upfront (customers pay before order is sent to kitchen)</option>
    <option value="tab">Open Tab (customers order first, pay later)</option>
  </select>
</div>
```

- [ ] **Step 3: Ensure RestaurantSerializer includes `payment_model`**

In `backend/restaurants/serializers/restaurant_serializers.py`, add `payment_model` to the `RestaurantSerializer` fields list.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/ backend/restaurants/serializers/
git commit -m "feat: add payment model toggle to restaurant settings"
```

---

## Chunk 6: WebSocket & Final Integration

### Task 25: Add WebSocket consumer for tab events

**Files:**
- Modify: `backend/orders/consumers.py` (add TabConsumer)
- Modify: `backend/orders/routing.py` (add tab route)
- Create: `backend/orders/tab_broadcasts.py` (broadcast helper functions)

- [ ] **Step 1: Create broadcast helpers**

```python
# backend/orders/tab_broadcasts.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def broadcast_tab_update(tab, event_type, extra_data=None):
    """Broadcast a tab event to the table's WebSocket channel."""
    channel_layer = get_channel_layer()
    group_name = f"tab_{tab.id}"
    data = {
        "type": event_type,
        "tab_id": str(tab.id),
        "table_identifier": tab.table_identifier,
        "total": str(tab.total),
        "amount_paid": str(tab.amount_paid),
        "amount_remaining": str(tab.amount_remaining),
        "status": tab.status,
    }
    if extra_data:
        data.update(extra_data)
    async_to_sync(channel_layer.group_send)(
        group_name,
        {"type": "tab_update", "data": data},
    )
```

- [ ] **Step 2: Add TabConsumer**

Append to `backend/orders/consumers.py`:

```python
class TabConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.tab_id = str(self.scope["url_route"]["kwargs"]["tab_id"])
        self.group_name = f"tab_{self.tab_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def tab_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))
```

- [ ] **Step 3: Add route**

In `backend/orders/routing.py`, add:
```python
from orders.consumers import CustomerOrderConsumer, KitchenConsumer, TabConsumer

websocket_urlpatterns = [
    # ... existing routes ...
    re_path(r"ws/tab/(?P<tab_id>[0-9a-f-]+)/$", TabConsumer.as_asgi()),
]
```

- [ ] **Step 4: Add broadcasts to tab service and payment service**

In `backend/orders/tab_service.py`, after tab state changes, call:
```python
from orders.tab_broadcasts import broadcast_tab_update
```

Add after `get_or_create_tab` creates a new order (in `tab_views.py` TabOrderView):
```python
broadcast_tab_update(tab, "tab.order_added")
```

In `TabService.close_tab`:
```python
broadcast_tab_update(tab, "tab.closing")
```

In `TabService.finalize_tab`:
```python
broadcast_tab_update(tab, "tab.closed")
```

In `TabPaymentService.confirm_payment` (after marking payment as paid):
```python
broadcast_tab_update(tab, "tab.payment_received")
```

- [ ] **Step 5: Commit**

```bash
git add backend/orders/consumers.py backend/orders/routing.py backend/orders/tab_broadcasts.py backend/orders/tab_service.py backend/orders/tab_views.py backend/orders/tab_payment_service.py
git commit -m "feat: add WebSocket broadcasts for tab events"
```

---

### Task 26: Final integration test

**Files:**
- Create: `backend/orders/tests/test_tab_integration.py`

- [ ] **Step 1: Write end-to-end integration test**

```python
# backend/orders/tests/test_tab_integration.py
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from orders.models import Order, Tab, TabPayment
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestTabFullFlow:
    """Tests the complete tab lifecycle: order -> order again -> close -> pay -> closed."""

    @pytest.fixture
    def tab_restaurant(self):
        restaurant = RestaurantFactory(slug="full-flow", payment_model="tab", tax_rate=Decimal("8.875"))
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        burger = MenuItemFactory(category=cat, name="Burger")
        burger_var = MenuItemVariantFactory(menu_item=burger, price=Decimal("10.00"), is_default=True)
        fries = MenuItemFactory(category=cat, name="Fries")
        fries_var = MenuItemVariantFactory(menu_item=fries, price=Decimal("5.00"), is_default=True)
        return {
            "restaurant": restaurant,
            "burger": burger,
            "burger_var": burger_var,
            "fries": fries,
            "fries_var": fries_var,
        }

    @patch("orders.tab_payment_service.stripe")
    def test_full_tab_lifecycle(self, mock_stripe, api_client, tab_restaurant):
        r = tab_restaurant

        # 1. Place first order
        resp1 = api_client.post(
            "/api/order/full-flow/tab/order/",
            {
                "items": [{"menu_item_id": r["burger"].id, "variant_id": r["burger_var"].id, "quantity": 2}],
                "raw_input": "Two burgers",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert resp1.status_code == status.HTTP_201_CREATED
        assert resp1.data["status"] == "confirmed"
        assert resp1.data["payment_status"] == "deferred"
        tab_id = resp1.data["tab"]["id"]

        # 2. Place second order on same tab
        resp2 = api_client.post(
            "/api/order/full-flow/tab/order/",
            {
                "items": [{"menu_item_id": r["fries"].id, "variant_id": r["fries_var"].id, "quantity": 1}],
                "raw_input": "One fries",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert resp2.status_code == status.HTTP_201_CREATED
        assert resp2.data["tab"]["id"] == tab_id

        # 3. Verify tab shows both orders
        resp_tab = api_client.get("/api/order/full-flow/tab/", {"table": "A3"})
        assert resp_tab.status_code == status.HTTP_200_OK
        assert len(resp_tab.data["orders"]) == 2
        # Subtotal: 20.00 + 5.00 = 25.00
        assert resp_tab.data["subtotal"] == "25.00"

        # 4. Close the tab
        resp_close = api_client.post(
            "/api/order/full-flow/tab/close/",
            {"table_identifier": "A3"},
            format="json",
        )
        assert resp_close.status_code == status.HTTP_200_OK
        assert resp_close.data["status"] == "closing"

        # 5. Create payment
        mock_intent = MagicMock()
        mock_intent.id = "pi_flow_test"
        mock_intent.client_secret = "pi_flow_test_secret"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        resp_pay = api_client.post(
            "/api/order/full-flow/tab/pay/",
            {"tab_id": tab_id, "type": "full"},
            format="json",
        )
        assert resp_pay.status_code == status.HTTP_201_CREATED
        assert resp_pay.data["client_secret"] == "pi_flow_test_secret"

        # 6. Confirm payment
        mock_intent_retrieved = MagicMock()
        mock_intent_retrieved.status = "succeeded"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent_retrieved

        payment_id = resp_pay.data["payment_id"]
        resp_confirm = api_client.post(f"/api/order/full-flow/tab/confirm-payment/{payment_id}/")
        assert resp_confirm.status_code == status.HTTP_200_OK
        assert resp_confirm.data["status"] == "closed"

        # 7. Verify all orders are now paid
        orders = Order.objects.filter(tab__id=tab_id)
        for order in orders:
            assert order.payment_status == "paid"
            assert order.paid_at is not None

        # 8. Verify new tab can be opened for same table
        resp_new = api_client.post(
            "/api/order/full-flow/tab/order/",
            {
                "items": [{"menu_item_id": r["burger"].id, "variant_id": r["burger_var"].id, "quantity": 1}],
                "raw_input": "One burger",
                "table_identifier": "A3",
                "language": "en",
            },
            format="json",
        )
        assert resp_new.status_code == status.HTTP_201_CREATED
        assert resp_new.data["tab"]["id"] != tab_id
```

- [ ] **Step 2: Run the integration test**

Run: `cd backend && python -m pytest orders/tests/test_tab_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run the full test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS, no regressions

- [ ] **Step 4: Commit**

```bash
git add backend/orders/tests/test_tab_integration.py
git commit -m "test: add full tab lifecycle integration test"
```
