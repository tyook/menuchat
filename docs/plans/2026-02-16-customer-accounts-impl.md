# Customer Accounts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add optional customer accounts with separate auth, order linking, profile/preferences, and order history.

**Architecture:** New `customers` Django app with independent `Customer` model and JWT auth. Separate frontend auth store and route group (`/account/*`). Order model gets nullable customer FK + name/phone fields. Header is split by context (admin vs customer).

**Tech Stack:** Django, DRF, SimpleJWT, Next.js 14 (App Router), Zustand, React Query, shadcn/ui

**Design doc:** `docs/plans/2026-02-16-customer-accounts-design.md`

---

## Task 1: Create `customers` Django app + Customer model

**Files:**
- Create: `backend/customers/__init__.py`
- Create: `backend/customers/apps.py`
- Create: `backend/customers/models.py`
- Create: `backend/customers/managers.py`
- Create: `backend/customers/admin.py`
- Modify: `backend/config/settings.py` (add to INSTALLED_APPS)
- Create: `backend/customers/tests/__init__.py`
- Create: `backend/customers/tests/factories.py`
- Create: `backend/customers/tests/test_models.py`

**Step 1: Create the app skeleton**

```bash
cd backend && python manage.py startapp customers
```

Then delete the auto-generated files we don't need and create the proper structure.

**Step 2: Write the Customer manager**

Create `backend/customers/managers.py`:

```python
from django.contrib.auth.hashers import make_password, check_password


class CustomerManager:
    """
    Not a Django model manager — just a helper for password operations
    since Customer is not an AbstractUser.
    """

    @staticmethod
    def hash_password(raw_password: str) -> str:
        return make_password(raw_password)

    @staticmethod
    def check_password(raw_password: str, hashed: str) -> bool:
        return check_password(raw_password, hashed)
```

**Step 3: Write the Customer model**

Create `backend/customers/models.py`:

```python
import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class Customer(models.Model):
    class AuthProvider(models.TextChoices):
        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, blank=True, default="")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, default="")
    auth_provider = models.CharField(
        max_length=10, choices=AuthProvider.choices, default=AuthProvider.EMAIL
    )
    auth_provider_id = models.CharField(max_length=255, blank=True, default="")
    dietary_preferences = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)
    preferred_language = models.CharField(max_length=10, blank=True, default="en-US")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password: str):
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.name} ({self.email})"
```

**Step 4: Register in settings**

In `backend/config/settings.py`, add `"customers"` to `INSTALLED_APPS` after `"orders"`.

**Step 5: Write model tests**

Create `backend/customers/tests/__init__.py` (empty).

Create `backend/customers/tests/factories.py`:

```python
import factory
from customers.models import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    email = factory.Sequence(lambda n: f"customer{n}@example.com")
    name = factory.Faker("name")
    phone = factory.Faker("phone_number")
    auth_provider = "email"
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
```

Create `backend/customers/tests/test_models.py`:

```python
import pytest
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestCustomerModel:
    def test_create_customer(self):
        customer = CustomerFactory(email="alice@example.com", name="Alice")
        assert customer.email == "alice@example.com"
        assert customer.name == "Alice"
        assert customer.id is not None

    def test_password_hashing(self):
        customer = CustomerFactory()
        assert customer.check_password("testpass123")
        assert not customer.check_password("wrongpass")

    def test_str(self):
        customer = CustomerFactory(name="Bob", email="bob@example.com")
        assert str(customer) == "Bob (bob@example.com)"

    def test_default_fields(self):
        customer = CustomerFactory()
        assert customer.dietary_preferences == []
        assert customer.allergies == []
        assert customer.preferred_language == "en-US"
        assert customer.auth_provider == "email"
```

**Step 6: Run migration and tests**

```bash
cd backend && python manage.py makemigrations customers
cd backend && python manage.py migrate
cd backend && pytest customers/tests/test_models.py -v
```

**Step 7: Commit**

```bash
git add backend/customers/ backend/config/settings.py
git commit -m "feat: add customers app with Customer model"
```

---

## Task 2: Customer JWT auth — register + login endpoints

