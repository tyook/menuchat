# Subscription Gate for Public Ordering Page

**Date:** 2026-04-11
**Status:** Approved

## Problem

When a customer visits `/order/{slug}`, the page loads the restaurant's menu and renders the full ordering flow regardless of the restaurant's subscription status. If the subscription is inactive (canceled, expired trial), the customer can browse the menu but hits errors when trying to parse or submit an order. The expected behavior is to block access at the menu level with a generic "not accepting orders" message.

## Decisions

- **Block at the menu level** — `PublicMenuView` checks subscription status and returns `{ available: false, restaurant_name }` (HTTP 200) when inactive. The frontend renders a dead-end message instead of the ordering flow.
- **Generic customer-facing message** — "This restaurant is not currently accepting online orders." No details about billing status.
- **Keep existing trial behavior** — New restaurants still get a 14-day free trial automatically.
- **Preserve legacy restaurant access** — Restaurants with no `Subscription` record continue to work (matching existing `check_subscription()` behavior).
- **Prorate upgrades** — Stripe's default proration behavior (already configured).
- **Payment failure email** — When a subscription transitions to `past_due`, send the restaurant owner an email: "Your payment failed. Please update your payment method to avoid service interruption."
- **Payment success email** — When `invoice.paid` webhook fires for a subscription invoice, send the restaurant owner a receipt email with amount, plan, and period.
- **Billing history on billing page** — Fetch invoices from Stripe List Invoices API, display a simple table (date, amount, plan, status, PDF receipt link) on the existing billing page.
- **Discriminated union responses** — Both available and unavailable responses include an `available` boolean for clean frontend type narrowing.

## Design

### Backend: Extract shared subscription check, use in `PublicMenuView`

**File:** `backend/orders/services.py`

Extract a reusable boolean helper from the existing `check_subscription()` to avoid logic duplication:

```python
@staticmethod
def is_subscription_active(restaurant: Restaurant) -> bool:
    """Return True if the restaurant may accept orders."""
    try:
        subscription = restaurant.subscription
    except Subscription.DoesNotExist:
        return True  # Legacy restaurant, allow access

    if not subscription.is_active:
        return False

    # is_active returns True for "trialing" status, but trial may have expired
    if (
        subscription.status == "trialing"
        and subscription.trial_end
        and subscription.trial_end < timezone.now()
    ):
        return False

    return True
```

Refactor `check_subscription()` to use this helper internally (raises `PermissionDenied` when `is_subscription_active()` returns False).

**File:** `backend/orders/views.py` — `PublicMenuView`

Use the new helper. Return HTTP 200 in both cases — `available: true` with the menu data, or `available: false` with just the restaurant name.

```python
class PublicMenuView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        if not OrderService.is_subscription_active(restaurant):
            return Response({
                "available": False,
                "restaurant_name": restaurant.name,
            })

        menu = OrderService.get_public_menu(slug)
        menu["available"] = True
        return Response(menu)
```

### Frontend: Handle unavailable state in `OrderPageClient`

**File:** `frontend/src/app/order/[slug]/OrderPageClient.tsx`

After the loading check and before the existing error check, add a condition: if the menu response has `available === false`, render a centered message with the restaurant name and "This restaurant is not currently accepting online orders."

### Frontend: Type changes

**File:** `frontend/src/types/index.ts`

Add a `MenuUnavailable` interface:
```ts
interface MenuUnavailable {
  available: false;
  restaurant_name: string;
}
```

Update the existing `PublicMenu` type to include `available: true`.

**File:** `frontend/src/lib/api.ts`

Update `fetchMenu` return type to `Promise<PublicMenu | MenuUnavailable>`.

**File:** `frontend/src/hooks/use-menu.ts`

Return type follows from `fetchMenu` — `PublicMenu | MenuUnavailable`.

### Backend: Payment failure email

**File:** `backend/restaurants/notifications.py`

Add `send_payment_failed_email(restaurant)` following the existing pattern (HTML template + plain text fallback):

```python
def send_payment_failed_email(restaurant) -> None:
    """Notify restaurant owner that their subscription payment failed."""
```

Email content: "Your payment for {restaurant_name} failed. Please update your payment method to avoid service interruption." Include a link to the billing page (`/account/restaurants/{slug}/billing`).

**File:** `backend/restaurants/tasks.py`

Add a Celery task `send_payment_failed_email_task` (same pattern as `send_subscription_activated_email_task`).

**File:** `backend/orders/templates/emails/payment_failed.html`

New HTML email template following the style of `subscription_activated.html`.

**File:** `backend/orders/services.py` — `_handle_subscription_updated`

After saving the subscription, check if the new status is `past_due` and the previous status was not `past_due` (to avoid duplicate emails on repeated webhook deliveries). If so, dispatch `send_payment_failed_email_task`.

### Backend: Payment success email

**File:** `backend/restaurants/notifications.py`

Add `send_payment_success_email(restaurant, amount, plan, period_end)` following the existing pattern. Email content: "Your payment of ${amount} for {restaurant_name} ({plan_name} plan) has been received. Next billing date: {period_end}." Include a link to the billing page.

