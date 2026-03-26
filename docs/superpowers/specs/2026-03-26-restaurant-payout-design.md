# Restaurant Payout System Design

## Overview

Daily payout system for restaurants using Stripe Connect with separate charges and transfers. The platform collects payments from diners into the platform Stripe account, holds funds until settlement (T+2), then transfers to restaurant connected accounts on a daily schedule via a Celery Beat job.

## Key Decisions

- **Model:** Marketplace with separate charges and transfers (Stripe Connect)
- **Fee structure:** 0% initially, designed for configurable percentage + fixed fees per restaurant
- **Payout trigger:** Platform-controlled daily Celery Beat job (not Stripe auto-payouts)
- **Settlement window:** T+2 (only pay out orders whose funds have settled, anchored on payment confirmation time)
- **Failure handling:** Flag immediately, notify restaurant owner, no auto-retry
- **Restaurant visibility:** Minimal dashboard in-app + Stripe Express Dashboard link

## Architecture

### Stripe Connect Account Type

Express accounts. Stripe hosts the onboarding (identity verification, bank details) and provides a hosted dashboard for payout history and tax forms.

### Money Flow

```
Diner pays → PaymentIntent (standard, no transfer_data) →
Funds land in platform Stripe account → T+2 settlement →
Daily Celery job creates stripe.Transfer to connected account →
Stripe auto-pays out from connected account to restaurant bank
```

Key distinction: PaymentIntents are created as standard charges on the platform account. The daily job handles all fund movement via `stripe.Transfer.create()`. This gives the platform full control over timing and fee deductions.

### Fallback

Restaurants without a connected account (or incomplete onboarding) continue to accept orders as today — funds stay in the platform account. The payout job skips them. Onboarding is not a prerequisite for taking orders.

## Data Models

### ConnectedAccount (restaurants app)

| Field | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| restaurant | OneToOne → Restaurant | |
| stripe_account_id | String | Stripe Connect Express account ID (acct_xxx) |
| onboarding_complete | Boolean | True when Stripe confirms verification |
| payouts_enabled | Boolean | Synced from Stripe account.payouts_enabled |
| charges_enabled | Boolean | Synced from Stripe account.charges_enabled |
| pending_refund_balance | Decimal | Running total of refunds not yet clawed back from payouts (default 0) |
| created_at | DateTime | |
| updated_at | DateTime | |

### Payout (restaurants app)

| Field | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| restaurant | FK → Restaurant | |
| stripe_transfer_id | String | Stripe Transfer ID (tr_xxx) |
| stripe_payout_id | String (nullable) | Stripe Payout ID (po_xxx) — set when payout.paid/payout.failed fires |
| amount | Decimal | Total payout amount |
| currency | String | e.g. "usd" |
| status | Enum | pending, in_transit, completed, failed |
| fee_amount | Decimal | Total fees deducted (default 0) |
| fee_rate | Decimal | Percentage rate applied (default 0) |
| fee_fixed | Decimal | Fixed per-order fee applied (default 0) |
| orders_count | Integer | Number of orders included |
| period_start | Date | Earliest order date in this payout |
| period_end | Date | Latest order date in this payout |
| created_at | DateTime | |

Status transitions: `pending` → `in_transit` (transfer accepted by Stripe) → `completed` (funds deposited to bank) or `failed`.

### Order Model Changes

| Field | Type | Description |
|---|---|---|
| payout_status | Enum | pending, transferred, paid_out, failed |
| payout | FK → Payout (nullable) | Links order to its payout |
| paid_at | DateTime (nullable) | Timestamp when payment_status became 'paid' — anchors T+2 settlement window |

### Migration Strategy for Existing Orders

The `payout_status` field defaults to `transferred` for all existing orders so the payout job ignores historical orders that were charged without connected accounts. The `paid_at` field defaults to `null` for existing orders (they are already excluded by the `payout_status` filter).

## Stripe Connect Onboarding

### Flow

1. Restaurant owner clicks "Set up payouts" in dashboard
2. `POST /api/restaurants/<slug>/connect/onboard/` → backend creates Express account via `stripe.Account.create(type="express")`, saves ConnectedAccount, generates Account Link, returns onboarding URL
3. Owner completes Stripe's hosted onboarding (identity + bank details)
4. Stripe redirects back to app (success or refresh URL)
5. Webhook `account.updated` → backend updates ConnectedAccount fields

### Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/restaurants/<slug>/connect/onboard/` | Create Express account + return onboarding URL |
| GET | `/api/restaurants/<slug>/connect/status/` | Return onboarding and payout status |
| POST | `/api/restaurants/<slug>/connect/dashboard/` | Generate Stripe Express Dashboard login link |

## Payment Flow

### No changes to OrderService.create_payment_intent()

PaymentIntents are created exactly as today — standard charges on the platform account. No `transfer_data` or `destination` parameters. Funds accumulate in the platform Stripe balance.

The `paid_at` field must be set to `timezone.now()` in both code paths that transition an order to `paid`:
1. `OrderService._handle_payment_succeeded()` — the `payment_intent.succeeded` webhook handler
2. `OrderService.confirm_payment()` — the synchronous payment confirmation path

Both paths must be updated to include `paid_at=timezone.now()` in their Order update calls.

## Daily Payout Job

### Schedule

Celery Beat task, runs daily at 2:00 AM UTC.

### Algorithm

For each restaurant with `ConnectedAccount.payouts_enabled=True`:

1. Query orders where:
   - `payment_status = 'paid'`
   - `payout_status = 'pending'`
   - `paid_at <= now() - 2 days` (T+2 settlement window, anchored on payment time)

2. Calculate total: `sum(order.total_price)` for eligible orders

3. Calculate fees (future):
   ```
   per_order_fee = (order.total_price * fee_rate) + fee_fixed
   transfer_amount = total - sum(per_order_fees)
   ```
   Currently: `transfer_amount = total`, `fee_amount = 0`

   Validation: if computed fees exceed 50% of any order total, log a warning and skip the restaurant for manual review.

4. If transfer_amount > 0:
   - Create `Payout` record (status=pending)
   - Call `stripe.Transfer.create(amount=transfer_amount_cents, currency=currency, destination=stripe_account_id, idempotency_key=f"payout-{restaurant_id}-{date}", metadata={...})`
   - Update `Payout.stripe_transfer_id`
   - Update all included orders: `payout_status='transferred'`, `payout=payout`

5. On API failure:
   - Set `Payout.status = 'failed'`
   - Leave orders as `payout_status = 'pending'` (picked up next run)
   - Log error, send failure notification

### Idempotency

The `idempotency_key` (`payout-{restaurant_id}-{date.today().isoformat()}`, e.g., `payout-abc123-2026-03-27`) ensures that if the job runs twice on the same day for the same restaurant, Stripe returns the same Transfer rather than creating a duplicate. A database-level advisory lock (or Redis lock) is acquired per-restaurant before processing to prevent concurrent execution.

### Task Location

`restaurants/tasks.py` — the task lives in the restaurants app alongside the Payout and ConnectedAccount models, since the payout job is fundamentally a restaurant financial operation. It queries Order records cross-app, which is a standard Django pattern.

### Fee Configuration (future-ready)

Fee settings will live on the Restaurant or Subscription model (per-restaurant configurable). The `PAYOUT_CONFIG` in settings provides defaults.

## Refund Handling

If an order is refunded after being included in a payout:
- The refund is processed as today (via Stripe refund on the PaymentIntent)
- The refunded amount is deducted from the restaurant's next payout. The daily job checks for orders with `payment_status='refunded'` and `payout_status='transferred'`, sums refund amounts, and subtracts from the next transfer.
- A `pending_refund_balance` Decimal field on ConnectedAccount tracks the running total of refunds not yet clawed back. Updated when refunds occur, drawn down when deducted from payouts. This avoids re-querying historical refunds on every run.
- If no future payout is large enough to cover the deduction, the remaining balance carries forward until it can be recovered.
- Edge case: if a restaurant has no future orders, a Stripe Transfer Reversal can be issued manually by an admin.

## Webhook Additions

### Connect Webhook Endpoint

A separate webhook endpoint is registered for Stripe Connect events:
- `POST /api/webhooks/stripe-connect/` with its own signing secret (`STRIPE_CONNECT_WEBHOOK_SECRET`)
- This receives events from connected accounts (prefixed with the connected account context)