**Files:**
- Create: `backend/customers/serializers.py`
- Create: `backend/customers/views.py`
- Create: `backend/customers/urls.py`
- Create: `backend/customers/authentication.py`
- Modify: `backend/config/urls.py`
- Create: `backend/customers/tests/test_auth.py`

**Step 1: Write the customer JWT helper**

Create `backend/customers/authentication.py`:

```python
from datetime import timedelta
from django.conf import settings
from rest_framework_simplejwt.tokens import Token


class CustomerAccessToken(Token):
    token_type = "access"
    lifetime = timedelta(hours=12)

    @classmethod
    def for_customer(cls, customer):
        token = cls()
        token["customer_id"] = str(customer.id)
        token["token_type"] = "customer_access"
        return token


class CustomerRefreshToken(Token):
    token_type = "refresh"
    lifetime = timedelta(days=7)
    access_token_class = CustomerAccessToken

    @classmethod
    def for_customer(cls, customer):
        token = cls()
        token["customer_id"] = str(customer.id)
        token["token_type"] = "customer_refresh"
        return token

    @property
    def access_token(self):
        access = CustomerAccessToken()
        access.set_exp(from_time=self.current_time)
        access["customer_id"] = self["customer_id"]
        access["token_type"] = "customer_access"
        return access
```

**Step 2: Write auth serializers**

Create `backend/customers/serializers.py`:

```python
from rest_framework import serializers
from customers.models import Customer
from customers.authentication import CustomerRefreshToken


class CustomerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20, required=False, default="")
    link_order_id = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        if Customer.objects.filter(email=value).exists():
            raise serializers.ValidationError("A customer with this email already exists.")
        return value.lower()

    def create(self, validated_data):
        link_order_id = validated_data.pop("link_order_id", None)
        password = validated_data.pop("password")
        customer = Customer(**validated_data)
        customer.set_password(password)
        customer.save()

        # Link order if provided
        if link_order_id:
            from orders.models import Order
            Order.objects.filter(id=link_order_id, customer__isnull=True).update(
                customer=customer
            )

        return customer

    def to_representation(self, instance):
        refresh = CustomerRefreshToken.for_customer(instance)
        return {
            "customer": {
                "id": str(instance.id),
                "email": instance.email,
                "name": instance.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        customer = Customer.objects.filter(email=data["email"].lower()).first()
        if not customer or not customer.password or not customer.check_password(data["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        data["customer"] = customer
        return data


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id", "email", "name", "phone",
            "dietary_preferences", "allergies", "preferred_language",
            "auth_provider", "created_at",
        ]
        read_only_fields = ["id", "email", "auth_provider", "created_at"]
```

**Step 3: Write auth views**

Create `backend/customers/views.py`:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.authentication import CustomerAccessToken, CustomerRefreshToken
from customers.models import Customer
from customers.serializers import (
    CustomerRegisterSerializer,
    CustomerLoginSerializer,
    CustomerProfileSerializer,
)


class CustomerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CustomerLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.validated_data["customer"]
        refresh = CustomerRefreshToken.for_customer(customer)
        return Response({
            "customer": {
                "id": str(customer.id),
                "email": customer.email,
                "name": customer.name,
            },
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })


class CustomerTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_str = request.data.get("refresh")
        if not token_str:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = CustomerRefreshToken(token_str)
            if refresh.get("token_type") != "customer_refresh":
                raise Exception("Invalid token type")
            return Response({"access": str(refresh.access_token)})
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class CustomerProfileView(APIView):
    """GET/PATCH customer profile. Requires customer JWT."""

    def get_customer(self, request):
        """Extract customer from JWT token."""
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None
        token_str = auth_header.split(" ", 1)[1]
        try:
            token = CustomerAccessToken(token_str)
            if token.get("token_type") != "customer_access":
                return None
            return Customer.objects.get(id=token["customer_id"])
        except Exception:
            return None

    def get(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(CustomerProfileSerializer(customer).data)

    def patch(self, request):
        customer = self.get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = CustomerProfileSerializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
```

**Step 4: Wire up URLs**

Create `backend/customers/urls.py`:

```python
from django.urls import path
from customers.views import (
    CustomerRegisterView,
    CustomerLoginView,
    CustomerTokenRefreshView,
    CustomerProfileView,
)

urlpatterns = [
    path("auth/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("auth/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("auth/refresh/", CustomerTokenRefreshView.as_view(), name="customer-token-refresh"),
    path("profile/", CustomerProfileView.as_view(), name="customer-profile"),
]
```

Modify `backend/config/urls.py` — add:

```python
path("api/customer/", include("customers.urls")),
```

**Step 5: Write auth tests**

Create `backend/customers/tests/test_auth.py`:

```python
import pytest
from rest_framework.test import APIClient
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestCustomerRegister:
    def test_register_success(self, api_client):
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "new@example.com",
            "password": "securepass123",
            "name": "New Customer",
        }, format="json")
        assert resp.status_code == 201
        assert "access" in resp.data
        assert "refresh" in resp.data
        assert resp.data["customer"]["email"] == "new@example.com"

    def test_register_duplicate_email(self, api_client):
        CustomerFactory(email="taken@example.com")
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "taken@example.com",
            "password": "securepass123",
            "name": "Another",
        }, format="json")
        assert resp.status_code == 400

    def test_register_short_password(self, api_client):
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "new@example.com",
            "password": "short",
            "name": "New Customer",
        }, format="json")
        assert resp.status_code == 400


