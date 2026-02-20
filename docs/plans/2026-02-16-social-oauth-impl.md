# Google & Apple OAuth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google and Apple social login for customers alongside existing email+password auth.

**Architecture:** Frontend obtains an ID token from Google/Apple SDKs, sends it to the backend. Backend verifies the token, creates or finds the customer, returns a customer JWT. Same `Customer` model — `auth_provider` and `auth_provider_id` fields already exist.

**Tech Stack:** `google-auth` (Python), `PyJWT` + Apple public keys (Python), `@react-oauth/google` (React), Apple Sign-In JS SDK

**Prerequisite:** Google Cloud Console and Apple Developer account setup (client IDs, secrets). These are configured via environment variables — the plan assumes they exist.

---

## Task 1: Install backend dependencies

**Files:**
- Modify: `backend/pyproject.toml`

**Step 1: Add google-auth and PyJWT**

`google-auth` is used to verify Google ID tokens. `PyJWT` with `cryptography` is used to verify Apple identity tokens.

```bash
cd backend && poetry add google-auth PyJWT cryptography
```

Note: `PyJWT` may already be installed as a dependency of `djangorestframework-simplejwt`. `cryptography` is needed for Apple's RS256 token verification.

**Step 2: Add env vars to settings**

In `backend/config/settings.py`, add at the bottom:

```python
# ---------------------------------------------------------------------------
# Social Auth
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
APPLE_CLIENT_ID = config("APPLE_CLIENT_ID", default="")  # e.g. "com.yourapp.service"
```

**Step 3: Commit**

```bash
git add backend/pyproject.toml backend/poetry.lock backend/config/settings.py
git commit -m "chore: add google-auth and PyJWT dependencies for social login"
```

---

## Task 2: Backend — Google OAuth endpoint

**Files:**
- Create: `backend/customers/social_auth.py`
- Modify: `backend/customers/views.py`
- Modify: `backend/customers/urls.py`
- Create: `backend/customers/tests/test_google_auth.py`

**Step 1: Write Google token verification helper**

Create `backend/customers/social_auth.py`:

```python
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings


def verify_google_token(token: str) -> dict:
    """
    Verify a Google ID token and return user info.

    Returns dict with keys: sub, email, name, picture
    Raises ValueError if token is invalid.
    """
    idinfo = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )
    # Verify issuer
    if idinfo["iss"] not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Invalid issuer.")
    return {
        "sub": idinfo["sub"],           # Google user ID
        "email": idinfo.get("email"),
        "name": idinfo.get("name", ""),
        "picture": idinfo.get("picture", ""),
    }
```

**Step 2: Write Google auth serializer**

In `backend/customers/serializers.py`, add:

```python
class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()
    link_order_id = serializers.UUIDField(required=False, allow_null=True, default=None)
```

**Step 3: Write Google auth view**

In `backend/customers/views.py`, add:

```python
from customers.social_auth import verify_google_token


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        link_order_id = request.data.get("link_order_id")
        if not token:
            return Response(
                {"detail": "Google token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            google_user = verify_google_token(token)
        except ValueError as e:
            return Response(
                {"detail": f"Invalid Google token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = google_user["email"]
        if not email:
            return Response(
                {"detail": "Google account has no email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Find or create customer
        customer, created = Customer.objects.get_or_create(
            email=email.lower(),
            defaults={
                "name": google_user["name"],
                "auth_provider": "google",
                "auth_provider_id": google_user["sub"],
            },
        )

        # If existing customer, update provider info if they were email-only
        if not created and customer.auth_provider == "email":
            customer.auth_provider = "google"
            customer.auth_provider_id = google_user["sub"]
            customer.save(update_fields=["auth_provider", "auth_provider_id"])

        # Link order if provided
        if link_order_id:
            from orders.models import Order
            Order.objects.filter(id=link_order_id, customer__isnull=True).update(
                customer=customer
            )

        # Return JWT
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
```

**Step 4: Add URL**

In `backend/customers/urls.py`, add:

```python
path("auth/google/", GoogleAuthView.as_view(), name="customer-google-auth"),
```

**Step 5: Write tests**

Create `backend/customers/tests/test_google_auth.py`:

```python
import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from customers.models import Customer
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestGoogleAuth:
    MOCK_GOOGLE_USER = {
        "sub": "google-user-123",
        "email": "alice@gmail.com",
        "name": "Alice Smith",
        "picture": "https://example.com/photo.jpg",
    }

    @patch("customers.views.verify_google_token")
    def test_google_login_new_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_GOOGLE_USER
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "fake-google-token",
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert resp.data["customer"]["email"] == "alice@gmail.com"
        assert resp.data["customer"]["name"] == "Alice Smith"
        # Customer created
        customer = Customer.objects.get(email="alice@gmail.com")
        assert customer.auth_provider == "google"
        assert customer.auth_provider_id == "google-user-123"

    @patch("customers.views.verify_google_token")
    def test_google_login_existing_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_GOOGLE_USER
        CustomerFactory(email="alice@gmail.com", name="Alice")
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "fake-google-token",
        }, format="json")
        assert resp.status_code == 200
        assert resp.data["customer"]["email"] == "alice@gmail.com"
        # No duplicate created
        assert Customer.objects.filter(email="alice@gmail.com").count() == 1

    @patch("customers.views.verify_google_token")
    def test_google_login_invalid_token(self, mock_verify, api_client):
        mock_verify.side_effect = ValueError("Invalid token")
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "bad-token",
        }, format="json")
        assert resp.status_code == 400

    def test_google_login_missing_token(self, api_client):
        resp = api_client.post("/api/customer/auth/google/", {}, format="json")
        assert resp.status_code == 400

    @patch("customers.views.verify_google_token")
    def test_google_login_links_order(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_GOOGLE_USER
        # Create a guest order first
        from restaurants.tests.factories import RestaurantFactory, MenuCategoryFactory, MenuItemFactory, MenuItemVariantFactory
        restaurant = RestaurantFactory()
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat)
        variant = MenuItemVariantFactory(menu_item=item, price="10.00")
        order_resp = api_client.post(f"/api/order/{restaurant.slug}/confirm/", {
            "items": [{"menu_item_id": item.id, "variant_id": variant.id, "quantity": 1}],
            "raw_input": "one item",
            "customer_name": "Alice",
        }, format="json")
        order_id = order_resp.data["id"]

        # Google auth with link_order_id
        resp = api_client.post("/api/customer/auth/google/", {
            "token": "fake-google-token",
            "link_order_id": order_id,
        }, format="json")
        assert resp.status_code == 200
        from orders.models import Order
        order = Order.objects.get(id=order_id)
        assert order.customer is not None
        assert order.customer.email == "alice@gmail.com"
```

**Step 6: Run tests**

```bash
cd backend && poetry run pytest customers/tests/test_google_auth.py -v
```

**Step 7: Commit**

```bash
git add backend/customers/
git commit -m "feat: add Google OAuth login endpoint for customers"
```

---

## Task 3: Backend — Apple Sign-In endpoint

**Files:**
- Modify: `backend/customers/social_auth.py`
- Modify: `backend/customers/views.py`
- Modify: `backend/customers/urls.py`
- Create: `backend/customers/tests/test_apple_auth.py`

**Step 1: Write Apple token verification helper**

In `backend/customers/social_auth.py`, add:

```python
import jwt
import requests as http_requests

APPLE_PUBLIC_KEYS_URL = "https://appleid.apple.com/auth/keys"
_apple_keys_cache = None


def _get_apple_public_keys():
    """Fetch and cache Apple's public keys."""
    global _apple_keys_cache
    if _apple_keys_cache is None:
        resp = http_requests.get(APPLE_PUBLIC_KEYS_URL, timeout=10)
        resp.raise_for_status()
        _apple_keys_cache = resp.json()["keys"]
    return _apple_keys_cache


def verify_apple_token(token: str) -> dict:
    """
    Verify an Apple identity token and return user info.

    Returns dict with keys: sub, email, name
    Raises ValueError if token is invalid.
    """
    # Decode header to find the right key
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Token missing kid header.")

    # Find matching public key
    apple_keys = _get_apple_public_keys()
    matching_key = None
    for key in apple_keys:
        if key["kid"] == kid:
            matching_key = key
            break
    if not matching_key:
        raise ValueError("No matching Apple public key found.")

    # Build public key and verify
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(matching_key)
    decoded = jwt.decode(
        token,
        key=public_key,
        algorithms=["RS256"],
        audience=settings.APPLE_CLIENT_ID,
        issuer="https://appleid.apple.com",
    )

    return {
        "sub": decoded["sub"],
        "email": decoded.get("email"),
        "name": "",  # Apple only sends name on first auth; frontend must pass it
    }
```

**Step 2: Write Apple auth view**

In `backend/customers/views.py`, add:

```python
from customers.social_auth import verify_apple_token


class AppleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        name = request.data.get("name", "")  # Apple sends name only on first sign-in
        link_order_id = request.data.get("link_order_id")
        if not token:
            return Response(
                {"detail": "Apple token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            apple_user = verify_apple_token(token)
        except (ValueError, Exception) as e:
            return Response(
                {"detail": f"Invalid Apple token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = apple_user["email"]
        if not email:
            return Response(
                {"detail": "Apple account has no email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use name from request body (Apple only sends it the first time)
        display_name = name or apple_user.get("name", "") or email.split("@")[0]

        customer, created = Customer.objects.get_or_create(
            email=email.lower(),
            defaults={
                "name": display_name,
                "auth_provider": "apple",
                "auth_provider_id": apple_user["sub"],
            },
        )

        if not created and customer.auth_provider == "email":
            customer.auth_provider = "apple"
            customer.auth_provider_id = apple_user["sub"]
            customer.save(update_fields=["auth_provider", "auth_provider_id"])

        if link_order_id:
            from orders.models import Order
            Order.objects.filter(id=link_order_id, customer__isnull=True).update(
                customer=customer
            )

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
```

**Step 3: Add URL**

In `backend/customers/urls.py`, add:

```python
path("auth/apple/", AppleAuthView.as_view(), name="customer-apple-auth"),
```

**Step 4: Write tests**

Create `backend/customers/tests/test_apple_auth.py`:

```python
import pytest
from unittest.mock import patch
from customers.models import Customer
from customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


class TestAppleAuth:
    MOCK_APPLE_USER = {
        "sub": "apple-user-456",
        "email": "bob@icloud.com",
        "name": "",
    }

    @patch("customers.views.verify_apple_token")
    def test_apple_login_new_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_APPLE_USER
        resp = api_client.post("/api/customer/auth/apple/", {
            "token": "fake-apple-token",
            "name": "Bob Jones",
        }, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data
        assert resp.data["customer"]["email"] == "bob@icloud.com"
        customer = Customer.objects.get(email="bob@icloud.com")
        assert customer.auth_provider == "apple"
        assert customer.auth_provider_id == "apple-user-456"
        assert customer.name == "Bob Jones"

    @patch("customers.views.verify_apple_token")
    def test_apple_login_existing_user(self, mock_verify, api_client):
        mock_verify.return_value = self.MOCK_APPLE_USER
        CustomerFactory(email="bob@icloud.com", name="Bob")
        resp = api_client.post("/api/customer/auth/apple/", {
            "token": "fake-apple-token",
        }, format="json")
        assert resp.status_code == 200
        assert Customer.objects.filter(email="bob@icloud.com").count() == 1

    @patch("customers.views.verify_apple_token")
    def test_apple_login_invalid_token(self, mock_verify, api_client):
        mock_verify.side_effect = ValueError("Invalid token")
        resp = api_client.post("/api/customer/auth/apple/", {
            "token": "bad-token",
        }, format="json")
        assert resp.status_code == 400

    def test_apple_login_missing_token(self, api_client):
        resp = api_client.post("/api/customer/auth/apple/", {}, format="json")
        assert resp.status_code == 400

    @patch("customers.views.verify_apple_token")
    def test_apple_login_fallback_name(self, mock_verify, api_client):
        """When no name is provided, use email prefix as display name."""
        mock_verify.return_value = self.MOCK_APPLE_USER
        resp = api_client.post("/api/customer/auth/apple/", {
            "token": "fake-apple-token",
            # No name provided
        }, format="json")
        assert resp.status_code == 200
        customer = Customer.objects.get(email="bob@icloud.com")
        assert customer.name == "bob"  # Falls back to email prefix
```

**Step 5: Run tests**

```bash
cd backend && poetry run pytest customers/tests/test_apple_auth.py -v
```

**Step 6: Commit**

```bash
git add backend/customers/
git commit -m "feat: add Apple Sign-In endpoint for customers"
```

---

## Task 4: Frontend — install Google OAuth package

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install @react-oauth/google**

```bash
cd frontend && npm install @react-oauth/google
```

**Step 2: Add GoogleOAuthProvider to layout**

In `frontend/src/app/layout.tsx`, wrap the app with `GoogleOAuthProvider`:

```tsx
import { GoogleOAuthProvider } from "@react-oauth/google";

// In the return:
<GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ""}>
  <QueryProvider>
    <ConditionalHeader />
    {children}
  </QueryProvider>
</GoogleOAuthProvider>
```

Note: The layout needs to become a client component, or the provider should be extracted into a separate client component wrapper (preferred). Create `frontend/src/components/GoogleAuthProvider.tsx`:

```tsx
"use client";

import { GoogleOAuthProvider } from "@react-oauth/google";

export function GoogleAuthWrapper({ children }: { children: React.ReactNode }) {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
  if (!clientId) return <>{children}</>;
  return (
    <GoogleOAuthProvider clientId={clientId}>
      {children}
    </GoogleOAuthProvider>
  );
}
```

