# Stripe Connect Payment Setup Onboarding Step Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mandatory Stripe Connect payment setup step to the restaurant owner onboarding flow, with redirect to Stripe's hosted form and return handling.

**Architecture:** Backend gets two new subscription-free views for initiating Stripe Connect and checking status. `ConnectService.create_onboarding_link` becomes configurable for return/refresh URLs. Frontend gets a new `PaymentSetupStep` component inserted between menu-upload and pos-vendor in both onboarding flows, with `sessionStorage` for state persistence across the Stripe redirect.

**Tech Stack:** Django REST Framework, Stripe Connect API, Next.js 14, TanStack Query, Tailwind CSS + shadcn/ui

**Spec:** `docs/superpowers/specs/2026-04-04-stripe-connect-onboarding-step-design.md`

---

## Chunk 1: Backend — Configurable URLs and Onboarding-Safe Views

### Task 1: Make ConnectService.create_onboarding_link accept optional URLs

**Files:**
- Modify: `backend/restaurants/services/connect_service.py`
- Test: `backend/restaurants/tests/test_connect_views.py`

- [ ] **Step 1: Write test for custom return/refresh URLs**

Add to `backend/restaurants/tests/test_connect_views.py` at the end of the file:

```python
@pytest.mark.django_db
class TestConnectServiceCustomURLs:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_custom_return_url_passed_to_stripe(self, mock_link, mock_create, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        from restaurants.services.connect_service import ConnectService
        result = ConnectService.create_onboarding_link(
            restaurant,
            return_url="http://localhost:3000/account/onboarding?stripe_return=true",
            refresh_url="http://localhost:3000/account/onboarding?stripe_refresh=true",
        )

        assert result["url"] == "https://connect.stripe.com/setup/abc"
        call_kwargs = mock_link.call_args[1]
        assert "stripe_return=true" in call_kwargs["return_url"]
        assert "stripe_refresh=true" in call_kwargs["refresh_url"]

    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_default_urls_when_none_provided(self, mock_link, mock_create, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        from restaurants.services.connect_service import ConnectService
        ConnectService.create_onboarding_link(restaurant)

        call_kwargs = mock_link.call_args[1]
        assert "/dashboard/" in call_kwargs["return_url"]
        assert "/dashboard/" in call_kwargs["refresh_url"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py::TestConnectServiceCustomURLs -v`
Expected: FAIL — `create_onboarding_link()` does not accept `return_url`/`refresh_url`.

- [ ] **Step 3: Update ConnectService to accept optional URLs**

Modify `backend/restaurants/services/connect_service.py`. Change the `create_onboarding_link` method signature and body:

```python
    @staticmethod
    def create_onboarding_link(restaurant, return_url=None, refresh_url=None):
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

    if return_url is None:
        return_url = f"{settings.FRONTEND_URL}/dashboard/{restaurant.slug}/connect/complete"
    if refresh_url is None:
        refresh_url = f"{settings.FRONTEND_URL}/dashboard/{restaurant.slug}/connect/refresh"

    account_link = stripe.AccountLink.create(
        account=account.stripe_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return {"url": account_link.url}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py::TestConnectServiceCustomURLs -v`
Expected: PASS

- [ ] **Step 5: Run existing connect tests for regressions**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py -v`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/services/connect_service.py backend/restaurants/tests/test_connect_views.py
git commit -m "feat: make ConnectService.create_onboarding_link accept custom return/refresh URLs"
```

### Task 2: Add onboarding-safe connect views and URLs

**Files:**
- Modify: `backend/restaurants/views.py` (add two new views after `ConnectDashboardView`, around line 300)
- Modify: `backend/restaurants/urls.py` (add two new URL patterns)
- Test: `backend/restaurants/tests/test_connect_views.py`

- [ ] **Step 1: Write failing tests for the new endpoints**

Add to `backend/restaurants/tests/test_connect_views.py`:

```python
@pytest.mark.django_db
class TestOnboardingConnectInitiateView:
    @patch("restaurants.services.connect_service.stripe.Account.create")
    @patch("restaurants.services.connect_service.stripe.AccountLink.create")
    def test_initiate_with_valid_urls(self, mock_link, mock_create, api_client, restaurant):
        mock_create.return_value = MagicMock(id="acct_test123")
        mock_link.return_value = MagicMock(url="https://connect.stripe.com/setup/abc")

        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 200
        assert "url" in response.data

    def test_initiate_rejects_invalid_return_url(self, api_client, restaurant):
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "https://evil.com/steal",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_initiate_rejects_invalid_refresh_url(self, api_client, restaurant):
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "https://evil.com/steal",
            },
            format="json",
        )
        assert response.status_code == 400

    def test_initiate_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 401

    def test_initiate_wrong_owner(self, restaurant):
        other_user = User.objects.create_user(email="other@test.com", password="testpass123")
        client = APIClient()
        client.force_authenticate(user=other_user)
        response = client.post(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-initiate/",
            {
                "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
                "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true",
            },
            format="json",
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestOnboardingConnectStatusView:
    def test_status_no_account(self, api_client, restaurant):
        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 200
        assert response.data["has_account"] is False
        assert response.data["onboarding_complete"] is False

    def test_status_with_complete_account(self, api_client, restaurant):
        ConnectedAccount.objects.create(
            restaurant=restaurant,
            stripe_account_id="acct_test123",
            onboarding_complete=True,
            payouts_enabled=True,
        )
        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 200
        assert response.data["onboarding_complete"] is True

    def test_status_unauthenticated(self, restaurant):
        client = APIClient()
        response = client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 401

    def test_status_wrong_owner(self, restaurant):
        other_user = User.objects.create_user(email="other@test.com", password="testpass123")
        client = APIClient()
        client.force_authenticate(user=other_user)
        response = client.get(
            f"/api/restaurants/{restaurant.slug}/connect/onboarding-status/"
        )
        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py::TestOnboardingConnectInitiateView -v`
Expected: FAIL — views/URLs don't exist.

- [ ] **Step 3: Implement the views**

Add to `backend/restaurants/views.py` after `ConnectDashboardView` (after line 299), before the `from restaurants.models import Table` import:

```python
class OnboardingConnectInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug, owner=request.user)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")

        return_url = request.data.get("return_url", "")
        refresh_url = request.data.get("refresh_url", "")
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")

        if not return_url.startswith(frontend_url) or not refresh_url.startswith(frontend_url):
            return Response(
                {"error": "Invalid return URL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = ConnectService.create_onboarding_link(
            restaurant, return_url=return_url, refresh_url=refresh_url
        )
        return Response(result)


class OnboardingConnectStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        try:
            restaurant = Restaurant.objects.get(slug=slug, owner=request.user)
        except Restaurant.DoesNotExist:
            raise NotFound("Restaurant not found.")

        result = ConnectService.get_connect_status(restaurant)
        return Response(result)
```

Add these imports to the top of `views.py` if not already present:
- `from django.conf import settings` — NOT currently imported, add near line 1
- `from rest_framework.exceptions import NotFound` — currently only used inline in a few methods, add as a top-level import
- `from rest_framework import status` — already imported
- `from restaurants.services.connect_service import ConnectService` — already imported at line 278

- [ ] **Step 4: Add URL patterns**

Add to `backend/restaurants/urls.py` — import the new views and add URL patterns after the existing connect URLs (after line 149):

```python
# In the imports at the top, add:
from restaurants.views import (
    # ... existing imports ...
    OnboardingConnectInitiateView,
    OnboardingConnectStatusView,
)

# Add URL patterns:
path(
    "restaurants/<slug:slug>/connect/onboarding-initiate/",
    OnboardingConnectInitiateView.as_view(),
    name="connect-onboarding-initiate",
),
path(
    "restaurants/<slug:slug>/connect/onboarding-status/",
    OnboardingConnectStatusView.as_view(),
    name="connect-onboarding-status",
),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py::TestOnboardingConnectInitiateView restaurants/tests/test_connect_views.py::TestOnboardingConnectStatusView -v`
Expected: All 8 tests PASS.

- [ ] **Step 6: Run full connect test suite**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py -v`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/restaurants/views.py backend/restaurants/urls.py backend/restaurants/tests/test_connect_views.py
git commit -m "feat: add subscription-free connect views for onboarding flow"
```

---

## Chunk 2: Frontend — API, Hook, and Step Component

### Task 3: Add API functions and hook for connect onboarding

**Files:**
- Modify: `frontend/src/lib/api.ts` (add two functions after the POS integration section, around line 410)
- Create: `frontend/src/hooks/use-connect-onboarding.ts`

- [ ] **Step 1: Add API functions**

Add to `frontend/src/lib/api.ts` after the POS integration section:

```typescript
// ── Connect Onboarding ──
export async function createOnboardingConnectLink(
  slug: string,
  returnUrl: string,
  refreshUrl: string
): Promise<{ url: string }> {
  return apiFetch<{ url: string }>(
    `/api/restaurants/${slug}/connect/onboarding-initiate/`,
    {
      method: "POST",
      body: JSON.stringify({ return_url: returnUrl, refresh_url: refreshUrl }),
    }
  );
}

export async function fetchOnboardingConnectStatus(
  slug: string
): Promise<{
  has_account: boolean;
  onboarding_complete: boolean;
  payouts_enabled: boolean;
  charges_enabled: boolean;
}> {
  return apiFetch(
    `/api/restaurants/${slug}/connect/onboarding-status/`
  );
}
```

- [ ] **Step 2: Create the hook**

Create `frontend/src/hooks/use-connect-onboarding.ts`:

```typescript
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  createOnboardingConnectLink,
  fetchOnboardingConnectStatus,
} from "@/lib/api";

export function useConnectOnboardingLink(slug: string) {
  return useMutation({
    mutationFn: ({
      returnUrl,
      refreshUrl,
    }: {
      returnUrl: string;
      refreshUrl: string;
    }) => createOnboardingConnectLink(slug, returnUrl, refreshUrl),
  });
}

export function useConnectOnboardingStatus(slug: string, enabled: boolean) {
  return useQuery({
    queryKey: ["connect-onboarding-status", slug],
    queryFn: () => fetchOnboardingConnectStatus(slug),
    enabled,
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/use-connect-onboarding.ts
git commit -m "feat: add connect onboarding API functions and hooks"
```

### Task 4: Create PaymentSetupStep component

**Files:**
- Create: `frontend/src/components/onboarding/payment-setup-step.tsx`

- [ ] **Step 1: Create the step component**

Create `frontend/src/components/onboarding/payment-setup-step.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useConnectOnboardingLink, useConnectOnboardingStatus } from "@/hooks/use-connect-onboarding";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2 } from "lucide-react";

interface PaymentSetupStepProps {
  slug: string;
  onComplete: () => void;
}

export function PaymentSetupStep({ slug, onComplete }: PaymentSetupStepProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { toast } = useToast();

  const isStripeReturn = searchParams.get("stripe_return") === "true";
  const isStripeRefresh = searchParams.get("stripe_refresh") === "true";
  const shouldCheckStatus = isStripeReturn || isStripeRefresh;

  const connectLink = useConnectOnboardingLink(slug);
  const { data: status, isLoading: statusLoading } = useConnectOnboardingStatus(slug, shouldCheckStatus);
  const [hasCheckedStatus, setHasCheckedStatus] = useState(false);

  useEffect(() => {
    if (status && shouldCheckStatus && !hasCheckedStatus) {
      setHasCheckedStatus(true);
      // Clean query params from URL
      router.replace(pathname);
    }
  }, [status, shouldCheckStatus, hasCheckedStatus, router, pathname]);

  const isComplete = status?.onboarding_complete ?? false;

  const handleSetup = () => {
    const baseUrl = window.location.origin;
    const returnUrl = `${baseUrl}${pathname}?stripe_return=true`;
    const refreshUrl = `${baseUrl}${pathname}?stripe_refresh=true`;

    sessionStorage.setItem("onboarding_restaurant_slug", slug);

    connectLink.mutate(
      { returnUrl, refreshUrl },
      {
        onSuccess: (data) => {
          window.location.href = data.url;
        },
        onError: (err) => {
          toast({
            title: "Failed to start payment setup",
            description: err instanceof Error ? err.message : "Unknown error",
            variant: "destructive",
          });
        },
      }
    );
  };

  // Loading state while checking status after return
  if (shouldCheckStatus && statusLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Verifying Payment Setup</h1>
          <p className="text-muted-foreground mt-1">Checking your Stripe account status...</p>
        </div>
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      </div>
    );
  }

  // Complete state
  if (isComplete) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Payments Ready</h1>
          <p className="text-muted-foreground mt-1">
            Your Stripe account is set up and ready to receive payouts.
          </p>
        </div>
        <div className="flex flex-col items-center gap-3 py-6">
          <CheckCircle2 className="h-12 w-12 text-success" />
          <p className="text-success font-medium">Payment setup complete</p>
        </div>
        <div className="flex gap-3 pt-2">
          <Button onClick={onComplete} className="flex-1">
            Continue
          </Button>
        </div>
      </div>
    );
  }

  // Returned but incomplete
  if (isStripeReturn && hasCheckedStatus && !isComplete) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Payment Setup Incomplete</h1>
          <p className="text-muted-foreground mt-1">
            It looks like the payment setup was not completed. Please try again to finish connecting your bank account.
          </p>
        </div>
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleSetup}
            className="flex-1"
            disabled={connectLink.isPending}
          >
            {connectLink.isPending ? "Redirecting..." : "Try Again"}
          </Button>
        </div>
      </div>
    );
  }

  // Session expired / refresh
  if (isStripeRefresh && hasCheckedStatus && !isComplete) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Session Expired</h1>
          <p className="text-muted-foreground mt-1">
            Your payment setup session expired. Please try again.
          </p>
        </div>
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleSetup}
            className="flex-1"
            disabled={connectLink.isPending}
          >
            {connectLink.isPending ? "Redirecting..." : "Set Up Payments"}
          </Button>
        </div>
      </div>
    );
  }

  // Not started (default)
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Set Up Payments</h1>
        <p className="text-muted-foreground mt-1">
          Connect your bank account to receive payouts for QR orders.
          You will be redirected to Stripe to complete setup.
        </p>
      </div>
      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleSetup}
          className="flex-1"
          disabled={connectLink.isPending}
        >
          {connectLink.isPending ? "Redirecting to Stripe..." : "Set Up Payments"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/onboarding/payment-setup-step.tsx
git commit -m "feat: add PaymentSetupStep component for Stripe Connect onboarding"
```

