# Capacitor Mobile App Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing Next.js QR ordering app as native iOS/Android apps using Capacitor, with push notifications and native QR scanning.

**Architecture:** Capacitor 6 wraps a Next.js static export (`output: 'export'`). Dual build mode: static export for mobile, normal SSR for web. Native plugins provide push notifications (FCM) and QR camera scanning. Backend gets a new `notifications` Django app for device tokens and Firebase push delivery.

**Tech Stack:** Capacitor 6, Next.js 14 static export, `@capacitor/push-notifications`, `@capacitor-mlkit/barcode-scanning`, `@capacitor/status-bar`, `@capacitor/preferences`, `@capacitor/app`, `firebase-admin` (Python), Django REST Framework.

**Spec:** `docs/superpowers/specs/2026-04-08-capacitor-mobile-app-design.md`

---

## Chunk 1: Capacitor Setup & Static Export

### Task 1: Install Capacitor and configure dual build mode

**Files:**
- Modify: `frontend/package.json` (add dependencies and scripts)
- Modify: `frontend/next.config.mjs` (conditional static export)
- Create: `frontend/capacitor.config.ts`

- [ ] **Step 1: Install Capacitor core and CLI**

```bash
cd frontend && yarn add @capacitor/core @capacitor/cli cross-env
```

- [ ] **Step 2: Initialize Capacitor**

```bash
cd frontend && npx cap init "QR Ordering" "com.menuchat.qrordering" --web-dir out
```

This creates `capacitor.config.ts`. Replace its contents in the next step.

- [ ] **Step 3: Write Capacitor config**

Replace `frontend/capacitor.config.ts` with:

```ts
import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.menuchat.qrordering",
  appName: "MenuChat",
  webDir: "out",
  server: {
    hostname: "app.localhost",
    androidScheme: "https",
    allowNavigation: ["*"],
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
  },
};

export default config;
```

- [ ] **Step 4: Configure dual build mode in next.config.mjs**

Modify `frontend/next.config.mjs` to add conditional static export. Merge with any existing config — do not replace the file:

```js
/** @type {import('next').NextConfig} */
const isMobile = process.env.NEXT_BUILD_MODE === "mobile";

const nextConfig = {
  ...(isMobile && {
    output: "export",
    images: {
      unoptimized: true,
    },
  }),
};

export default nextConfig;
```

If the file already has other config properties (webpack, redirects, etc.), add the mobile spread alongside them rather than replacing.

- [ ] **Step 5: Add mobile build scripts to package.json**

Add to `scripts` in `frontend/package.json`:

```json
{
  "build:mobile": "cross-env NEXT_BUILD_MODE=mobile next build",
  "cap:sync": "npx cap sync",
  "cap:open:ios": "npx cap open ios",
  "cap:open:android": "npx cap open android"
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/capacitor.config.ts frontend/next.config.mjs
git commit -m "feat: add Capacitor setup and dual build mode"
```

---

### Task 2: Fix dynamic routes for static export

The app has dynamic routes that need `generateStaticParams` to work with `output: 'export'`. Each dynamic route must export this function returning an empty array so Next.js doesn't try to enumerate slugs at build time. Client-side routing resolves pages at runtime.

**Files:**
- Modify: `frontend/src/app/order/[slug]/page.tsx`
- Modify: `frontend/src/app/order/[slug]/[tableId]/page.tsx`
- Modify: `frontend/src/app/kitchen/[slug]/page.tsx`
- Modify: `frontend/src/app/account/orders/[orderId]/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/orders/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/billing/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/sync-logs/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/menu/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/settings/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/settings/integrations/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/analytics/page.tsx`
- Create: `frontend/public/404.html` (SPA fallback for Capacitor)

- [ ] **Step 1: Verify all dynamic route pages**

```bash
find frontend/src/app -name "page.tsx" -path "*\[*\]*"
```

This should find all 11 files listed above. If any additional dynamic routes were added, include them too.

- [ ] **Step 2: Add generateStaticParams to each dynamic route**

For each of the 11 dynamic route pages, add at the top of the file (after imports, before the component):

```tsx
export function generateStaticParams() {
  return [];
}

export const dynamicParams = true;
```

For example, in `frontend/src/app/order/[slug]/[tableId]/page.tsx`:

```tsx
// ... existing imports ...

export function generateStaticParams() {
  return [];
}

export const dynamicParams = true;

// ... existing component ...
```

Repeat for all 11 dynamic route pages.

- [ ] **Step 3: Create SPA fallback for Capacitor**

With `generateStaticParams` returning empty arrays, Next.js won't generate HTML for dynamic routes. Capacitor needs a fallback so unmatched paths still load the app.

Create `frontend/public/404.html` that redirects to the app's index. This file is copied to `out/404.html` during static export, and Capacitor's local server will serve it for unmatched routes:

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script>
    // SPA fallback: redirect unmatched Capacitor routes to index
    // The Next.js client-side router will resolve the correct page
    sessionStorage.setItem('capacitor_redirect', window.location.pathname + window.location.search);
    window.location.replace('/');
  </script>