The existing `POST /api/webhooks/stripe/` continues to handle platform-level events.

### Event Handlers

Two webhook handler methods:
- `OrderService.handle_stripe_webhook(payload, sig_header)` — existing, uses `STRIPE_WEBHOOK_SECRET` for platform events
- `OrderService.handle_stripe_connect_webhook(payload, sig_header)` — new, uses `STRIPE_CONNECT_WEBHOOK_SECRET` for Connect events

Both share the same dispatcher pattern but verify signatures with their respective secrets. The Connect webhook view at `/api/webhooks/stripe-connect/` calls the new method.

Event routing:

| Event | Source | Action |
|---|---|---|
| `account.updated` | Connect | Update ConnectedAccount: payouts_enabled, charges_enabled, onboarding_complete |
| `transfer.created` | Platform | Set Payout.status='in_transit' |
| `transfer.failed` | Platform | Set Payout.status='failed', revert orders to payout_status='pending', send failure notification |
| `payout.paid` | Connect | Correlate via connected account ID + amount + time window to find matching Payout record. Set stripe_payout_id, Payout.status='completed', update orders payout_status='paid_out', send success notification |
| `payout.failed` | Connect | Same correlation. Set Payout.status='failed', send failure notification |

## Notifications

Email-based (Django email backend):

| Trigger | Recipient | Message |
|---|---|---|
| Payout completed (payout.paid) | Restaurant owner | "Your daily payout of $X has been deposited to your bank account" |
| Payout failed | Restaurant owner | "Your payout of $X failed. Please check your bank details." |
| Onboarding reminder (7 days, has orders, no connected account) | Restaurant owner | Nudge to complete payout setup |

## Restaurant Dashboard

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/restaurants/<slug>/payouts/` | Paginated payout list (amount, status, date, order count) |
| GET | `/api/restaurants/<slug>/payouts/<id>/` | Single payout detail with included orders |

### Frontend

"Payouts" tab in restaurant dashboard:
- Summary cards: total paid out, next estimated payout, pending amount
- Table: date, amount, order count, status
- Prominent "View full details in Stripe" button (links to Express Dashboard)

## Infrastructure Setup

### Celery Configuration

1. Create `backend/config/celery.py` — Celery app initialization, autodiscover tasks
2. Update `backend/config/__init__.py` — Import Celery app so it loads on Django startup
3. Add `django_celery_beat` to `INSTALLED_APPS`
4. Configure Beat schedule in `settings.py`:
   ```python
   CELERY_BROKER_URL = env("REDIS_URL")
   CELERY_BEAT_SCHEDULE = {
       "daily-restaurant-payouts": {
           "task": "restaurants.tasks.process_daily_payouts",
           "schedule": crontab(hour=2, minute=0),  # 2:00 AM UTC
       },
   }
   ```

### Docker Compose Services

Add two new services to `docker-compose.yml`:
- `celery-worker` — Runs `celery -A config worker`
- `celery-beat` — Runs `celery -A config beat`

Both use the same backend image and depend on Redis and PostgreSQL.

## Configuration

```python
# config/settings.py
PAYOUT_CONFIG = {
    "settlement_days": 2,          # T+2 window
    "job_run_hour_utc": 2,         # 2:00 AM UTC
    "default_fee_rate": 0,         # 0% for now
    "default_fee_fixed_cents": 0,  # $0 for now
}

STRIPE_CONNECT_WEBHOOK_SECRET = env("STRIPE_CONNECT_WEBHOOK_SECRET")
```

## Dependencies

- `stripe` (already installed) — Connect API
- `celery` + `django-celery-beat` (new) — Task scheduling
- `redis` (already configured) — Celery broker

## Security Considerations

- Stripe Connect account IDs and transfer IDs are not sensitive (safe to store in DB)
- Webhook signature verification: existing endpoint uses `STRIPE_WEBHOOK_SECRET`, new Connect endpoint uses `STRIPE_CONNECT_WEBHOOK_SECRET` — both verified via `stripe.Webhook.construct_event()`
- Connected account onboarding URLs are short-lived (Stripe enforces this)
- Express Dashboard login links are single-use and expire
- No bank account numbers are stored in our database — Stripe handles all PII
- Idempotency keys and advisory locks prevent duplicate payouts
