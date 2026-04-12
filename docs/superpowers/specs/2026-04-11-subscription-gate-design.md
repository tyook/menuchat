# Subscription Gate for Public Ordering Page

**Date:** 2026-04-11
**Status:** Approved

## Problem

When a customer visits `/order/{slug}`, the page loads the restaurant's menu and renders the full ordering flow regardless of the restaurant's subscription status. If the subscription is inactive (canceled, expired trial, no subscription), the customer can browse the menu but hits errors when trying to parse or submit an order. The expected behavior is to block access at the menu level with a generic "not accepting orders" message.

## Decisions

- **Block at the menu level** — `PublicMenuView` checks subscription status and returns `{ available: false, restaurant_name }` when inactive. The frontend renders a dead-end message instead of the ordering flow.
- **Generic customer-facing message** — "This restaurant is not currently accepting online orders." No details about billing status.
- **Keep existing trial behavior** — New restaurants still get a 14-day free trial automatically.
- **Prorate upgrades** — Stripe's default proration behavior (already configured).
- **No billing page changes** — Upgrade, cancel, reactivate flows already exist and work.

## Design

### Backend: `PublicMenuView` subscription check

**File:** `backend/orders/views.py`

Add a subscription check before returning menu data. If the subscription is missing, inactive, or the trial has expired, return a JSON response with `available: false` and the restaurant name. Otherwise, return the normal menu response.

Logic:
1. Fetch the restaurant by slug (existing behavior).
2. Try to access `restaurant.subscription`.
3. If `Subscription.DoesNotExist` → return `{ available: false, restaurant_name }`.
4. If `subscription.is_active` is false → return `{ available: false, restaurant_name }`.
5. If subscription is trialing and `trial_end < now()` → return `{ available: false, restaurant_name }`.
6. Otherwise → return normal menu via `OrderService.get_public_menu(slug)`.

### Frontend: Handle unavailable state in `OrderPageClient`

**File:** `frontend/src/app/order/[slug]/OrderPageClient.tsx`

After the loading check and before the existing error check, add a condition: if the menu response contains `available: false`, render a centered message with the restaurant name and "This restaurant is not currently accepting online orders."

### Frontend: Type addition

**File:** `frontend/src/types/index.ts`

Add a `MenuUnavailable` interface:
```ts
interface MenuUnavailable {
  available: false;
  restaurant_name: string;
}
```

The menu hook return type becomes `MenuResponse | MenuUnavailable`.

## Edge Cases

| Scenario | Result |
|----------|--------|
| No subscription record (legacy) | `available: false` |
| Expired trial | `available: false` |
| Canceled subscription | `available: false` |
| Past due beyond 3-day grace | `available: false` (via `is_active`) |
| Active subscription | Normal menu |
| Trialing (not expired) | Normal menu |
| Past due within grace | Normal menu (via `is_active`) |
| Frontend JS bypass | Backend still blocks parse/confirm via `check_subscription()` |

## Files Changed

1. `backend/orders/views.py` — Subscription check in `PublicMenuView`
2. `frontend/src/app/order/[slug]/OrderPageClient.tsx` — Handle `available: false`
3. `frontend/src/types/index.ts` — Add `MenuUnavailable` type

## Out of Scope

- Billing page UI changes (already functional)
- Cancel/reactivate/upgrade backend flows (already implemented)
- `HasActiveSubscription` permission on owner dashboard (already enforced)
- `check_subscription()` gate on parse/confirm (already enforced)
- Webhook handlers for subscription lifecycle (already working)