</head>
<body></body>
</html>
```

Then in `frontend/src/app/page.tsx` (the home page), add redirect logic at the top of the component:

```tsx
useEffect(() => {
  const redirect = sessionStorage.getItem('capacitor_redirect');
  if (redirect) {
    sessionStorage.removeItem('capacitor_redirect');
    router.replace(redirect);
  }
}, [router]);
```

This ensures that when Capacitor loads a deep path like `/order/my-restaurant/table-5`, the 404 fallback bounces to `/` which then client-side navigates to the correct route.

- [ ] **Step 4: Test mobile build**

```bash
cd frontend && yarn build:mobile
```

Expected: build succeeds, `out/` directory is created with static files.

- [ ] **Step 5: Verify the output structure**

```bash
ls frontend/out/
ls frontend/out/_next/
```

Expected: HTML files, `_next/static/` with JS/CSS chunks, `404.html`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/ frontend/public/404.html
git commit -m "feat: add generateStaticParams and SPA fallback for static export"
```

---

### Task 3: Add iOS and Android native projects

**Files:**
- Create: `frontend/ios/` (generated by Capacitor)
- Create: `frontend/android/` (generated by Capacitor)
- Modify: `frontend/.gitignore` (ensure native projects are tracked but build artifacts aren't)

- [ ] **Step 1: Install Capacitor platform packages**

```bash
cd frontend && yarn add @capacitor/ios @capacitor/android
```

- [ ] **Step 2: Build mobile assets first**

```bash
cd frontend && yarn build:mobile
```

- [ ] **Step 3: Add iOS platform**

```bash
cd frontend && npx cap add ios
```

- [ ] **Step 4: Add Android platform**

```bash
cd frontend && npx cap add android
```

- [ ] **Step 5: Sync web assets to native projects**

```bash
cd frontend && npx cap sync
```

- [ ] **Step 6: Update .gitignore**

Add to `frontend/.gitignore`:

```
# Capacitor build artifacts (but track ios/ and android/ directories)
ios/App/App/public/
android/app/src/main/assets/public/
```

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/ios/ frontend/android/ frontend/.gitignore
git commit -m "feat: add iOS and Android native projects via Capacitor"
```

---

### Task 4: Create platform detection utility

**Files:**
- Create: `frontend/src/lib/native.ts`

- [ ] **Step 1: Write platform detection module**

Create `frontend/src/lib/native.ts`:

```ts
import { Capacitor } from "@capacitor/core";

export function isNativePlatform(): boolean {
  return Capacitor.isNativePlatform();
}

export function getPlatform(): "ios" | "android" | "web" {
  return Capacitor.getPlatform() as "ios" | "android" | "web";
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/native.ts
git commit -m "feat: add platform detection utility"
```

---

## Chunk 2: Auth Adaptation for Native

### Task 5: Return JWT tokens in login response body

The backend's `CookieJWTAuthentication` already supports `Authorization: Bearer` headers. But login endpoints only set httpOnly cookies — they don't return tokens in the response body. Native apps need the tokens to store them locally.

**Files:**
- Modify: `backend/accounts/services.py` (add function to return tokens in response data)
- Modify: `backend/accounts/views.py` (include tokens in login/register/social auth responses)
- Test: `backend/accounts/tests/test_auth_tokens.py`

- [ ] **Step 1: Write failing test for token in login response**

Create `backend/accounts/tests/test_auth_tokens.py`:

```python
import pytest
from django.test import TestCase
from rest_framework.test import APIClient


class TokenInResponseTest(TestCase):
    def setUp(self):
        from accounts.models import User
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )

    def test_login_returns_tokens_in_body(self):
        response = self.client.post("/api/auth/login/", {
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert response.status_code == 200
        assert "access_token" in response.data
        assert "refresh_token" in response.data
        assert isinstance(response.data["access_token"], str)
        assert isinstance(response.data["refresh_token"], str)

    def test_register_returns_tokens_in_body(self):
        response = self.client.post("/api/auth/register/", {
            "email": "new@example.com",
            "password": "newpass123",
            "first_name": "Test",
            "last_name": "User",
        })
        assert response.status_code == 201
        assert "access_token" in response.data
        assert "refresh_token" in response.data

    def test_refresh_returns_new_access_token(self):
        login = self.client.post("/api/auth/login/", {
            "email": "test@example.com",
            "password": "testpass123",
        })
        refresh_token = login.data["refresh_token"]
        response = self.client.post("/api/auth/refresh/", {
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        assert "access_token" in response.data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest accounts/tests/test_auth_tokens.py -v
```

Expected: FAIL — `access_token` not in response.data.

- [ ] **Step 3: Add token-returning helper to services.py**

In `backend/accounts/services.py`, add a function that includes tokens in response data:

```python
def set_auth_cookies_and_tokens(response: Response, user: User) -> Response:
    """Set auth cookies AND include tokens in response body."""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token_str = str(refresh)

    # Set cookies (for web)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path="/",
        max_age=settings.SIMPLE_JWT.get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=15)).total_seconds(),
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_str,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
        path="/api/auth/refresh/",
        max_age=settings.SIMPLE_JWT.get("REFRESH_TOKEN_LIFETIME", timedelta(days=7)).total_seconds(),
    )

    # Include tokens in body (for native)
    if isinstance(response.data, dict):
        response.data["access_token"] = access_token
        response.data["refresh_token"] = refresh_token_str

    return response
```

- [ ] **Step 4: Update login/register/social auth views to use new helper**

In `backend/accounts/views.py`, replace calls to `set_auth_cookies()` with `set_auth_cookies_and_tokens()` in:
- `LoginView.post()`
- `RegisterView.post()`
- `GoogleAuthView.post()`
- `AppleAuthView.post()`

Also update `RefreshView.post()` to:
1. Read the refresh token from **either** `request.COOKIES.get("refresh_token")` or `request.data.get("refresh_token")` (falling back from cookie to body). This is critical — native clients don't have cookies and will send the refresh token in the request body.
2. Return the new access token (and refresh token) in the response body.

```python
def post(self, request):
    refresh_token = request.COOKIES.get("refresh_token") or request.data.get("refresh_token")
    if not refresh_token:
        return Response(
            {"detail": "Refresh token not found."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    # ... rest of existing logic ...
```

- [ ] **Step 5: Update WsTokenView for native**

The existing `WsTokenView` reads the access token from cookies, which won't work on native. Update it to also check the `Authorization` header:

In `backend/accounts/views.py`, modify `WsTokenView.get()`:

```python
def get(self, request):
    # Try cookie first (web), then use the auth token from header (native)
    token = request.COOKIES.get("access_token", "")
    if not token:
        # On native, the request is already authenticated via Bearer token.
        # The auth middleware has validated it, so we can re-issue it.
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    if not token:
        return Response(
            {"detail": "No access token found."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response({"token": token})
```

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest accounts/tests/test_auth_tokens.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 7: Run existing auth tests to check for regressions**

```bash
cd backend && python -m pytest accounts/ -v
```

Expected: all existing tests still PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/accounts/services.py backend/accounts/views.py backend/accounts/tests/test_auth_tokens.py
git commit -m "feat: return JWT tokens in login/register response body for native auth"
```

---

### Task 6: Make frontend apiFetch platform-aware

On native platforms, `apiFetch` should use `Authorization: Bearer` headers instead of cookies. Tokens are stored in `@capacitor/preferences`.

**Files:**
- Install: `@capacitor/preferences`
- Create: `frontend/src/lib/token-storage.ts` (token storage using Capacitor Preferences)
- Modify: `frontend/src/lib/api.ts` (use Bearer auth on native)
- Modify: `frontend/src/stores/auth-store.ts` (store tokens on native login)

- [ ] **Step 1: Install @capacitor/preferences**

```bash
cd frontend && yarn add @capacitor/preferences
```

- [ ] **Step 2: Create token storage module**

Create `frontend/src/lib/token-storage.ts`:

```ts
import { Preferences } from "@capacitor/preferences";
import { isNativePlatform } from "./native";

const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export async function getAccessToken(): Promise<string | null> {
  if (!isNativePlatform()) return null;
  const { value } = await Preferences.get({ key: ACCESS_TOKEN_KEY });
  return value;
}

export async function getRefreshToken(): Promise<string | null> {
  if (!isNativePlatform()) return null;
  const { value } = await Preferences.get({ key: REFRESH_TOKEN_KEY });
  return value;
}

export async function setTokens(accessToken: string, refreshToken: string): Promise<void> {
  if (!isNativePlatform()) return;
  await Preferences.set({ key: ACCESS_TOKEN_KEY, value: accessToken });
  await Preferences.set({ key: REFRESH_TOKEN_KEY, value: refreshToken });
}

export async function clearTokens(): Promise<void> {
  if (!isNativePlatform()) return;
  await Preferences.remove({ key: ACCESS_TOKEN_KEY });
  await Preferences.remove({ key: REFRESH_TOKEN_KEY });
}
```

- [ ] **Step 3: Modify apiFetch to use Bearer auth on native**

In `frontend/src/lib/api.ts`, update `apiFetch`:

1. Import `isNativePlatform` and `getAccessToken`/`getRefreshToken`/`setTokens`/`clearTokens` from the new modules
2. Before making the fetch call, if `isNativePlatform()`:
   - Get the access token from storage
   - Add `Authorization: Bearer ${token}` header
   - Skip CSRF token logic
   - Remove `credentials: "include"` (not needed for Bearer auth)
3. On 401, if native:
   - Get the refresh token from storage
   - Send it as `{ refresh_token }` in the refresh request body (with `Authorization: Bearer ${refreshToken}` header)
   - Store the new tokens on success
   - Clear tokens on failure

The key change in `apiFetch`:

```ts
import { isNativePlatform } from "./native";
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from "./token-storage";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const url = `${API_URL}${path}`;
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  if (isNativePlatform()) {
    // Native: Bearer token auth
    const token = await getAccessToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  } else {
    // Web: Cookie + CSRF auth
    const csrfToken = getCsrfToken();
    if (csrfToken && !["GET", "HEAD"].includes((options.method || "GET").toUpperCase())) {
      headers.set("X-CSRFToken", csrfToken);
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    ...(isNativePlatform() ? {} : { credentials: "include" }),
  });

  // ... rest of response handling ...
}
```

Also update `tryRefresh()` for native. The existing function relies on cookies — native needs to send the refresh token in the body:

```ts
async function tryRefresh(): Promise<boolean> {
  try {
    if (isNativePlatform()) {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return false;
      const resp = await fetch(`${API_URL}/api/auth/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data.access_token && data.refresh_token) {
          await setTokens(data.access_token, data.refresh_token);
        }
        return true;
      }
      await clearTokens();
      return false;
    } else {
      const resp = await fetch(`${API_URL}/api/auth/refresh/`, {
        method: "POST",
        credentials: "include",
      });
      return resp.ok;
    }
  } catch {
    return false;
  }
}
```

- [ ] **Step 4: Update auth store to save tokens on login (native)**

In `frontend/src/stores/auth-store.ts`, after successful login/register/social auth calls, save the returned tokens:

```ts
import { setTokens, clearTokens } from "@/lib/token-storage";
import { isNativePlatform } from "@/lib/native";

// In login(), after successful apiFetch:
if (isNativePlatform() && data.access_token && data.refresh_token) {
  await setTokens(data.access_token, data.refresh_token);
}

// In logout() and clearAuth():
if (isNativePlatform()) {
  await clearTokens();
}
```

Apply the same pattern to `register()`, `googleLogin()`, and `appleLogin()`.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/src/lib/token-storage.ts frontend/src/lib/api.ts frontend/src/stores/auth-store.ts
git commit -m "feat: platform-aware auth — Bearer tokens on native, cookies on web"
```

---

### Task 7: Add native OAuth plugins for Google and Apple sign-in

On native platforms, the web-based Google/Apple sign-in scripts won't work (origin restrictions). Use native Capacitor plugins instead.

**Files:**
- Install: `@codetrix-studio/capacitor-google-auth`
- Modify: `frontend/src/components/SocialLoginButtons.tsx` (use native plugin on mobile)
- Modify: `frontend/src/app/layout.tsx` (skip loading web OAuth scripts on native)

- [ ] **Step 1: Install native Google auth plugin**

```bash
cd frontend && yarn add @codetrix-studio/capacitor-google-auth
```

Note: Apple Sign-In is built into iOS via `SignInWithApple` from `@capacitor-community/apple-sign-in`. Install if needed:

```bash
cd frontend && yarn add @capacitor-community/apple-sign-in
```

- [ ] **Step 2: Update SocialLoginButtons for platform detection**

In `frontend/src/components/SocialLoginButtons.tsx`, add platform-specific logic:

```tsx
import { isNativePlatform } from "@/lib/native";

// For Google:
if (isNativePlatform()) {
  const { GoogleAuth } = await import("@codetrix-studio/capacitor-google-auth");
  const result = await GoogleAuth.signIn();
  // result.authentication.idToken is the same format the backend expects
  await googleLogin(result.authentication.idToken, linkOrderId);
} else {
  // existing web Google Sign-In logic
}

// For Apple (iOS only):
if (isNativePlatform() && getPlatform() === "ios") {
  const { SignInWithApple } = await import("@capacitor-community/apple-sign-in");
  const result = await SignInWithApple.authorize({
    options: { requestedScopes: ["fullName", "email"] },
  });
  await appleLogin(result.response.identityToken, /* name */, linkOrderId);
} else {
  // existing web Apple Sign-In logic (hidden on Android native)
}
```

- [ ] **Step 3: Skip web OAuth scripts on native in layout.tsx**

In `frontend/src/app/layout.tsx`, the Google Sign-In and Apple ID scripts are loaded via `<Script strategy="lazyOnload">`. These are only needed on web. Wrap them conditionally:

Since `layout.tsx` is a server component, we can't use `isNativePlatform()` directly. Instead, create a client component wrapper:

Create `frontend/src/components/WebOnlyScripts.tsx`:

```tsx
"use client";

import Script from "next/script";
import { isNativePlatform } from "@/lib/native";

export function WebOnlyScripts() {
  if (isNativePlatform()) return null;

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="lazyOnload"
      />
      <Script
        src="https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js"
        strategy="lazyOnload"
      />
    </>
  );
}
```

Replace the inline `<Script>` tags in `layout.tsx` with `<WebOnlyScripts />`.

- [ ] **Step 4: Sync native projects**

```bash
cd frontend && npx cap sync
```

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/src/components/SocialLoginButtons.tsx frontend/src/components/WebOnlyScripts.tsx frontend/src/app/layout.tsx
git commit -m "feat: native OAuth plugins for Google and Apple sign-in on mobile"
```

---

## Chunk 3: Push Notifications (Backend)

### Task 8: Create notifications Django app and DeviceToken model

**Files:**
- Create: `backend/notifications/__init__.py`
- Create: `backend/notifications/apps.py`
- Create: `backend/notifications/models.py`
- Create: `backend/notifications/admin.py`
- Modify: `backend/config/settings.py` (add to INSTALLED_APPS)
- Test: `backend/notifications/tests/__init__.py`
- Test: `backend/notifications/tests/test_models.py`

- [ ] **Step 1: Write failing test for DeviceToken model**

Create `backend/notifications/tests/__init__.py` (empty file).

Create `backend/notifications/tests/test_models.py`:

```python
import pytest
from django.test import TestCase
from django.db import IntegrityError
from accounts.models import User
from notifications.models import DeviceToken


class DeviceTokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_create_device_token_with_user(self):
        token = DeviceToken.objects.create(
            user=self.user,
            token="fcm-token-123",
            platform="ios",
        )
        assert token.is_active is True
        assert token.user == self.user
        assert token.order is None

    def test_create_device_token_with_order(self):
        from orders.models import Order
        from restaurants.models import Restaurant

        restaurant = Restaurant.objects.create(
            name="Test", slug="test", owner=self.user
        )
        order = Order.objects.create(restaurant=restaurant)
        token = DeviceToken.objects.create(
            order=order,
            token="fcm-token-456",
            platform="android",
        )
        assert token.order == order
        assert token.user is None

    def test_token_unique(self):
        DeviceToken.objects.create(
            user=self.user, token="same-token", platform="ios"
        )
        with pytest.raises(IntegrityError):
            DeviceToken.objects.create(
                user=self.user, token="same-token", platform="android"
            )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest notifications/tests/test_models.py -v
```

Expected: FAIL — `notifications` module not found.

- [ ] **Step 3: Create the notifications app**

Create `backend/notifications/__init__.py` (empty).

Create `backend/notifications/apps.py`:

```python
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
```

Create `backend/notifications/models.py`:

```python
from django.conf import settings
from django.db import models


class DeviceToken(models.Model):
    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        null=True,
        blank=True,
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="device_tokens",
        null=True,
        blank=True,
    )
    token = models.TextField(unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        owner = self.user.email if self.user else f"order:{self.order_id}"
        return f"{owner} ({self.platform})"
```

Create `backend/notifications/admin.py`:

```python
from django.contrib import admin
from .models import DeviceToken


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ["__str__", "platform", "is_active", "created_at"]
    list_filter = ["platform", "is_active"]
    search_fields = ["token", "user__email"]
```

- [ ] **Step 4: Add to INSTALLED_APPS and migrate**

In `backend/config/settings.py`, add `"notifications"` to `INSTALLED_APPS`.

```bash
cd backend && python manage.py makemigrations notifications && python manage.py migrate
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest notifications/tests/test_models.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/notifications/ backend/config/settings.py
git commit -m "feat: add notifications app with DeviceToken model"
```

---

### Task 9: Add device registration API endpoint

**Files:**
- Create: `backend/notifications/serializers.py`
- Create: `backend/notifications/views.py`
- Create: `backend/notifications/urls.py`
- Modify: `backend/config/urls.py` (include notifications URLs)
- Test: `backend/notifications/tests/test_views.py`

- [ ] **Step 1: Write failing test for device registration**

Create `backend/notifications/tests/test_views.py`:

```python
from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User
from notifications.models import DeviceToken


class DeviceRegisterViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_register_device_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/devices/register/", {
            "token": "fcm-token-abc",
            "platform": "ios",
        })
        assert response.status_code == 201
        token = DeviceToken.objects.get(token="fcm-token-abc")
        assert token.user == self.user
        assert token.platform == "ios"
        assert token.is_active is True

    def test_register_device_unauthenticated_with_order(self):
        from orders.models import Order
        from restaurants.models import Restaurant

        restaurant = Restaurant.objects.create(
            name="Test", slug="test", owner=self.user
        )
        order = Order.objects.create(restaurant=restaurant)
        response = self.client.post("/api/devices/register/", {
            "token": "fcm-token-def",
            "platform": "android",
            "order_id": str(order.id),
        })
        assert response.status_code == 201
        token = DeviceToken.objects.get(token="fcm-token-def")
        assert token.order == order

    def test_register_device_updates_existing(self):
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/devices/register/", {
            "token": "fcm-token-abc",
            "platform": "ios",
        })
        # Register same token again — should update, not duplicate
        response = self.client.post("/api/devices/register/", {
            "token": "fcm-token-abc",
            "platform": "ios",
        })
        assert response.status_code == 200
        assert DeviceToken.objects.filter(token="fcm-token-abc").count() == 1

    def test_register_device_reactivates_inactive(self):
        self.client.force_authenticate(user=self.user)
        dt = DeviceToken.objects.create(
            user=self.user, token="old-token", platform="ios", is_active=False
        )
        response = self.client.post("/api/devices/register/", {
            "token": "old-token",
            "platform": "ios",
        })
        assert response.status_code == 200
        dt.refresh_from_db()
        assert dt.is_active is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest notifications/tests/test_views.py -v
