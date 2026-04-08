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

Note: `payment_mode` (stripe vs pos_collected) lives on `POSConnection` and determines HOW payment is collected. `payment_model` on `Restaurant` determines WHEN. These are orthogonal concerns — `payment_mode` is a POS integration detail, while `payment_model` is a restaurant-level business decision. A helper `get_payment_config(restaurant)` should be added to the service layer to resolve both fields together.

### New: Tab model (orders app)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUIDField (PK) | |
| `restaurant` | FK -> Restaurant | |
| `table_identifier` | CharField | e.g., "A3", "Patio 2" |
| `status` | CharField | `open` -> `closing` -> `closed` |
| `opened_at` | DateTimeField | auto_now_add |
| `closed_at` | DateTimeField | nullable |

Unique constraint on `(restaurant, table_identifier)` where `status = "open"` — only one open tab per table. This uses PostgreSQL's partial unique index via `UniqueConstraint(... condition=Q(status="open"))`. As a safety net, the service layer also uses `select_for_update()` when creating tabs to prevent races.

Tab totals (`subtotal`, `tax_amount`, `total`) are computed as `@property` methods that aggregate from `self.orders.all()`. No stored fields — the number of orders per tab is small enough that this is efficient, and it avoids sync issues.

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

Add `deferred` to `payment_status` choices — used when an order is placed in tab mode (payment comes later). When the tab closes and payment is confirmed, `payment_status` transitions from `deferred` to `paid` and `paid_at` is set. This ensures payout-eligibility queries (which filter on `payment_status = "paid"`) naturally pick up tab orders.

## API Design

### New endpoints

| Method | Endpoint | Purpose | Caller |
|--------|----------|---------|--------|
| `GET` | `/api/order/{slug}/tab/?table={id}` | Get open tab for a table (orders, totals, payment progress) | Customer |
| `POST` | `/api/order/{slug}/tab/order/` | Place an order on a tab (tab mode only) | Customer |
| `POST` | `/api/order/{slug}/tab/close/` | Initiate tab close | Customer or staff |
| `POST` | `/api/order/{slug}/tab/pay/` | Create a TabPayment | Customer |
| `POST` | `/api/order/{slug}/tab/confirm-payment/{payment_id}/` | Verify Stripe payment | Customer |
| `POST` | `/api/kitchen/tab/{tab_id}/close/` | Staff-initiated close | Staff (authenticated) |

Tab order placement gets its own endpoint (`tab/order/`) rather than overloading `create-payment`. The existing `create-payment` and `confirm-order` endpoints remain unchanged for upfront mode.

### Tab endpoint response shape

`GET /api/order/{slug}/tab/` returns:
```json
{
  "id": "tab-uuid",
  "table_identifier": "A3",
  "status": "open",
  "orders": [ ... ],
  "subtotal": "45.00",
  "tax_amount": "3.99",
  "total": "48.99",
  "amount_paid": "20.00",
  "amount_remaining": "28.99",
  "opened_at": "..."
}
```

The `amount_paid` and `amount_remaining` fields are included so the frontend can show split payment progress without additional queries.

### Modified endpoints

**`GET /api/order/{slug}/menu/`** — response includes `payment_model` field so frontend knows which flow to use.

**`POST /api/order/{slug}/confirm/`** (POS-collected flow) — in tab mode with POS-collected payment, this endpoint also creates/retrieves the Tab and links the order to it, setting `payment_status = "pos_collected"` as it does today.

### Authorization

Customer-facing tab endpoints (`/api/order/{slug}/tab/*`) use `AllowAny` permissions, consistent with the existing order endpoints. The `slug` + `table_identifier` combination serves as the access scope — a customer must know both to interact with a tab. This matches the existing security model where QR code scanning provides implicit authorization.

Staff endpoints (`/api/kitchen/tab/{tab_id}/close/`) require `IsAuthenticated` + restaurant staff membership, consistent with existing kitchen endpoints.

For `pay_by_item`, the tab remains in `closing` status until all items are paid. Unpaid items are the responsibility of remaining customers at the table. If all customers leave without paying, staff can use the "mark as unpaid" action.

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
4. When sum of paid TabPayments >= tab total -> tab status = `closed`, all orders' `payment_status` updated from `deferred` -> `paid`, and `paid_at` set on each order

