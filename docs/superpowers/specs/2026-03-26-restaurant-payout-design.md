# Restaurant Payout System Design

## Overview

Daily payout system for restaurants using Stripe Connect with destination charges. The platform collects payments from diners, holds funds until settlement, then transfers to restaurant bank accounts on a daily schedule.

## Key Decisions

- **Model:** Marketplace with destination charges (Stripe Connect)
- **Fee structure:** 0% initially, designed for configurable percentage + fixed fees per restaurant
- **Payout trigger:** Platform-controlled daily Celery Beat job (not Stripe auto-payouts)
- **Settlement window:** T+2 (only pay out orders whose funds have settled)
- **Failure handling:** Flag immediately, notify restaurant owner, no auto-retry
- **Restaurant visibility:** Minimal dashboard in-app + Stripe Express Dashboard link

## Architecture

### Stripe Connect Account Type

Express accounts. Stripe hosts the onboarding (identity verification, bank details) and provides a hosted dashboard for payout history and tax forms.

### Money Flow

```
Diner pays → PaymentIntent with transfer_data[destination] →
Funds land in platform account → T+2 settlement →
Daily job creates Transfer to connected account →
Stripe auto-pays out from connected account to restaurant bank
```

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
| created_at | DateTime | |
| updated_at | DateTime | |

### Payout (orders app)

| Field | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| restaurant | FK → Restaurant | |
| stripe_transfer_id | String | Stripe Transfer ID (tr_xxx) |
| amount | Decimal | Total payout amount |
| currency | String | e.g. "usd" |
| status | Enum | pending, completed, failed |
| fee_amount | Decimal | Total fees deducted (default 0) |
| fee_rate | Decimal | Percentage rate applied (default 0) |
| fee_fixed | Decimal | Fixed per-order fee applied (default 0) |
| orders_count | Integer | Number of orders included |
| period_start | Date | Earliest order date in this payout |
| period_end | Date | Latest order date in this payout |
| created_at | DateTime | |

### Order Model Changes

| Field | Type | Description |
|---|---|---|
| payout_status | Enum | pending, transferred, paid_out, failed |
| payout | FK → Payout (nullable) | Links order to its payout |

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

## Modified Payment Flow

### Changes to OrderService.create_payment_intent()

When creating a PaymentIntent, if the restaurant has a connected account with `charges_enabled=True`:

```python
stripe.PaymentIntent.create(
    amount=total_cents,
    currency=currency,
    # ... existing params ...
    transfer_data={"destination": connected_account.stripe_account_id},
    # application_fee_amount=fee_cents,  # future: uncomment when fees enabled
)
```

If no connected account exists, the PaymentIntent is created as today (no transfer_data). Funds stay in platform account.

## Daily Payout Job

### Schedule

Celery Beat task, runs daily at 2:00 AM UTC.

### Algorithm

For each restaurant with `ConnectedAccount.payouts_enabled=True`:

1. Query orders where:
   - `payment_status = 'paid'`
   - `payout_status = 'pending'`
   - `created_at <= now() - 2 days` (T+2 settlement window)

2. Calculate total: `sum(order.total_price)` for eligible orders

3. Calculate fees (future):
   ```
   per_order_fee = (order.total_price * fee_rate) + fee_fixed
   transfer_amount = total - sum(per_order_fees)
   ```
   Currently: `transfer_amount = total`, `fee_amount = 0`

4. If transfer_amount > 0:
   - Create `Payout` record (status=pending)
   - Call `stripe.Transfer.create(amount=transfer_amount_cents, currency=currency, destination=stripe_account_id, metadata={...})`
   - Update `Payout.stripe_transfer_id`
   - Update all included orders: `payout_status='transferred'`, `payout=payout`

5. On API failure:
   - Set `Payout.status = 'failed'`
   - Leave orders as `payout_status = 'pending'` (picked up next run)
   - Log error

### Task Location

`orders/tasks.py`

### Fee Configuration (future-ready)

Fee settings will live on the Restaurant or Subscription model (per-restaurant configurable). The `PAYOUT_CONFIG` in settings provides defaults.

## Webhook Additions

Added to existing `OrderService.handle_stripe_webhook()` dispatcher:

| Event | Action |
|---|---|
| `account.updated` | Update ConnectedAccount: payouts_enabled, charges_enabled, onboarding_complete |
| `transfer.created` | Set Payout.status='completed', update orders payout_status='transferred' |
| `transfer.failed` | Set Payout.status='failed', send failure notification to restaurant owner |

## Notifications

Email-based (Django email backend):

| Trigger | Recipient | Message |
|---|---|---|
| Payout completed | Restaurant owner | "Your daily payout of $X has been sent to your bank account" |
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

## Configuration

```python
# config/settings.py
PAYOUT_CONFIG = {
    "settlement_days": 2,          # T+2 window
    "job_run_hour_utc": 2,         # 2:00 AM UTC
    "default_fee_rate": 0,         # 0% for now
    "default_fee_fixed_cents": 0,  # $0 for now
}
```

## Dependencies

- `stripe` (already installed) — Connect API
- `celery` + `django-celery-beat` (new) — Task scheduling
- `redis` (already configured) — Celery broker

## Security Considerations

- Stripe Connect account IDs and transfer IDs are not sensitive (safe to store in DB)
- Webhook signature verification already implemented — reuse for new events
- Connected account onboarding URLs are short-lived (Stripe enforces this)
- Express Dashboard login links are single-use and expire
- No bank account numbers are stored in our database — Stripe handles all PII