Then use `<GoogleAuthWrapper>` in `layout.tsx`.

**Step 3: Add API functions**

In `frontend/src/lib/api.ts`, add:

```typescript
export async function customerGoogleAuth(
  token: string,
  linkOrderId?: string,
): Promise<CustomerAuthResponse> {
  return customerApiFetch<CustomerAuthResponse>("/api/customer/auth/google/", {
    method: "POST",
    body: JSON.stringify({ token, link_order_id: linkOrderId }),
  });
}

export async function customerAppleAuth(
  token: string,
  name?: string,
  linkOrderId?: string,
): Promise<CustomerAuthResponse> {
  return customerApiFetch<CustomerAuthResponse>("/api/customer/auth/apple/", {
    method: "POST",
    body: JSON.stringify({ token, name, link_order_id: linkOrderId }),
  });
}
```

**Step 4: Add social login methods to customer auth store**

In `frontend/src/stores/customer-auth-store.ts`, add:

```typescript
import { customerGoogleAuth, customerAppleAuth } from "@/lib/api";

// Add to interface:
googleLogin: (token: string, linkOrderId?: string) => Promise<void>;
appleLogin: (token: string, name?: string, linkOrderId?: string) => Promise<void>;

// Add to store:
googleLogin: async (token, linkOrderId) => {
  const data = await customerGoogleAuth(token, linkOrderId);
  localStorage.setItem(TOKEN_KEY, data.access);
  localStorage.setItem(REFRESH_KEY, data.refresh);
  set({ isAuthenticated: true, customer: data.customer });
},

appleLogin: async (token, name, linkOrderId) => {
  const data = await customerAppleAuth(token, name, linkOrderId);
  localStorage.setItem(TOKEN_KEY, data.access);
  localStorage.setItem(REFRESH_KEY, data.refresh);
  set({ isAuthenticated: true, customer: data.customer });
},
```

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: add Google OAuth provider and social auth API functions"
```

---

## Task 5: Frontend — create SocialLoginButtons component

**Files:**
- Create: `frontend/src/components/SocialLoginButtons.tsx`

This is a reusable component used in login, register, and submitted pages.

**Step 1: Create the component**

Create `frontend/src/components/SocialLoginButtons.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useGoogleLogin } from "@react-oauth/google";
import { Button } from "@/components/ui/button";
import { useCustomerAuthStore } from "@/stores/customer-auth-store";

interface SocialLoginButtonsProps {
  linkOrderId?: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
  disabled?: boolean;
}