---

## Chunk 3: Frontend — Wire Into Onboarding Flows

### Task 5: Wire PaymentSetupStep into onboarding flow

**Files:**
- Modify: `frontend/src/app/account/onboarding/page.tsx`

- [ ] **Step 1: Update the onboarding page**

Make these changes to `frontend/src/app/account/onboarding/page.tsx`:

1. Add imports:
```typescript
import { useSearchParams } from "next/navigation";
import { PaymentSetupStep } from "@/components/onboarding/payment-setup-step";
```

Note: `useRouter` is already imported. `useSearchParams` is new.

2. Update `Step` type:
```typescript
type Step = "preferences" | "owner-question" | "restaurant-details" | "menu-upload" | "payment-setup" | "pos-vendor";
```

3. Inside the component, after the existing `useState` calls (after line 23), add `useSearchParams` and the Stripe return detection logic:
```typescript
const searchParams = useSearchParams();
```

4. Update the React import to include `useEffect`:
```typescript
import { useState, useEffect } from "react";
```

5. After `if (!isAuthenticated || !user) return null;` (line 25), add a `stripeReturnError` state and Stripe return handling:
```typescript
const [stripeReturnError, setStripeReturnError] = useState(false);

// Restore state after Stripe redirect
useEffect(() => {
  const isStripeReturn = searchParams.get("stripe_return") === "true" || searchParams.get("stripe_refresh") === "true";
  if (isStripeReturn && !restaurantSlug) {
    const savedSlug = sessionStorage.getItem("onboarding_restaurant_slug");
    if (savedSlug) {
      setRestaurantSlug(savedSlug);
      setStep("payment-setup");
    } else {
      setStripeReturnError(true);
    }
  }
}, [searchParams]);
```

6. Add an error UI block before the step rendering (before the `<div>` return):
```tsx
if (stripeReturnError) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md text-center space-y-4">
        <h1 className="text-2xl font-bold">Unable to Restore Session</h1>
        <p className="text-muted-foreground">
          Unable to restore your session. Please return to your profile and continue setup.
        </p>
        <a href="/account/profile" className="text-primary underline">
          Go to Profile
        </a>
      </div>
    </div>
  );
}
```

7. Update `totalSteps`:
```typescript
const totalSteps = step === "restaurant-details" || step === "menu-upload" || step === "payment-setup" || step === "pos-vendor" ? 6 : 2;
```

8. Update `currentStep`:
```typescript
const currentStep =
  step === "preferences" ? 1 :
  step === "owner-question" ? 2 :
  step === "restaurant-details" ? 3 :
  step === "menu-upload" ? 4 :
  step === "payment-setup" ? 5 : 6;
```

9. Change menu-upload to advance to `"payment-setup"`:
```tsx
{step === "menu-upload" && restaurantSlug && (
  <MenuUploadStep slug={restaurantSlug} onComplete={() => setStep("payment-setup")} onSkip={() => setStep("payment-setup")} />
)}
```

