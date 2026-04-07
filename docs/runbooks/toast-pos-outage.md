# Toast POS Outage / Rollback Runbook

## Overview

This runbook covers how to respond to Toast POS integration failures, including how to disable the integration without redeployment and how to recover.

## Detection

**Automated alerts:**
- Celery Beat task `check_toast_health` runs every 5 minutes
- Fires a `toast_health_alert` log event (CRITICAL level) when Toast error rate exceeds 5% over a 5-minute window
- Search structured logs for `"event": "toast_health_alert"` or `"event": "toast_api_error"`

**Manual checks:**
- Check `POSSyncLog` entries in Django admin for recent `FAILED` or `RETRYING` status
- Query: `POSSyncLog.objects.filter(status__in=["failed", "retrying"], created_at__gte=now - timedelta(hours=1))`

## Immediate Rollback (No Redeployment)

Set the `TOAST_POS_ENABLED` environment variable to `False` in the Render dashboard:

1. Go to [Render Dashboard](https://dashboard.render.com) → menuchat-backend → Environment
2. Set `TOAST_POS_ENABLED` = `False`
3. Restart the service (Settings → Manual Deploy or Restart)

**Effect:** The `ENABLED_POS_VENDORS` set will no longer include `toast`. New restaurants cannot select Toast as their POS. Existing Toast connections remain in the database but the dispatch service will still route to the Toast adapter if a connection is active. To fully stop dispatches for existing connections, also deactivate connections:

```python
# Django shell
from integrations.models import POSConnection
POSConnection.objects.filter(pos_type="toast", is_active=True).update(is_active=False)
```

## Secrets

| Variable | Description | Where Set |
|---|---|---|
| `POS_TOAST_CLIENT_ID` | Toast machine client ID | Render env vars (staging + prod) |
| `POS_TOAST_CLIENT_SECRET` | Toast machine client secret | Render env vars (staging + prod) |
| `POS_TOAST_RESTAURANT_GUID` | Default restaurant GUID (per-connection GUID stored in `external_location_id`) | Render env vars |
| `TOAST_POS_ENABLED` | Feature flag — `True` in staging, `False` in prod until QA sign-off | Render env vars |
| `POS_ENCRYPTION_KEY` | Fernet key for encrypting OAuth tokens at rest | Render env vars |

**Security notes:**
- Secrets are never logged. The adapter scrubs `clientId` and `clientSecret` from error payloads before logging.
- OAuth tokens are encrypted at rest using `POS_ENCRYPTION_KEY` (Fernet symmetric encryption).

## Observability

### Structured Log Events

All Toast logs are JSON-formatted with these common fields: `event`, `pos_type`, `restaurant_id`, `latency_ms`, `status_code`.

| Event | Level | Description |
|---|---|---|
| `toast_auth_success` | INFO | Successful machine client auth |
| `toast_auth_error` | WARNING | Auth failure (bad creds, Toast down) |
| `toast_api_call` | INFO | Successful API call with latency |
| `toast_api_error` | WARNING | 4xx/5xx response from Toast |
| `toast_order_pushed` | INFO | Order successfully pushed to Toast |
| `toast_order_push_failed` | WARNING | Order push failed |
| `toast_cancel_failed` | ERROR | Order cancellation failed |
| `toast_token_refresh_failed` | ERROR | Token refresh failed |
| `toast_health_ok` | INFO | Health check passed |
| `toast_health_alert` | CRITICAL | Error rate above 5% threshold |

### Key Queries (Log Aggregator)

```
# Error rate over last hour
event:toast_api_error OR event:toast_api_call | stats count by event

# Latency p99
event:toast_api_call | percentile(latency_ms, 99)

# Failed orders
event:toast_order_push_failed | count by restaurant_id
```

## Recovery Steps

1. **Check Toast status page** — Verify if Toast is experiencing an outage
2. **Check credentials** — Ensure `POS_TOAST_CLIENT_ID` and `POS_TOAST_CLIENT_SECRET` are correct and not expired
3. **Check sandbox vs production URL** — `POS_TOAST_API_BASE_URL` should point to `https://ws-sandbox-api.eng.toasttab.com` for staging or `https://ws-api.toasttab.com` for production
4. **Re-enable** — Set `TOAST_POS_ENABLED=True` in Render and restart
5. **Retry failed orders** — Orders with `pos_sync_status=failed` can be retried by triggering the Celery task:

```python
from integrations.tasks import dispatch_order_to_pos
from orders.models import Order

failed = Order.objects.filter(pos_sync_status="failed")
for order in failed:
    dispatch_order_to_pos.delay(str(order.id))
```

## Escalation

- **On-call SRE** — Check Slack `#oncall` channel
- **Toast Support** — https://pos.toasttab.com/support (requires partner credentials)