```

Expected: FAIL — 404 (URL not configured).

- [ ] **Step 3: Create serializer, view, and URLs**

Create `backend/notifications/serializers.py`:

```python
from rest_framework import serializers
from .models import DeviceToken


class DeviceTokenSerializer(serializers.Serializer):
    token = serializers.CharField()
    platform = serializers.ChoiceField(choices=DeviceToken.Platform.choices)
    order_id = serializers.UUIDField(required=False)
```

Create `backend/notifications/views.py`:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeviceToken
from .serializers import DeviceTokenSerializer


class DeviceRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_value = serializer.validated_data["token"]
        platform = serializer.validated_data["platform"]
        order_id = serializer.validated_data.get("order_id")

        defaults = {
            "platform": platform,
            "is_active": True,
        }

        if request.user.is_authenticated:
            defaults["user"] = request.user
        elif order_id:
            from orders.models import Order
            defaults["order"] = Order.objects.get(id=order_id)

        device_token, created = DeviceToken.objects.update_or_create(
            token=token_value,
            defaults=defaults,
        )

        return Response(
            {"status": "registered"},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
```

Create `backend/notifications/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    path("devices/register/", views.DeviceRegisterView.as_view(), name="device-register"),
]
```

- [ ] **Step 4: Include notifications URLs in config**