class TestCustomerLogin:
    def test_login_success(self, api_client):
        CustomerFactory(email="alice@example.com")
        resp = api_client.post("/api/customer/auth/login/", {
            "email": "alice@example.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert "refresh" in resp.data

    def test_login_wrong_password(self, api_client):
        CustomerFactory(email="alice@example.com")
        resp = api_client.post("/api/customer/auth/login/", {
            "email": "alice@example.com",
            "password": "wrongpass",
        }, format="json")
        assert resp.status_code == 400

    def test_login_nonexistent(self, api_client):
        resp = api_client.post("/api/customer/auth/login/", {
            "email": "nobody@example.com",
            "password": "testpass123",
        }, format="json")
        assert resp.status_code == 400


class TestCustomerTokenRefresh:
    def test_refresh_success(self, api_client):
        CustomerFactory(email="alice@example.com")
        login_resp = api_client.post("/api/customer/auth/login/", {
            "email": "alice@example.com",
            "password": "testpass123",
        }, format="json")
        refresh_token = login_resp.data["refresh"]
        resp = api_client.post("/api/customer/auth/refresh/", {
            "refresh": refresh_token,
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data

    def test_refresh_invalid_token(self, api_client):
        resp = api_client.post("/api/customer/auth/refresh/", {
            "refresh": "invalid-token",
        }, format="json")
        assert resp.status_code == 401

    def test_owner_token_rejected(self, api_client):
        """Owner refresh tokens should not work on customer refresh endpoint."""
        from restaurants.tests.factories import UserFactory
        from rest_framework_simplejwt.tokens import RefreshToken
        user = UserFactory()
        owner_refresh = str(RefreshToken.for_user(user))
        resp = api_client.post("/api/customer/auth/refresh/", {
            "refresh": owner_refresh,
        }, format="json")
        assert resp.status_code == 401
```

**Step 6: Run tests**

```bash
cd backend && pytest customers/tests/ -v
```

**Step 7: Commit**

```bash
git add backend/customers/ backend/config/urls.py
git commit -m "feat: add customer auth endpoints (register, login, refresh, profile)"
```

---

## Task 3: Add customer fields to Order model

**Files:**
- Modify: `backend/orders/models.py`
- Modify: `backend/orders/serializers.py`
- Modify: `backend/orders/views.py` (ConfirmOrderView)
- Create: `backend/customers/tests/test_order_linking.py`

**Step 1: Add fields to Order model**

In `backend/orders/models.py`, add to the `Order` class:

```python
from customers.models import Customer

# Add these fields after table_identifier:
customer = models.ForeignKey(
    "customers.Customer", on_delete=models.SET_NULL,
    null=True, blank=True, related_name="orders",
)
customer_name = models.CharField(max_length=255, blank=True, default="")
customer_phone = models.CharField(max_length=20, blank=True, default="")
```

**Step 2: Generate and run migration**

```bash
cd backend && python manage.py makemigrations orders
cd backend && python manage.py migrate
```

**Step 3: Update ConfirmOrderSerializer**

In `backend/orders/serializers.py`, add to `ConfirmOrderSerializer`:

```python
customer_name = serializers.CharField(max_length=255, required=False, default="")
customer_phone = serializers.CharField(max_length=20, required=False, default="", allow_blank=True)
```

Add to `OrderResponseSerializer.Meta.fields`:

```python
"customer_name", "customer_phone"
```

**Step 4: Update ConfirmOrderView**

In `backend/orders/views.py`, in the `ConfirmOrderView.post` method, when creating the order, add:

```python
customer_name=data.get("customer_name", ""),
customer_phone=data.get("customer_phone", ""),
```

Also, try to auto-link if a customer JWT is present:

```python
# Before creating the order, check for customer auth
customer = None
auth_header = request.META.get("HTTP_AUTHORIZATION", "")
if auth_header.startswith("Bearer "):
    try:
        from customers.authentication import CustomerAccessToken
        from customers.models import Customer
        token = CustomerAccessToken(auth_header.split(" ", 1)[1])
        if token.get("token_type") == "customer_access":
            customer = Customer.objects.get(id=token["customer_id"])
    except Exception:
        pass  # Not a customer token or invalid — that's fine

# Then in Order.objects.create(...), add:
customer=customer,
```

**Step 5: Write tests**

Create `backend/customers/tests/test_order_linking.py`:

```python
import pytest
from rest_framework.test import APIClient
from customers.tests.factories import CustomerFactory
from customers.authentication import CustomerRefreshToken
from restaurants.tests.factories import (
    RestaurantFactory, MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory,
)

pytestmark = pytest.mark.django_db


class TestOrderCustomerLinking:
    @pytest.fixture
    def restaurant_with_menu(self):
        restaurant = RestaurantFactory(slug="test-rest")
        category = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=category)
        variant = MenuItemVariantFactory(menu_item=item, price="10.00")
        return restaurant, item, variant

    def test_confirm_order_with_customer_name(self, api_client, restaurant_with_menu):
        restaurant, item, variant = restaurant_with_menu
        resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
            "customer_phone": "555-1234",
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["customer_name"] == "Alice"
        assert resp.data["customer_phone"] == "555-1234"

    def test_confirm_order_auto_links_customer(self, api_client, restaurant_with_menu):
        restaurant, item, variant = restaurant_with_menu
        customer = CustomerFactory(email="alice@example.com")
        refresh = CustomerRefreshToken.for_customer(customer)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
        }, format="json")
        assert resp.status_code == 201
        from orders.models import Order
        order = Order.objects.get(id=resp.data["id"])
        assert order.customer == customer

    def test_register_links_existing_order(self, api_client, restaurant_with_menu):
        restaurant, item, variant = restaurant_with_menu
        # Place order as guest
        resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
        }, format="json")
        order_id = resp.data["id"]

        # Register with link_order_id
        resp = api_client.post("/api/customer/auth/register/", {
            "email": "alice@example.com",
            "password": "securepass123",
            "name": "Alice",
            "link_order_id": order_id,
        }, format="json")
        assert resp.status_code == 201

        from orders.models import Order
        order = Order.objects.get(id=order_id)
        from customers.models import Customer
        customer = Customer.objects.get(email="alice@example.com")
        assert order.customer == customer
```

**Step 6: Run tests**

```bash
cd backend && pytest customers/tests/ orders/tests/ -v
```

**Step 7: Commit**

```bash
git add backend/orders/ backend/customers/
git commit -m "feat: add customer fields to Order model with auto-linking"
```

---

## Task 4: Customer order history endpoint

**Files:**
- Modify: `backend/customers/views.py`
- Modify: `backend/customers/urls.py`
- Create: `backend/customers/tests/test_order_history.py`

**Step 1: Add order history view**

In `backend/customers/views.py`, add:

```python
from orders.serializers import OrderResponseSerializer
from orders.models import Order


