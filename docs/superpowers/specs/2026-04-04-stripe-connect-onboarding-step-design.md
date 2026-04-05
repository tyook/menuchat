# Stripe Connect Payment Setup Onboarding Step

## Problem

Restaurant owners must set up Stripe Connect to receive payouts, but the Stripe Connect onboarding is currently disconnected from the app's onboarding flow. There is no frontend UI for it at all. Owners need to complete payment setup before they can accept orders.

## Goal

Add a mandatory payment setup step to the onboarding flow that guides restaurant owners through Stripe Connect Express onboarding. This is the first frontend UI for Stripe Connect in the app.

## Design

### Backend Changes

**1. Make return/refresh URLs configurable in `ConnectService.create_onboarding_link`**

Currently `create_onboarding_link` hardcodes `return_url` and `refresh_url` to `/dashboard/{slug}/connect/...`. Change the method to accept optional `return_url` and `refresh_url` parameters, falling back to the current hardcoded defaults if not provided.

**2. Add onboarding-safe connect views**

The existing `ConnectOnboardView` and `ConnectStatusView` use `RestaurantMixin` which requires `HasActiveSubscription`. During onboarding, restaurants won't have a subscription.

Add two new views with `permission_classes = [IsAuthenticated]` and an inline owner-only restaurant lookup (same pattern as `get_restaurant` in `RestaurantPOSMixin` but without `HasActiveSubscription` — note that `RestaurantPOSMixin` itself also has `HasActiveSubscription`, so we cannot reuse it directly):

- `OnboardingConnectInitiateView` at `POST /api/restaurants/{slug}/connect/onboarding-initiate/` — calls `ConnectService.create_onboarding_link` with the caller-provided `return_url` and `refresh_url`
- `OnboardingConnectStatusView` at `GET /api/restaurants/{slug}/connect/onboarding-status/` — calls `ConnectService.get_connect_status`

These are separate from the existing subscription-gated views so the settings page flow remains unchanged.

**3. Accept `return_url` and `refresh_url` in the initiate request body**

The new `OnboardingConnectInitiateView` accepts:
```json
{
  "return_url": "http://localhost:3000/account/onboarding?stripe_return=true",
  "refresh_url": "http://localhost:3000/account/onboarding?stripe_refresh=true"
}
```

Validate that **both** `return_url` and `refresh_url` start with `settings.FRONTEND_URL`. If either URL fails validation, return `400 Bad Request` with `{"error": "Invalid return URL"}`.

**Webhook dependency:** The step checks `onboarding_complete` to determine if setup is complete. This field is set by the existing Stripe `account.updated` webhook handler in `orders/services.py::_handle_account_updated()`. No new webhook handling is needed.

### Frontend — New Files

**API functions** in `src/lib/api.ts`:
- `createOnboardingConnectLink(slug: string, returnUrl: string, refreshUrl: string)` → `POST /api/restaurants/{slug}/connect/onboarding-initiate/`
- `fetchOnboardingConnectStatus(slug: string)` → `GET /api/restaurants/{slug}/connect/onboarding-status/`

**Hook** `src/hooks/use-connect-onboarding.ts`:
- `useConnectOnboardingLink(slug)` — mutation wrapping `createOnboardingConnectLink`
- `useConnectOnboardingStatus(slug)` — query wrapping `fetchOnboardingConnectStatus`, with `enabled` flag to control when it runs

**Step component** `src/components/onboarding/payment-setup-step.tsx`:

Props: `slug: string`, `onComplete: () => void`

No `onSkip` — this step is mandatory.

Four UI states:

1. **Not started** (no `?stripe_return` or `?stripe_refresh` in URL, status is not `onboarding_complete`):
   - Heading: "Set Up Payments"
   - Explanation: "Connect your bank account to receive payouts for QR orders. You'll be redirected to Stripe to complete setup."
   - "Set up payments" button → calls initiate endpoint, then `window.location.href = url`. Button shows loading state and disables on click to prevent double-clicks.