In `backend/config/urls.py`, add:

```python
path("api/", include("notifications.urls")),
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest notifications/tests/test_views.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/notifications/ backend/config/urls.py
git commit -m "feat: add device token registration endpoint"
```

---

### Task 10: Add Firebase push notification sending service

**Files:**
- Install: `firebase-admin` in pyproject.toml
- Create: `backend/notifications/services.py`
- Modify: `backend/config/settings.py` (Firebase config)
- Modify: `backend/orders/broadcast.py` (trigger push after WebSocket broadcast)
- Test: `backend/notifications/tests/test_services.py`

- [ ] **Step 1: Install firebase-admin**

```bash
cd backend && poetry add firebase-admin
```

- [ ] **Step 2: Write failing test for push notification service**

Create `backend/notifications/tests/test_services.py`:

```python
from unittest.mock import patch, MagicMock
from django.test import TestCase
from accounts.models import User
from notifications.models import DeviceToken
from notifications.services import send_push_notification


class PushNotificationServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.device = DeviceToken.objects.create(
            user=self.user, token="fcm-token-123", platform="ios"
        )

    @patch("notifications.services.messaging")
    def test_send_push_to_user(self, mock_messaging):
        mock_messaging.send.return_value = "projects/test/messages/123"
        result = send_push_notification(
            user=self.user,
            title="Order Ready",
            body="Your order #42 is ready for pickup",
        )
        assert result == 1
        mock_messaging.send.assert_called_once()
        call_args = mock_messaging.send.call_args[0][0]
        assert call_args.token == "fcm-token-123"
        assert call_args.notification.title == "Order Ready"

    @patch("notifications.services.messaging")
    def test_deactivates_invalid_token(self, mock_messaging):
        from firebase_admin.messaging import UnregisteredError
        mock_messaging.send.side_effect = UnregisteredError("invalid")
        send_push_notification(
            user=self.user,
            title="Test",
            body="Test",
        )
        self.device.refresh_from_db()
        assert self.device.is_active is False

    @patch("notifications.services.messaging")
    def test_skips_inactive_tokens(self, mock_messaging):
        self.device.is_active = False
        self.device.save()
        result = send_push_notification(
            user=self.user, title="Test", body="Test"
        )
        assert result == 0
        mock_messaging.send.assert_not_called()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && python -m pytest notifications/tests/test_services.py -v
```