### Split-even rounding

Last payer's amount is adjusted to cover the exact remainder, not `total / N`. This avoids overpayment from rounding.

### Split-even sharing

Tab page shows a shareable link or QR code so other people at the table can pay their portion from their own devices.

## Frontend Changes

### Order store additions

- `paymentModel: "upfront" | "tab"` — from menu fetch
- `tabId: string | null`
- `tabOrders: Order[]` — all orders on current tab (each Order contains its own items)
- `tabTotal: string`
- `tabAmountPaid: string` — for split payment progress
- `tabAmountRemaining: string`
- New step: `"tab_review"`

### New components

- **`TabReviewStep.tsx`** — all orders on tab grouped by order, total, payment progress, payment action buttons
- **`SplitEvenModal.tsx`** — input for N people, per-person amount, share link
- **`PayByItemModal.tsx`** — checkboxes for each OrderItem across all tab orders, running selected total
- **`TabStatusBar.tsx`** — persistent bar during ordering: "Tab open - $X.XX so far"

### Modified components

- **`PaymentStep.tsx`** — add TabPayment code path using TabPayment's `client_secret`
- **`CartBottomBar.tsx`** — tab mode: "Place Order" instead of "Proceed to Payment"
- **`SubmittedStep.tsx`** — tab mode: "Order More" and "View Tab & Pay" buttons
- **`WelcomeStep.tsx`** — detect open tab on load, offer shortcut to resume

## Webhook Handling

The existing `payment_intent.succeeded` webhook handler dispatches based on which model owns the `stripe_payment_intent_id`:

1. Try `Order.objects.get(stripe_payment_intent_id=intent["id"])` — if found, use existing `_handle_payment_succeeded` handler
2. If `Order.DoesNotExist`, try `TabPayment.objects.get(stripe_payment_intent_id=intent["id"])` — if found, use `_handle_tab_payment_succeeded`
3. If neither found, log warning and return (may be a subscription or other event)

**`_handle_tab_payment_succeeded(intent)`:**
- Find TabPayment, mark `paid`, set `paid_at`
- Sum all paid TabPayments for the tab
- If sum >= tab total: set tab status = `closed`, `closed_at` = now, update all tab orders from `deferred` -> `paid` with `paid_at` set
- Broadcast tab update via WebSocket

**`_handle_tab_payment_failed(intent)`:**
- Mark TabPayment `failed`, tab stays `closing` for retry

## WebSocket Broadcasts

Tab events broadcast to the relevant table's channel:

- **`tab.order_added`** — when a new order is placed on the tab (updates running total for anyone viewing the tab)
- **`tab.closing`** — when close is initiated (notifies all devices at the table)
- **`tab.payment_received`** — when a split payment is completed (updates progress for remaining payers)
- **`tab.closed`** — when fully paid (final confirmation to all devices)

Kitchen channel receives existing order events — no tab-specific broadcasts needed for kitchen since orders are already sent individually.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Order placed while tab is `closing` | Rejected — "Tab is being closed" |
| Staff closes tab, customer hasn't paid | Tab = `closing`, customer sees payment prompt on next page load |
| Split-even rounding | Last payer covers exact remainder |
| Customer abandons tab | Staff can close from admin. Unpaid tabs stay `closing`. Staff can "mark as unpaid" to force-close. |
| Payment model switched with open tabs | Existing tabs continue until closed. New orders follow new model. |
| No open tab + tab mode | Tab auto-created on first order |
| POS-collected + tab mode | Tab tracks orders, closing marks all as `pos_collected` (no Stripe). `confirm/` endpoint handles this. |
| `pay_by_item` with items left unpaid | Tab stays `closing` until all items covered. Remaining customers pay or staff force-closes. |

## POS-Collected + Tab Interaction

`payment_mode` (stripe vs pos_collected) = HOW payment happens.
`payment_model` (upfront vs tab) = WHEN payment happens.

A restaurant using POS-collected payment with tab mode: customers order multiple times via QR, food goes to kitchen, all tracked on a tab. When closing, everything is marked `pos_collected` — no Stripe PaymentIntent needed. Payment is handled at the physical register. The `POST /api/order/{slug}/confirm/` endpoint handles this path, linking orders to the tab while setting `pos_collected` status.