**File:** `backend/restaurants/tasks.py`

Add a Celery task `send_payment_success_email_task`.

**File:** `backend/orders/templates/emails/payment_success.html`

New HTML email template following the style of `subscription_activated.html`.

**File:** `backend/orders/services.py` — `_handle_invoice_paid`

Currently only resets `order_count`. Add: extract amount, plan, and period end from the invoice data, then dispatch `send_payment_success_email_task`. Only send for subscription invoices (skip one-time charges) — the existing `if not subscription_id: return` guard already handles this.

### Backend + Frontend: Billing history

**File:** `backend/restaurants/views.py`

Add `BillingHistoryView` — a new endpoint at `GET /api/restaurants/{slug}/subscription/invoices/` that fetches invoices from Stripe's List Invoices API using the subscription's `stripe_customer_id`. Return a list of:

```python
{
    "id": invoice.id,
    "date": invoice.created,          # Unix timestamp
    "amount": invoice.amount_paid,     # In cents
    "currency": invoice.currency,
    "status": invoice.status,          # "paid", "open", "void", etc.
    "plan": plan_name,                 # Extracted from line items
    "receipt_url": invoice.hosted_invoice_url,  # Stripe-hosted receipt
}
```

Paginate with `limit=12` (1 year of monthly invoices). Uses `IsAuthenticated` + `IsRestaurantOwnerOrStaff` permissions.

**File:** `backend/restaurants/urls.py`

Add URL pattern for `subscription/invoices/`.

**File:** `frontend/src/hooks/use-billing-history.ts`

New hook `useBillingHistory(slug)` — fetches from the invoices endpoint.

**File:** `frontend/src/lib/api.ts`

Add `fetchBillingHistory(slug)` function.

**File:** `frontend/src/types/index.ts`

Add `BillingInvoice` interface matching the API response shape.

**File:** `frontend/src/app/account/restaurants/[slug]/billing/BillingPageClient.tsx`

Add a "Billing History" section below the plan selection grid. Simple table with columns: Date, Amount, Plan, Status, Receipt (link). Show "No billing history yet" for restaurants still on trial.

## Edge Cases

| Scenario | Result |
|----------|--------|
| No subscription record (legacy) | Normal menu (matches existing `check_subscription()`) |
| Expired trial | `available: false` |
| Canceled subscription | `available: false` (via `is_active`) |
| Past due (any duration) | Normal menu (`is_active` returns true for `past_due`) |
| Active subscription | Normal menu |
| Trialing (not expired) | Normal menu |
| Frontend JS bypass | Backend still blocks parse endpoints via `check_subscription()` |

**Note:** The `past_due` grace period (3 days) is only enforced by `HasActiveSubscription` on owner dashboard endpoints. The public ordering path (both this gate and `check_subscription()`) allows all `past_due` subscriptions. This is intentional — customers should be able to order even if the restaurant owner is a few days late on payment.

**Known gap:** `ConfirmOrderView` and `CreatePaymentView` do not call `check_subscription()`. This means a crafted request could bypass the menu gate and create an order for an inactive subscription. This is a pre-existing issue and is out of scope for this change, but worth noting for a future hardening pass.

## Files Changed

1. `backend/orders/services.py` — Extract `is_subscription_active()` helper, refactor `check_subscription()`, trigger payment failure email in `_handle_subscription_updated`, trigger payment success email in `_handle_invoice_paid`
2. `backend/orders/views.py` — Subscription check in `PublicMenuView`
3. `backend/restaurants/notifications.py` — Add `send_payment_failed_email()` and `send_payment_success_email()`
4. `backend/restaurants/tasks.py` — Add `send_payment_failed_email_task` and `send_payment_success_email_task`
5. `backend/orders/templates/emails/payment_failed.html` — New email template
6. `backend/orders/templates/emails/payment_success.html` — New email template
7. `backend/restaurants/views.py` — Add `BillingHistoryView`
8. `backend/restaurants/urls.py` — Add invoices endpoint
9. `frontend/src/app/order/[slug]/OrderPageClient.tsx` — Handle `available: false`
10. `frontend/src/types/index.ts` — Add `MenuUnavailable`, `BillingInvoice` types, update `PublicMenu`
11. `frontend/src/lib/api.ts` — Update `fetchMenu` return type, add `fetchBillingHistory`
12. `frontend/src/hooks/use-menu.ts` — Return type follows from `fetchMenu`
13. `frontend/src/hooks/use-billing-history.ts` — New hook for billing history
14. `frontend/src/app/account/restaurants/[slug]/billing/BillingPageClient.tsx` — Add billing history table

## Out of Scope

- Billing page UI changes beyond billing history table (upgrade/cancel/reactivate flows already functional)
- Cancel/reactivate/upgrade backend flows (already implemented)
- `HasActiveSubscription` permission on owner dashboard (already enforced)
- Webhook handlers for subscription lifecycle (already working)
- Adding `check_subscription()` to `ConfirmOrderView`/`CreatePaymentView` (pre-existing gap, separate task)
- Cache-control headers (menu endpoint is not cached)