Expected: FAIL — `notifications.services` not found.

- [ ] **Step 4: Create push notification service**

Create `backend/notifications/services.py`:

```python
import logging

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

from .models import DeviceToken

logger = logging.getLogger(__name__)

# Initialize Firebase app once
if not firebase_admin._apps:
    if settings.FIREBASE_CREDENTIALS:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    else:
        logger.warning("FIREBASE_CREDENTIALS not set — push notifications disabled")


def send_push_notification(
    user=None,
    order=None,
    title: str = "",
    body: str = "",
    data: dict | None = None,
) -> int:
    """Send push notification to all active devices for a user or order.

    Returns the number of successfully sent notifications.
    """
    if not firebase_admin._apps:
        logger.warning("Firebase not initialized, skipping push")
        return 0

    tokens = DeviceToken.objects.filter(is_active=True)
    if user:
        tokens = tokens.filter(user=user)
    elif order:
        tokens = tokens.filter(order=order)
    else:
        return 0

    sent = 0
    for device_token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=device_token.token,
        )
        try:
            messaging.send(message)
            sent += 1
        except messaging.UnregisteredError:
            logger.info(f"Deactivating unregistered token: {device_token.token[:8]}...")
            device_token.is_active = False
            device_token.save(update_fields=["is_active", "updated_at"])
        except Exception:
            logger.exception(f"Failed to send push to {device_token.token[:8]}...")

    return sent
```

