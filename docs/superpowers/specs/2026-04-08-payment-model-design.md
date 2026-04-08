# Payment Model Design: Upfront vs Tab

**Date:** 2026-04-08
**Status:** Approved

## Problem

All restaurants currently require upfront payment for every order. This works for simple pickup restaurants but not for full-service restaurants where customers order multiple times and pay once at the end. Restaurant owners need to choose which payment model fits their business.

## Decisions

- Payment model is a per-restaurant setting: `upfront` (default) or `tab`
- Owners can switch between models at any time from settings
- Tab is scoped per table — all orders at a table share one tab
- Orders in tab mode go straight to kitchen (no staff approval gate)
- Either customer or staff can close the tab
- Split bill supported: pay full amount, split evenly, or pay by item

## Data Model

### Restaurant model change

Add field to existing `Restaurant` model:

```python
payment_model = CharField(
    max_length=20,
    choices=[("upfront", "Pay Upfront"), ("tab", "Open Tab")],
    default="upfront"
)
```

### New: Tab model (orders app)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `restaurant` | FK -> Restaurant | |
| `table_identifier` | CharField | e.g., "A3", "Patio 2" |
| `status` | CharField | `open` -> `closing` -> `closed` |
| `opened_at` | DateTimeField | auto_now_add |
| `closed_at` | DateTimeField | nullable |
| `subtotal` | DecimalField | computed from orders |
| `tax_amount` | DecimalField | computed from orders |
| `total` | DecimalField | computed from orders |

Unique constraint on `(restaurant, table_identifier)` where `status = "open"` — only one open tab per table.

### New: TabPayment model (orders app)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `tab` | FK -> Tab | |
| `type` | CharField | `full`, `split_even`, `pay_by_item` |
| `amount` | DecimalField | amount this payment covers |
| `tax_amount` | DecimalField | tax portion |
| `stripe_payment_intent_id` | CharField | nullable, unique |
| `payment_status` | CharField | `pending`, `paid`, `failed` |
| `items` | M2M -> OrderItem | only for `pay_by_item` |
| `split_count` | PositiveIntegerField | only for `split_even` — total people splitting |
| `paid_at` | DateTimeField | nullable |
| `created_at` | DateTimeField | auto_now_add |

### Order model change

Add nullable FK:

```python
tab = ForeignKey("Tab", null=True, blank=True, on_delete=SET_NULL, related_name="orders")
```

Add `deferred` to `payment_status` choices — used when an order is placed in tab mode (payment comes later).

## API Design

### New endpoints

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| `GET` | `/api/order/{slug}/tab/?table={id}` | Get open tab for a table | Customer |
| `POST` | `/api/order/{slug}/tab/close/` | Initiate tab close | Customer or staff |
| `POST` | `/api/order/{slug}/tab/pay/` | Create a TabPayment | Customer |
| `POST` | `/api/order/{slug}/tab/confirm-payment/{payment_id}/` | Verify Stripe payment | Customer |
| `POST` | `/api/kitchen/tab/{tab_id}/close/` | Staff-initiated close | Staff |

### Modified endpoints

**`POST /api/order/{slug}/create-payment/`** — when `restaurant.payment_model == "tab"`:
- Creates or retrieves the open Tab for the table
- Creates Order linked to the Tab
- Skips PaymentIntent creation
- Sets `order.status = "confirmed"`, `order.payment_status = "deferred"`
- Returns order + tab summary (no `client_secret`)

**`GET /api/order/{slug}/menu/`** — response includes `payment_model` field so frontend knows which flow to use.

## Order Flow

### Upfront mode (unchanged)

```
Scan QR -> Welcome -> Ordering -> Cart -> Payment -> Submitted
```

### Tab mode

```
Scan QR -> Welcome -> Ordering -> Cart -> Submitted (order sent to kitchen)
  -> "Order More" (back to Ordering) or "View Tab & Pay" (to Tab Review)
  -> Tab Review -> Payment -> Tab Closed
```

### Re-scan with open tab

```
Scan QR -> WelcomeStep detects open tab
  -> "You have an open tab ($24.50). Continue ordering?"
  -> Skip to Ordering (TabStatusBar shows running total)
  -> Place new order -> new kitchen ticket -> Submitted
```

Each re-order creates a new Order (separate kitchen ticket) linked to the same Tab.

## Tab Closing Flow

1. Customer or staff initiates close -> Tab status = `closing`
2. Customer sees payment options:
   - **Pay full amount** — single PaymentIntent for `tab.total`
   - **Split evenly** — enter N people, each pays `tab.total / N`. Shareable link/QR for others to pay their share.
   - **Pay by item** — select OrderItems, pay sum of selected + proportional tax
3. Each TabPayment creates its own Stripe PaymentIntent
4. When sum of paid TabPayments >= tab total -> tab status = `closed`, all orders updated from `deferred` -> `paid`

### Split-even rounding

Last payer's amount is adjusted to cover the exact remainder, not `total / N`. This avoids overpayment from rounding.

### Split-even sharing

Tab page shows a shareable link or QR code so other people at the table can pay their portion from their own devices.

## Frontend Changes

### Order store additions

- `paymentModel: "upfront" | "tab"` — from menu fetch
- `tabId: string | null`
- `tabOrders: OrderItem[]` — all orders on current tab
- `tabTotal: string`
- New step: `"tab_review"`

### New components

- **`TabReviewStep.tsx`** — all orders on tab, total, payment action buttons
- **`SplitEvenModal.tsx`** — input for N people, per-person amount, share link
- **`PayByItemModal.tsx`** — checkboxes for each OrderItem, running selected total
- **`TabStatusBar.tsx`** — persistent bar during ordering: "Tab open - $X.XX so far"

### Modified components

- **`PaymentStep.tsx`** — add TabPayment code path using TabPayment's `client_secret`
- **`CartBottomBar.tsx`** — tab mode: "Place Order" instead of "Proceed to Payment"
- **`SubmittedStep.tsx`** — tab mode: "Order More" and "View Tab & Pay" buttons
- **`WelcomeStep.tsx`** — detect open tab on load, offer shortcut to resume

## Webhook Handling

- `_handle_tab_payment_succeeded(intent)` — find TabPayment by `stripe_payment_intent_id`, mark `paid`, check if tab is fully paid, if so close tab and update all orders to `paid`
- `_handle_tab_payment_failed(intent)` — mark TabPayment `failed`, tab stays `closing` for retry

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Order placed while tab is `closing` | Rejected — "Tab is being closed" |
| Staff closes tab, customer hasn't paid | Tab = `closing`, customer sees payment prompt on next page load |
| Split-even rounding | Last payer covers exact remainder |
| Customer abandons tab | Staff can close from admin. Unpaid tabs stay `closing`. Optional "mark as unpaid" staff action. |
| Payment model switched with open tabs | Existing tabs continue until closed. New orders follow new model. |
| No open tab + tab mode | Tab auto-created on first order |
| POS-collected + tab mode | Tab tracks orders, closing marks all as `pos_collected` (no Stripe). |

## POS-Collected + Tab Interaction

`payment_mode` (stripe vs pos_collected) = HOW payment happens.
`payment_model` (upfront vs tab) = WHEN payment happens.

A restaurant using POS-collected payment with tab mode: customers order multiple times via QR, food goes to kitchen, all tracked on a tab. When closing, everything is marked `pos_collected` — no Stripe PaymentIntent needed. Payment is handled at the physical register.