2. **Returned but incomplete** (`?stripe_return=true` in URL, but `onboarding_complete` is false):
   - "Payment setup incomplete" message
   - "Try again" button → generates new onboarding link, redirects again

3. **Session expired / refresh** (`?stripe_refresh=true` in URL):
   - "Your payment setup session expired. Please try again." message
   - "Set up payments" button → generates new onboarding link, redirects again

4. **Complete** (`onboarding_complete` is true):
   - Success message with checkmark
   - Continue button enabled → calls `onComplete()`

On mount, if `?stripe_return=true` or `?stripe_refresh=true` is in the URL, immediately fetch connect status. If `onboarding_complete` is true, show state 4 regardless of which query param is present. After processing, clean the query params from the URL via `router.replace` to prevent confusion on refresh.

### Frontend — Onboarding Flow Changes

**`/account/onboarding/page.tsx`:**
- New step `"payment-setup"` between `"menu-upload"` and `"pos-vendor"`
- Owner path becomes 6 steps: preferences → owner-question → restaurant-details → menu-upload → payment-setup → pos-vendor
- Update `totalSteps` conditional: add `"payment-setup"` to the owner-path condition, change value from 5 to 6
- Update `currentStep` mapping: preferences=1, owner-question=2, restaurant-details=3, menu-upload=4, payment-setup=5, pos-vendor=6
- Menu-upload advances to `"payment-setup"` (not `"pos-vendor"`)
- Payment-setup advances to `"pos-vendor"` on complete
- On page load, if `?stripe_return=true` or `?stripe_refresh=true` query param is present, restore `restaurantSlug` from `sessionStorage` and set step to `"payment-setup"`

**`/account/register-restaurant/page.tsx`:**
- New step `"payment-setup"` between `"menu"` and `"pos-vendor"`
- Becomes 4 steps: details → menu → payment-setup → pos-vendor
- Update `currentStep` mapping: details=1, menu=2, payment-setup=3, pos-vendor=4
- Same Stripe return handling

### Return URL Flow

1. User reaches payment-setup step, clicks "Set up payments"
2. Frontend saves `restaurantSlug` to `sessionStorage`
3. Frontend calls `POST /connect/onboarding-initiate/` with `return_url` = `{FRONTEND_URL}/account/onboarding?stripe_return=true`, `refresh_url` = `{FRONTEND_URL}/account/onboarding?stripe_refresh=true`
4. Backend creates Stripe Express account (if needed), generates AccountLink, returns `{ url: "https://connect.stripe.com/..." }`
5. Frontend does `window.location.href = url` — user leaves the app
6. User completes Stripe form
7. Stripe redirects to `return_url` → onboarding page loads
8. Page detects `?stripe_return=true`, restores `restaurantSlug` from `sessionStorage`, sets step to `"payment-setup"`
9. Step fetches `GET /connect/onboarding-status/` — if `onboarding_complete`, shows success + Continue
10. Cleans query params from URL via `router.replace`

### State Persistence Across Redirect

The Stripe redirect causes a full page reload, which loses React state (`restaurantSlug`). To handle this:

- Before redirecting to Stripe, save `restaurantSlug` to `sessionStorage` under a known key (e.g., `onboarding_restaurant_slug`)
- On page load with `?stripe_return=true` or `?stripe_refresh=true`, read `restaurantSlug` from `sessionStorage` and restore state
- If `sessionStorage` has no slug on return, show an error: "Unable to restore your session. Please return to your profile and continue setup." with a link to `/account/profile`

### Register-Restaurant Return URL

For the register-restaurant flow, use `return_url` = `{FRONTEND_URL}/account/register-restaurant?stripe_return=true`. Same `sessionStorage` pattern for slug persistence.

## Out of Scope

- Stripe Connect dashboard link UI (settings page feature, not onboarding)
- Payout list/detail UI
- Modifying the existing subscription-gated connect views
- `payouts_enabled` polling — we only check `onboarding_complete`
- Back navigation from payment-setup step (mandatory step, no going back)