class CustomerOrderHistoryView(APIView):
    """GET /api/customer/orders/ — list customer's past orders."""

    def get(self, request):
        customer = self._get_customer(request)
        if not customer:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        orders = Order.objects.filter(customer=customer).select_related(
            "restaurant"
        ).prefetch_related("items__menu_item", "items__variant")
        data = []
        for order in orders:
            order_data = OrderResponseSerializer(order).data
            order_data["restaurant_name"] = order.restaurant.name
            order_data["restaurant_slug"] = order.restaurant.slug
            data.append(order_data)
        return Response(data)

    def _get_customer(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None
        token_str = auth_header.split(" ", 1)[1]
        try:
            token = CustomerAccessToken(token_str)
            if token.get("token_type") != "customer_access":
                return None
            return Customer.objects.get(id=token["customer_id"])
        except Exception:
            return None
```

Note: Refactor the `_get_customer` logic out of both views into a shared helper or mixin to avoid duplication. Create a `CustomerAuthMixin`:

```python
class CustomerAuthMixin:
    """Mixin to extract customer from JWT."""

    def get_customer(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None
        token_str = auth_header.split(" ", 1)[1]
        try:
            token = CustomerAccessToken(token_str)
            if token.get("token_type") != "customer_access":
                return None
            return Customer.objects.get(id=token["customer_id"])
        except Exception:
            return None
```

Then have both `CustomerProfileView` and `CustomerOrderHistoryView` use `CustomerAuthMixin`.

**Step 2: Add URL**

In `backend/customers/urls.py`, add:

```python
path("orders/", CustomerOrderHistoryView.as_view(), name="customer-orders"),
```

**Step 3: Write tests**

Create `backend/customers/tests/test_order_history.py`:

```python
import pytest
from customers.tests.factories import CustomerFactory
from customers.authentication import CustomerRefreshToken
from orders.tests.factories import OrderFactory

pytestmark = pytest.mark.django_db


class TestCustomerOrderHistory:
    def test_list_own_orders(self, api_client):
        customer = CustomerFactory()
        order1 = OrderFactory(customer=customer, customer_name=customer.name)
        order2 = OrderFactory(customer=customer, customer_name=customer.name)
        OrderFactory()  # Another customer's order

        refresh = CustomerRefreshToken.for_customer(customer)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        resp = api_client.get("/api/customer/orders/")
        assert resp.status_code == 200
        assert len(resp.data) == 2

    def test_unauthenticated(self, api_client):
        resp = api_client.get("/api/customer/orders/")
        assert resp.status_code == 401

    def test_owner_token_rejected(self, api_client):
        from restaurants.tests.factories import UserFactory
        from rest_framework_simplejwt.tokens import RefreshToken
        user = UserFactory()
        token = str(RefreshToken.for_user(user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.get("/api/customer/orders/")
        assert resp.status_code == 401
```

**Step 4: Run tests**

```bash
cd backend && pytest customers/tests/ -v
```

**Step 5: Commit**

```bash
git add backend/customers/
git commit -m "feat: add customer order history endpoint"
```

---

## Task 5: Frontend — customer auth store + API functions

**Files:**
- Create: `frontend/src/stores/customer-auth-store.ts`
- Modify: `frontend/src/lib/api.ts` (add customer API functions)
- Modify: `frontend/src/types/index.ts` (add customer types)

**Step 1: Add customer types**

In `frontend/src/types/index.ts`, add:

```typescript
// Customer types
export interface CustomerProfile {
  id: string;
  email: string;
  name: string;
  phone: string;
  dietary_preferences: string[];
  allergies: string[];
  preferred_language: string;
  auth_provider: string;
  created_at: string;
}

export interface CustomerAuthResponse {
  customer: {
    id: string;
    email: string;
    name: string;
  };
  access: string;
  refresh: string;
}

export interface CustomerOrderHistoryItem extends OrderResponse {
  restaurant_name: string;
  restaurant_slug: string;
}
```

**Step 2: Add customer API functions**

In `frontend/src/lib/api.ts`, add:

```typescript
import type { CustomerAuthResponse, CustomerProfile, CustomerOrderHistoryItem } from "@/types";

const CUSTOMER_TOKEN_KEY = "customer_access_token";
const CUSTOMER_REFRESH_KEY = "customer_refresh_token";

export async function customerApiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_URL}${path}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const token = typeof window !== "undefined"
    ? localStorage.getItem(CUSTOMER_TOKEN_KEY)
    : null;
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401 && typeof window !== "undefined") {
    // Try refresh
    const refreshToken = localStorage.getItem(CUSTOMER_REFRESH_KEY);
    if (refreshToken) {
      try {
        const refreshResp = await fetch(`${url.split("/api/")[0]}/api/customer/auth/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        });
        if (refreshResp.ok) {
          const data = await refreshResp.json();
          localStorage.setItem(CUSTOMER_TOKEN_KEY, data.access);
          // Retry
          (headers as Record<string, string>)["Authorization"] = `Bearer ${data.access}`;
          const retryResp = await fetch(url, { ...options, headers });
          if (retryResp.ok) return retryResp.json();
        }
      } catch {}
    }
    // Clear auth
    localStorage.removeItem(CUSTOMER_TOKEN_KEY);
    localStorage.removeItem(CUSTOMER_REFRESH_KEY);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.email?.[0] || `API error: ${response.status}`);
  }

  return response.json();
}

export async function customerRegister(data: {
  email: string;
  password: string;
  name: string;
  phone?: string;
  link_order_id?: string;
}): Promise<CustomerAuthResponse> {
  return customerApiFetch<CustomerAuthResponse>("/api/customer/auth/register/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function customerLogin(
  email: string,
  password: string,
): Promise<CustomerAuthResponse> {
  return customerApiFetch<CustomerAuthResponse>("/api/customer/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function fetchCustomerProfile(): Promise<CustomerProfile> {
  return customerApiFetch<CustomerProfile>("/api/customer/profile/");
}

export async function updateCustomerProfile(
  data: Partial<CustomerProfile>,
): Promise<CustomerProfile> {
  return customerApiFetch<CustomerProfile>("/api/customer/profile/", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function fetchCustomerOrders(): Promise<CustomerOrderHistoryItem[]> {
  return customerApiFetch<CustomerOrderHistoryItem[]>("/api/customer/orders/");
}
```

**Step 3: Create customer auth store**

Create `frontend/src/stores/customer-auth-store.ts`:

```typescript
import { create } from "zustand";
import { customerLogin, customerRegister } from "@/lib/api";

const TOKEN_KEY = "customer_access_token";
const REFRESH_KEY = "customer_refresh_token";

interface CustomerAuthState {
  isAuthenticated: boolean;
  customer: { id: string; email: string; name: string } | null;

  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    name: string;
    phone?: string;
    link_order_id?: string;
  }) => Promise<void>;
  logout: () => void;
  checkAuth: () => boolean;
}

export const useCustomerAuthStore = create<CustomerAuthState>((set) => ({
  isAuthenticated:
    typeof window !== "undefined" && !!localStorage.getItem(TOKEN_KEY),
  customer: null,

  login: async (email, password) => {
    const data = await customerLogin(email, password);
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    set({ isAuthenticated: true, customer: data.customer });
  },

  register: async (formData) => {
    const data = await customerRegister(formData);
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    set({ isAuthenticated: true, customer: data.customer });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    set({ isAuthenticated: false, customer: null });
  },

  checkAuth: () => {
    return !!localStorage.getItem(TOKEN_KEY);
  },
}));
```

**Step 4: Commit**

```bash
git add frontend/src/stores/customer-auth-store.ts frontend/src/lib/api.ts frontend/src/types/index.ts
git commit -m "feat: add customer auth store and API functions"
```

---

## Task 6: Frontend — customer login + register pages

**Files:**
- Create: `frontend/src/app/account/login/page.tsx`
- Create: `frontend/src/app/account/register/page.tsx`
- Create: `frontend/src/app/account/layout.tsx`

**Step 1: Create account layout**

Create `frontend/src/app/account/layout.tsx`:

```tsx
export default function AccountLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
```

**Step 2: Create customer login page**

Create `frontend/src/app/account/login/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";

export default function CustomerLoginPage() {
  const router = useRouter();
  const login = useCustomerAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/account/orders");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6 text-center">Sign In</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-destructive text-sm">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>
        <p className="text-sm text-center mt-4 text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/account/register" className="text-primary underline">
            Register
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

**Step 3: Create customer register page**

Create `frontend/src/app/account/register/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";

export default function CustomerRegisterPage() {
  const router = useRouter();
  const register = useCustomerAuthStore((s) => s.register);
  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    phone: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(form);
      router.push("/account/orders");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6 text-center">Create Account</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="phone">Phone (optional)</Label>
            <Input
              id="phone"
              type="tel"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={8}
            />
          </div>
          {error && <p className="text-destructive text-sm">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Creating account..." : "Create Account"}
          </Button>
        </form>
        <p className="text-sm text-center mt-4 text-muted-foreground">
          Already have an account?{" "}
          <Link href="/account/login" className="text-primary underline">
            Sign in
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/app/account/
git commit -m "feat: add customer login and register pages"
```

---

## Task 7: Frontend — update order flow (name/phone + account prompt)

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`
- Modify: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`
- Modify: `frontend/src/stores/order-store.ts`
- Modify: `frontend/src/hooks/use-confirm-order.ts`
- Modify: `frontend/src/types/index.ts` (update ConfirmOrderPayload if needed)

**Step 1: Add customer name/phone to order store**

In `frontend/src/stores/order-store.ts`, add to the state interface and initial state:

```typescript
customerName: string;
customerPhone: string;
setCustomerName: (name: string) => void;
setCustomerPhone: (phone: string) => void;
```

**Step 2: Update ConfirmationStep**

In `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`, add name and phone input fields above the "Place Order" button:

```tsx
{/* Customer info */}
<div className="space-y-3 mb-6">
  <div>
    <Label htmlFor="customer-name">Your name</Label>
    <Input
      id="customer-name"
      value={customerName}
      onChange={(e) => setCustomerName(e.target.value)}
      placeholder="Name for the order"
      required
    />
  </div>
  <div>
    <Label htmlFor="customer-phone">Phone (optional)</Label>
    <Input
      id="customer-phone"
      type="tel"
      value={customerPhone}
      onChange={(e) => setCustomerPhone(e.target.value)}
      placeholder="For order updates"
    />
  </div>
</div>
```

If a customer is logged in (via `useCustomerAuthStore`), auto-fill name and phone from their profile.

Pass `customer_name` and `customer_phone` in the confirm mutation payload.

**Step 3: Update SubmittedStep with account creation prompt**

In `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`, add below the success message:

```tsx
const { isAuthenticated } = useCustomerAuthStore();
const { orderId, customerName, customerPhone } = useOrderStore();
const [showRegister, setShowRegister] = useState(false);
const [registerForm, setRegisterForm] = useState({ email: "", password: "" });
const [registerError, setRegisterError] = useState("");
const [registerLoading, setRegisterLoading] = useState(false);
const register = useCustomerAuthStore((s) => s.register);

const handleRegister = async (e: React.FormEvent) => {
  e.preventDefault();
  setRegisterLoading(true);
  setRegisterError("");
  try {
    await register({
      email: registerForm.email,
      password: registerForm.password,
      name: customerName,
      phone: customerPhone,
      link_order_id: orderId || undefined,
    });
    setShowRegister(false);
  } catch (err) {
    setRegisterError(err instanceof Error ? err.message : "Registration failed");
  } finally {
    setRegisterLoading(false);
  }
};
```

Display conditionally: if not authenticated, show the prompt card. If authenticated (just registered), show "Account created!" confirmation.

**Step 4: Commit**

```bash
git add frontend/src/app/order/ frontend/src/stores/order-store.ts frontend/src/types/index.ts
git commit -m "feat: add customer name/phone to order flow and post-order account prompt"
```

---

## Task 8: Frontend — customer orders page

**Files:**
- Create: `frontend/src/app/account/orders/page.tsx`
- Create: `frontend/src/hooks/use-customer-orders.ts`

**Step 1: Create hook**

Create `frontend/src/hooks/use-customer-orders.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchCustomerOrders } from "@/lib/api";

export function useCustomerOrders() {
  return useQuery({
    queryKey: ["customer-orders"],
    queryFn: fetchCustomerOrders,
  });
}
```

**Step 2: Create orders page**

Create `frontend/src/app/account/orders/page.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";
import { useCustomerOrders } from "@/hooks/use-customer-orders";

export default function CustomerOrdersPage() {
  const router = useRouter();
  const { isAuthenticated } = useCustomerAuthStore();
  const { data: orders, isLoading, error } = useCustomerOrders();

  useEffect(() => {
    if (!isAuthenticated) router.push("/account/login");
  }, [isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground">Failed to load orders.</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Your Orders</h1>
      {!orders || orders.length === 0 ? (
        <p className="text-muted-foreground">No orders yet.</p>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id} className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-medium">{order.restaurant_name}</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(order.created_at).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {order.items.length} item{order.items.length !== 1 ? "s" : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-medium">${order.total_price}</p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {order.status}
                  </p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/app/account/orders/ frontend/src/hooks/use-customer-orders.ts
git commit -m "feat: add customer order history page"
```

---

## Task 9: Frontend — customer profile page

**Files:**
- Create: `frontend/src/app/account/profile/page.tsx`
- Create: `frontend/src/hooks/use-customer-profile.ts`

**Step 1: Create hook**

Create `frontend/src/hooks/use-customer-profile.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchCustomerProfile, updateCustomerProfile } from "@/lib/api";
import type { CustomerProfile } from "@/types";

export function useCustomerProfile() {
  return useQuery({
    queryKey: ["customer-profile"],
    queryFn: fetchCustomerProfile,
  });
}

export function useUpdateCustomerProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<CustomerProfile>) => updateCustomerProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer-profile"] });
    },
  });
}
```

**Step 2: Create profile page**

Create `frontend/src/app/account/profile/page.tsx` with:
- Name, phone edit fields
- Dietary preferences — multi-select chips from predefined list + custom input
- Allergies — same pattern
- Preferred language dropdown (reuse `SPEECH_LANGUAGES`)
- Save button that calls `useUpdateCustomerProfile`
- Also sync to `usePreferencesStore` (localStorage) so preferences work on the order page immediately

**Step 3: Commit**

```bash
git add frontend/src/app/account/profile/ frontend/src/hooks/use-customer-profile.ts
git commit -m "feat: add customer profile page with dietary preferences"
```

---

## Task 10: Frontend — header reorganization

**Files:**
- Modify: `frontend/src/components/Header.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/order/[slug]/page.tsx`

**Step 1: Update Header to hide preferences for admin users**

In `frontend/src/components/Header.tsx`:
- Remove the `PreferencesDialog` and its menu item from the admin dropdown
- The Header component stays as the admin/global header

**Step 2: Add customer context to order pages**

In the order page (`/order/[slug]/page.tsx`), add a small gear icon in the top corner that opens `PreferencesDialog`. This already exists partially with `MenuModal` in the top-right. Add a preferences gear icon next to it.

Also add a small "Sign in" link for returning customers that goes to `/account/login`.

**Step 3: Conditionally show header**

In `frontend/src/app/layout.tsx`, use `usePathname()` to conditionally render the Header:
- Show on `/admin/*` and `/kitchen/*` routes
- Hide on `/order/*` routes (order pages have their own minimal UI)
- Show on `/account/*` routes with a simpler customer-focused nav

Alternatively, use Next.js route groups to have different layouts:
- `(admin)/admin/*` — uses admin layout with Header
- `(customer)/order/*`, `(customer)/account/*` — uses customer layout (no admin header)

The simplest approach: just hide the Header on `/order/*` pages since those have their own UI.

**Step 4: Commit**

```bash
git add frontend/src/components/Header.tsx frontend/src/app/
git commit -m "feat: reorganize header — remove preferences from admin, show on order pages"
```

---

## Task 11: Frontend build + backend test verification

**Step 1: Run all backend tests**

```bash
cd backend && pytest -v
```

Fix any failures.

**Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Fix any TypeScript errors.

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test and build issues from customer accounts feature"
```

---

## Notes for future tasks (not in this plan)

- **Google OAuth**: Add `POST /api/customer/auth/google/` endpoint that exchanges a Google ID token for a customer JWT. Frontend needs `@react-oauth/google` package.
- **Apple Sign-In**: Similar to Google, with Apple's identity token.
- **Preferences sync**: When a logged-in customer saves preferences on the profile page, also update localStorage. When they save via the PreferencesDialog on the order page, also push to the backend profile.