- [ ] **Step 5: Add Firebase config to settings.py**

In `backend/config/settings.py`, add:

```python
import json

# Firebase (push notifications)
_firebase_creds = config("FIREBASE_CREDENTIALS_JSON", default="")
FIREBASE_CREDENTIALS = json.loads(_firebase_creds) if _firebase_creds else None
```

The `FIREBASE_CREDENTIALS_JSON` env var should contain the JSON service account key as a string.

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest notifications/tests/test_services.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Hook push notifications into order broadcasts**

In `backend/orders/broadcast.py`, after the existing WebSocket broadcasts, add push notification calls:

```python
from notifications.services import send_push_notification


def broadcast_order_to_kitchen(order):
    # ... existing WebSocket broadcast code ...

    # Push notification to restaurant staff
    send_push_notification(
        user=order.restaurant.owner,
        title="New Order",
        body=f"New order #{order.order_number} received",
        data={"type": "new_order", "order_id": str(order.id)},
    )


def broadcast_order_status_to_customer(order):
    """New function: push notification when order status changes.
    Call this from KitchenOrderUpdateView after status update."""
    # Existing broadcast_order_to_customer handles WebSocket.
    # Add push notification for "ready" status.
    if order.status == "ready":
        send_push_notification(
            user=order.user if order.user else None,
            order=order if not order.user else None,
            title="Order Ready!",
            body=f"Your order from {order.restaurant.name} is ready for pickup",
            data={"type": "order_ready", "order_id": str(order.id)},
        )
```

- [ ] **Step 8: Run full test suite**

```bash
cd backend && python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/notifications/services.py backend/notifications/tests/test_services.py backend/config/settings.py backend/orders/broadcast.py backend/pyproject.toml backend/poetry.lock
git commit -m "feat: add Firebase push notification service and hook into order events"
```

---

## Chunk 4: Push Notifications & QR Scanning (Frontend)

### Task 11: Add push notification hook

**Files:**
- Install: `@capacitor/push-notifications`
- Create: `frontend/src/hooks/use-push-notifications.ts`

- [ ] **Step 1: Install plugin**

```bash
cd frontend && yarn add @capacitor/push-notifications
```

- [ ] **Step 2: Create push notification hook**

Create `frontend/src/hooks/use-push-notifications.ts`:

```ts
"use client";

import { useEffect, useRef } from "react";
import { isNativePlatform } from "@/lib/native";

export function usePushNotifications() {
  const registered = useRef(false);

  useEffect(() => {
    if (!isNativePlatform() || registered.current) return;

    async function setup() {
      const { PushNotifications } = await import("@capacitor/push-notifications");

      const permission = await PushNotifications.requestPermissions();
      if (permission.receive !== "granted") return;

      await PushNotifications.register();

      PushNotifications.addListener("registration", async (token) => {
        const { getPlatform } = await import("@/lib/native");
        const { apiFetch } = await import("@/lib/api");
        try {
          await apiFetch("/devices/register/", {
            method: "POST",
            body: JSON.stringify({
              token: token.value,
              platform: getPlatform(),
            }),
          });
        } catch (e) {
          console.error("Failed to register device token:", e);
        }
      });

      PushNotifications.addListener("pushNotificationReceived", (notification) => {
        console.log("Push received:", notification);
      });

      PushNotifications.addListener("pushNotificationActionPerformed", (action) => {
        const data = action.notification.data;
        if (data?.order_id) {
          // Navigate to order — the exact route depends on available context.
          // For now, use a generic approach; refine once order routes are confirmed.
          console.log("Push action:", data);
        }
      });

      registered.current = true;
    }

    setup();
  }, []);
}
```