10. Add payment-setup step rendering between menu-upload and pos-vendor:
```tsx
{step === "payment-setup" && restaurantSlug && (
  <PaymentSetupStep slug={restaurantSlug} onComplete={() => setStep("pos-vendor")} />
)}
```

11. Pos-vendor stays the same (already renders `handleComplete`).

- [ ] **Step 2: Verify the app compiles**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/onboarding/page.tsx
git commit -m "feat: add payment-setup step to onboarding flow (step 5 of 6)"
```

### Task 6: Wire PaymentSetupStep into register-restaurant flow

**Files:**
- Modify: `frontend/src/app/account/register-restaurant/page.tsx`

- [ ] **Step 1: Update the register-restaurant page**

Make these changes:

1. Update the React import to include `useEffect`:
```typescript
import { useState, useEffect } from "react";
```

2. Add imports:
```typescript
import { useSearchParams } from "next/navigation";
import { PaymentSetupStep } from "@/components/onboarding/payment-setup-step";
```

Note: `useRouter` already imported. `useSearchParams` is new.

3. Update `Step` type:
```typescript
type Step = "details" | "menu" | "payment-setup" | "pos-vendor";
```

4. Add `useSearchParams` inside the component:
```typescript
const searchParams = useSearchParams();
```

5. After the `isAuthenticated` checks, add a `stripeReturnError` state and Stripe return detection:
```typescript
const [stripeReturnError, setStripeReturnError] = useState(false);

useEffect(() => {
  const isStripeReturn = searchParams.get("stripe_return") === "true" || searchParams.get("stripe_refresh") === "true";
  if (isStripeReturn && !restaurantSlug) {
    const savedSlug = sessionStorage.getItem("onboarding_restaurant_slug");
    if (savedSlug) {
      setRestaurantSlug(savedSlug);
      setStep("payment-setup");
    } else {
      setStripeReturnError(true);
    }
  }
}, [searchParams]);
```

6. Add an error UI block before the step rendering:
```tsx
if (stripeReturnError) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md text-center space-y-4">
        <h1 className="text-2xl font-bold">Unable to Restore Session</h1>
        <p className="text-muted-foreground">
          Unable to restore your session. Please return to your profile and continue setup.
        </p>
        <a href="/account/profile" className="text-primary underline">
          Go to Profile
        </a>
      </div>
    </div>
  );
}
```

8. Update `totalSteps`:
```typescript
const totalSteps = 4;
```

9. Update `currentStep`:
```typescript
const currentStep = step === "details" ? 1 : step === "menu" ? 2 : step === "payment-setup" ? 3 : 4;
```

10. Change menu step to advance to `"payment-setup"`:
```tsx
{step === "menu" && restaurantSlug && (
  <MenuUploadStep
    slug={restaurantSlug}
    onComplete={() => setStep("payment-setup")}
    onSkip={() => setStep("payment-setup")}
  />
)}
```

11. Add payment-setup step between menu and pos-vendor:
```tsx
{step === "payment-setup" && restaurantSlug && (
  <PaymentSetupStep
    slug={restaurantSlug}
    onComplete={() => setStep("pos-vendor")}
  />
)}
```

- [ ] **Step 2: Verify the app compiles**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/register-restaurant/page.tsx
git commit -m "feat: add payment-setup step to register-restaurant flow (step 3 of 4)"
```

---

## Chunk 4: Final Verification

### Task 7: Full test suite and verification

- [ ] **Step 1: Run backend connect tests**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_connect_views.py -v`
Expected: All tests pass.

- [ ] **Step 2: Run frontend type check**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Run frontend build**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/frontend && npx next build --no-lint 2>&1 | tail -10`
Expected: Build succeeds.

- [ ] **Step 4: Manual smoke test checklist**

1. Go to `/account/onboarding` as new user → complete through menu-upload → see "Set Up Payments" step (5 of 6)
2. Click "Set Up Payments" → should redirect to Stripe Connect form
3. Complete Stripe form → redirected back to onboarding → see "Payments Ready" with Continue button
4. Click Continue → advance to POS vendor step (6 of 6)
5. Go to `/account/register-restaurant` → complete through menu → see payment setup (3 of 4)
6. Test the refresh scenario: start Stripe form, close it, come back via refresh URL → see "Session Expired" message