export function SocialLoginButtons({
  linkOrderId,
  onSuccess,
  onError,
  disabled,
}: SocialLoginButtonsProps) {
  const { googleLogin, appleLogin } = useCustomerAuthStore();
  const [loading, setLoading] = useState<"google" | "apple" | null>(null);

  const handleGoogleLogin = useGoogleLogin({
    onSuccess: async (response) => {
      setLoading("google");
      try {
        await googleLogin(response.access_token, linkOrderId);
        onSuccess?.();
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Google login failed");
      } finally {
        setLoading(null);
      }
    },
    onError: () => {
      onError?.("Google login was cancelled or failed");
    },
    flow: "implicit",
  });

  const handleAppleLogin = async () => {
    setLoading("apple");
    try {
      // Apple Sign-In JS SDK
      const AppleID = (window as any).AppleID;
      if (!AppleID) {
        onError?.("Apple Sign-In is not available");
        setLoading(null);
        return;
      }
      const response = await AppleID.auth.signIn();
      const token = response.authorization.id_token;
      const name = response.user
        ? `${response.user.name.firstName} ${response.user.name.lastName}`
        : undefined;
      await appleLogin(token, name, linkOrderId);
      onSuccess?.();
    } catch (err) {
      if ((err as any)?.error !== "popup_closed_by_user") {
        onError?.(err instanceof Error ? err.message : "Apple login failed");
      }
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-2">
      <Button
        variant="outline"
        className="w-full"
        onClick={() => handleGoogleLogin()}
        disabled={disabled || loading !== null}
      >
        {loading === "google" ? "Signing in..." : "Continue with Google"}
      </Button>
      <Button
        variant="outline"
        className="w-full"
        onClick={handleAppleLogin}
        disabled={disabled || loading !== null}
      >
        {loading === "apple" ? "Signing in..." : "Continue with Apple"}
      </Button>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/SocialLoginButtons.tsx
git commit -m "feat: add reusable SocialLoginButtons component"
```

---

## Task 6: Frontend — add social login buttons to all customer auth pages

**Files:**
- Modify: `frontend/src/app/account/login/page.tsx`
- Modify: `frontend/src/app/account/register/page.tsx`
- Modify: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`

**Step 1: Add to customer login page**

In `frontend/src/app/account/login/page.tsx`, add after the email/password form and before the register link:

```tsx
<div className="relative my-4">
  <div className="absolute inset-0 flex items-center">
    <Separator className="w-full" />
  </div>
  <div className="relative flex justify-center text-xs uppercase">
    <span className="bg-card px-2 text-muted-foreground">or</span>
  </div>
</div>

<SocialLoginButtons
  onSuccess={() => router.push("/account/orders")}
  onError={(err) => setError(err)}
/>
```

**Step 2: Add to customer register page**

Same pattern as login — add social login buttons below the form with an "or" separator.

**Step 3: Add to SubmittedStep**

In the SubmittedStep, add social login buttons as the primary account creation option (before the email/password form):

```tsx
{!showRegister ? (
  <div className="space-y-3">
    <SocialLoginButtons
      linkOrderId={orderId || undefined}
      onSuccess={() => setRegisterSuccess(true)}
      onError={(err) => setRegisterError(err)}
    />
    <div className="relative my-2">
      <div className="absolute inset-0 flex items-center">
        <Separator className="w-full" />
      </div>
      <div className="relative flex justify-center text-xs uppercase">
        <span className="bg-card px-2 text-muted-foreground">or</span>
      </div>
    </div>
    <Button variant="outline" className="w-full" onClick={() => setShowRegister(true)}>
      Sign up with email
    </Button>
    <Button variant="ghost" className="w-full text-muted-foreground" onClick={() => {}}>
      Skip
    </Button>
  </div>
)}
```

This matches the design doc layout: Google -> Apple -> email -> Skip.

**Step 4: Commit**

```bash
git add frontend/src/app/account/ frontend/src/app/order/
git commit -m "feat: add social login buttons to login, register, and order submitted pages"
```

---

## Task 7: Frontend — add Apple Sign-In JS SDK

**Files:**
- Modify: `frontend/src/app/layout.tsx`

**Step 1: Load Apple JS SDK**

In `frontend/src/app/layout.tsx`, add the Apple Sign-In script tag in the `<head>`:

```tsx
import Script from "next/script";

// Inside the <html> tag, before <body>:
<Script
  src="https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js"
  strategy="lazyOnload"
/>
```

**Step 2: Initialize Apple Sign-In**

Create `frontend/src/components/AppleAuthInit.tsx`:

```tsx
"use client";

import { useEffect } from "react";

export function AppleAuthInit() {
  useEffect(() => {
    const AppleID = (window as any).AppleID;
    if (AppleID) {
      AppleID.auth.init({
        clientId: process.env.NEXT_PUBLIC_APPLE_CLIENT_ID || "",
        scope: "name email",
        redirectURI: window.location.origin,
        usePopup: true,
      });
    }
  }, []);

  return null;
}
```

Add `<AppleAuthInit />` inside the layout body.

**Step 3: Commit**

```bash
git add frontend/src/app/layout.tsx frontend/src/components/AppleAuthInit.tsx
git commit -m "feat: add Apple Sign-In JS SDK initialization"
```

---

## Task 8: Build + test verification

**Step 1: Run all backend tests**

```bash
cd backend && poetry run pytest customers/tests/ -v
```

Expected: All tests pass including new Google and Apple auth tests.

**Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: No TypeScript errors.

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve issues from social auth implementation"
```

---

## Environment Variables Required

Add these to `.env` (or equivalent):

```
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Apple Sign-In
APPLE_CLIENT_ID=com.yourapp.service
NEXT_PUBLIC_APPLE_CLIENT_ID=com.yourapp.service
```

**Google setup:** Google Cloud Console -> APIs & Services -> Credentials -> OAuth 2.0 Client ID (Web application). Add `http://localhost:3000` to authorized JavaScript origins.

**Apple setup:** Apple Developer Portal -> Certificates, Identifiers & Profiles -> Service IDs. Configure Sign in with Apple, add return URL.

## Notes

- Google `useGoogleLogin` with `flow: "implicit"` returns an `access_token`. The backend uses `google-auth` to verify it by calling Google's tokeninfo endpoint. Alternatively, use `flow: "auth-code"` for a more secure server-side flow — but implicit is simpler for MVP.
- Apple only sends the user's name on the **first** sign-in. The frontend must capture and send it to the backend on that first request. Subsequent sign-ins won't include the name.
- The `get_or_create` pattern means a customer who signed up with email+password can later sign in with Google if the emails match. Their `auth_provider` gets updated to `google`. This is intentional — one account per email.