- [ ] **Step 3: Add hook to root layout**

Create `frontend/src/components/NativeInitializer.tsx`:

```tsx
"use client";

import { usePushNotifications } from "@/hooks/use-push-notifications";

export function NativeInitializer() {
  usePushNotifications();
  return null;
}
```

Add `<NativeInitializer />` to the root layout providers in `frontend/src/app/layout.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/src/hooks/use-push-notifications.ts frontend/src/components/NativeInitializer.tsx frontend/src/app/layout.tsx
git commit -m "feat: add push notification registration hook for native"
```

---

### Task 12: Add native QR code scanning hook

**Files:**
- Install: `@capacitor-mlkit/barcode-scanning`
- Create: `frontend/src/hooks/use-native-camera.ts`

- [ ] **Step 1: Install plugin**

```bash
cd frontend && yarn add @capacitor-mlkit/barcode-scanning
```

- [ ] **Step 2: Create QR scanning hook**

Create `frontend/src/hooks/use-native-camera.ts`:

```ts
"use client";

import { useCallback, useState } from "react";
import { isNativePlatform } from "@/lib/native";

export function useNativeCamera() {
  const [isScanning, setIsScanning] = useState(false);
  const isAvailable = isNativePlatform();

  const scan = useCallback(async (): Promise<string | null> => {
    if (!isNativePlatform()) return null;

    const { BarcodeScanner, BarcodeFormat } = await import(
      "@capacitor-mlkit/barcode-scanning"
    );

    const permission = await BarcodeScanner.requestPermissions();
    if (permission.camera !== "granted") return null;

    setIsScanning(true);
    try {
      const { barcodes } = await BarcodeScanner.scan({
        formats: [BarcodeFormat.QrCode],
      });

      if (barcodes.length > 0 && barcodes[0].rawValue) {
        return barcodes[0].rawValue;
      }
      return null;
    } finally {
      setIsScanning(false);
    }
  }, []);

  return { scan, isAvailable, isScanning };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/src/hooks/use-native-camera.ts
git commit -m "feat: add native QR code scanning hook"
```

---

### Task 13: Add status bar and safe area handling

**Files:**
- Install: `@capacitor/status-bar`
- Modify: `frontend/src/components/NativeInitializer.tsx` (configure status bar)
- Modify: `frontend/src/app/globals.css` (safe area padding)

- [ ] **Step 1: Install plugin**

```bash
cd frontend && yarn add @capacitor/status-bar
```

- [ ] **Step 2: Configure status bar in NativeInitializer**

Update `frontend/src/components/NativeInitializer.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { usePushNotifications } from "@/hooks/use-push-notifications";
import { isNativePlatform } from "@/lib/native";

export function NativeInitializer() {
  usePushNotifications();

  useEffect(() => {
    if (!isNativePlatform()) return;

    async function configureStatusBar() {
      const { StatusBar, Style } = await import("@capacitor/status-bar");
      await StatusBar.setStyle({ style: Style.Default });
      await StatusBar.setOverlaysWebView({ overlay: true });
    }

    configureStatusBar();
  }, []);

  return null;
}
```

- [ ] **Step 3: Add safe area CSS**

In `frontend/src/app/globals.css`, add:

```css
/* Safe area insets for native app (notch, Dynamic Island, status bar) */
body {
  padding-top: env(safe-area-inset-top);
  padding-bottom: env(safe-area-inset-bottom);
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/src/components/NativeInitializer.tsx frontend/src/app/globals.css
git commit -m "feat: add status bar config and safe area CSS for native"
```

---

## Chunk 5: WebSocket Reconnection & Deep Linking

### Task 14: Add app lifecycle-aware WebSocket reconnection

**Files:**
- Install: `@capacitor/app`
- Modify: `frontend/src/hooks/use-websocket.ts` (reconnect on app resume)

- [ ] **Step 1: Install @capacitor/app plugin**

```bash
cd frontend && yarn add @capacitor/app
```

- [ ] **Step 2: Add foreground reconnection to use-websocket.ts**

In `frontend/src/hooks/use-websocket.ts`, add app lifecycle handling:

```ts
import { isNativePlatform } from "@/lib/native";
import type { PluginListenerHandle } from "@capacitor/core";

// Inside the useEffect that manages the WebSocket connection, add:
let appStateListener: PluginListenerHandle | null = null;

if (isNativePlatform()) {
  import("@capacitor/app").then(({ App }) => {
    App.addListener("appStateChange", ({ isActive }) => {
      if (isActive && enabled) {
        // Force reconnect when app returns to foreground
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          connectWebSocket();
        }
      }
    }).then((handle) => {
      appStateListener = handle;
    });
  });
}

// In the cleanup function, remove ONLY this listener (not all App listeners):
return () => {
  // ... existing cleanup ...
  appStateListener?.remove();
};
```

