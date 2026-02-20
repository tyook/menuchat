# Saved Payment Methods — Design

## Overview

Allow logged-in customers to save payment methods (cards) during checkout and reuse them for future orders. Saved cards are stored entirely in Stripe — our backend only holds a `stripe_customer_id` reference. Management UI at `/account/payment-methods`.

## Data Model Changes

### Customer model — new fields

- `stripe_customer_id`: CharField, max_length=255, nullable, blank. Created lazily on first payment. Links to a Stripe Customer object.

### Order model — new fields

- `stripe_payment_method_id`: CharField, max_length=255, nullable, blank. Records which payment method was used.

No new Django models. Saved payment methods live in Stripe (queried via API).

## Backend API Changes

### Modified: POST `/api/order/{slug}/create-payment/`

New optional request body fields:

- `payment_method_id` (string, optional): ID of a saved Stripe PaymentMethod to charge directly.
- `save_card` (boolean, optional): When true, sets `setup_future_usage="on_session"` on the PaymentIntent so Stripe saves the card after payment.

Flow when customer is logged in:

1. If `stripe_customer_id` is null, create a Stripe Customer (`stripe.Customer.create`) and save the ID.
2. Attach `customer` param to the PaymentIntent.
3. If `payment_method_id` is provided: create PaymentIntent with `payment_method`, `confirm=True`, and `off_session=False`. Payment completes server-side. Return completed order.
4. If `save_card` is true: add `setup_future_usage="on_session"` to the PaymentIntent. After payment, Stripe automatically saves the card.

Flow for guests (not logged in): unchanged from current behavior.

### New: GET `/api/customer/payment-methods/`

Requires customer JWT. Calls `stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")`.

Returns:

```json
[
  {
    "id": "pm_xxx",
    "brand": "visa",
    "last4": "4242",
    "exp_month": 12,
    "exp_year": 2027
  }
]
```

Returns empty list if customer has no `stripe_customer_id` or no saved methods.

### New: DELETE `/api/customer/payment-methods/{pm_id}/`

Requires customer JWT. Calls `stripe.PaymentMethod.detach(pm_id)`. Returns 204 No Content.

Validates that the payment method belongs to the customer's Stripe Customer before detaching.

## Frontend Changes

### PaymentStep component

1. If customer is logged in, fetch saved payment methods on mount.
2. If saved cards exist: show radio list (brand + last4 + expiry) with most recent pre-selected, plus "Add new card" option.
3. Selecting saved card + "Pay Now": POST to `create-payment/` with `payment_method_id`. No Stripe Element needed. Transition to "submitted".
4. Selecting "Add new card" or not logged in: show current Stripe Payment Element.
5. "Save this card" checkbox: shown below Payment Element only when logged in. Sends `save_card: true` to backend.

### New page: `/account/payment-methods`

- List saved cards with brand, last4, expiry.
- Delete button per card.
- Empty state: "No saved payment methods."
- Linked from account navigation.

### New API functions (`api.ts`)

- `fetchPaymentMethods()` — GET `/api/customer/payment-methods/`
- `deletePaymentMethod(pmId)` — DELETE `/api/customer/payment-methods/{pm_id}/`

### New hooks

- `usePaymentMethods()` — React Query hook for the list
- `useDeletePaymentMethod()` — mutation hook with cache invalidation

## Edge Cases

| Scenario | Handling |
|---|---|
| Saved card declined | Backend returns error, frontend falls back to "Add new card" |
| Card expires | Stripe returns `card_declined`, same as above |
| Customer deletes all cards | Checkout shows standard Payment Element |
| Customer logs out mid-checkout | Saved cards disappear, guest Payment Element flow |
| Save checkbox unchecked | No `setup_future_usage`, card not saved |
| Stripe Customer already exists | Reuse existing `stripe_customer_id` |