Integrate this into the existing `useEffect` structure — don't create a separate effect. Use the `PluginListenerHandle` returned by `addListener` to clean up only this specific listener, not `App.removeAllListeners()` which would break deep link listeners.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/src/hooks/use-websocket.ts
git commit -m "feat: reconnect WebSocket on app foreground resume"
```

---

### Task 15: Configure deep linking

**Files:**
- Modify: `frontend/android/app/src/main/AndroidManifest.xml` (intent filters)
- Modify: `frontend/ios/App/App/Info.plist` (URL types)
- Create: `frontend/src/components/DeepLinkHandler.tsx` (handle incoming deep links)
- Modify: `frontend/src/components/NativeInitializer.tsx` (include deep link handler)

- [ ] **Step 1: Add deep link handler component**

Create `frontend/src/components/DeepLinkHandler.tsx`:

```tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isNativePlatform } from "@/lib/native";

export function DeepLinkHandler() {
  const router = useRouter();

  useEffect(() => {
    if (!isNativePlatform()) return;

    async function setupDeepLinks() {
      const { App } = await import("@capacitor/app");

      App.addListener("appUrlOpen", (event) => {
        // Extract path from URL: https://yourdomain.com/order/slug/tableId
        try {
          const url = new URL(event.url);
          const path = url.pathname;
          if (path.startsWith("/order/")) {
            router.push(path);
          }
        } catch {
          console.error("Invalid deep link URL:", event.url);
        }
      });
    }

    setupDeepLinks();
  }, [router]);

  return null;
}
```

- [ ] **Step 2: Add DeepLinkHandler to NativeInitializer**

In `frontend/src/components/NativeInitializer.tsx`, add:

```tsx
import { DeepLinkHandler } from "./DeepLinkHandler";

export function NativeInitializer() {
  usePushNotifications();
  // ... existing status bar code ...
  return <DeepLinkHandler />;
}
```

- [ ] **Step 3: Add Android intent filters**

In `frontend/android/app/src/main/AndroidManifest.xml`, add inside the main `<activity>` tag:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" android:host="yourdomain.com" android:pathPrefix="/order/" />
</intent-filter>
```

- [ ] **Step 4: Add iOS Associated Domains**

In `frontend/ios/App/App/Info.plist`, or via Xcode:
- Add `Associated Domains` capability
- Add `applinks:yourdomain.com`

Note: The `apple-app-site-association` file must be hosted on the web server at `https://yourdomain.com/.well-known/apple-app-site-association`. This is a deployment task, not a code task.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DeepLinkHandler.tsx frontend/src/components/NativeInitializer.tsx frontend/android/app/src/main/AndroidManifest.xml frontend/ios/App/App/Info.plist
git commit -m "feat: add deep link handling for order URLs"
```

---

## Chunk 6: Build Verification & Deployment Guide

### Task 16: Verify mobile build end-to-end

- [ ] **Step 1: Clean and rebuild**

```bash
cd frontend && rm -rf out/ && yarn build:mobile
```

Expected: build succeeds, `out/` directory created.

- [ ] **Step 2: Sync to native projects**

```bash
cd frontend && npx cap sync
```

Expected: web assets copied to both iOS and Android projects.

- [ ] **Step 3: Verify iOS build (if on macOS with Xcode)**

```bash
cd frontend && npx cap open ios
```

In Xcode: select a simulator, press Cmd+R to build and run. Verify the app loads and shows the home page.

- [ ] **Step 4: Verify Android build (if Android Studio installed)**

```bash
cd frontend && npx cap open android
```

In Android Studio: select an emulator, click Run. Verify the app loads.

- [ ] **Step 5: Run backend tests**

```bash
cd backend && python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit any remaining changes**

```bash
git add -A && git status
```

Review and commit if needed.

---

### Task 17: Create deployment guide

**Files:**
- Create: `docs/MOBILE_DEPLOYMENT.md`

- [ ] **Step 1: Write deployment guide**

Create `docs/MOBILE_DEPLOYMENT.md` covering:

1. **Prerequisites** — Xcode (iOS), Android Studio (Android), developer accounts
2. **Developer Account Setup**
   - Apple Developer Program enrollment ($99/year)
   - Google Play Developer registration ($25 one-time)
3. **Firebase Setup**
   - Create Firebase project
   - Add iOS app (download `GoogleService-Info.plist`)
   - Add Android app (download `google-services.json`)
   - Upload APNs key for iOS push
   - Generate service account key for backend
4. **App Icons & Splash Screens**
   - Place source images: `frontend/resources/icon.png` (1024x1024), `frontend/resources/splash.png` (2732x2732)
   - Run: `npx @capacitor/assets generate`
5. **Building for iOS**
   - `yarn build:mobile && npx cap sync`
   - Open in Xcode, configure signing
   - Add `GoogleService-Info.plist` to the Xcode project
   - Add privacy descriptions to `Info.plist`
   - Archive and upload to App Store Connect
6. **Building for Android**
   - `yarn build:mobile && npx cap sync`
   - Open in Android Studio
   - Add `google-services.json` to `android/app/`
   - Create signing keystore
   - Generate signed AAB
   - Upload to Google Play Console
7. **Deep Linking Setup**
   - Host `apple-app-site-association` at `/.well-known/`
   - Host `assetlinks.json` at `/.well-known/`
8. **Environment Variables**
   - `FIREBASE_CREDENTIALS_JSON` — backend service account key
   - `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` — already exists
   - Native Google Auth client IDs in Capacitor plugin config

- [ ] **Step 2: Commit**

```bash
git add docs/MOBILE_DEPLOYMENT.md
git commit -m "docs: add mobile deployment guide for iOS and Android"
```
