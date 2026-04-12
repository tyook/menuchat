# Subscription Gate Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Block the public ordering page when a restaurant's subscription is inactive, send emails on payment success/failure, and display billing history on the billing page.

**Architecture:** Add a subscription check to `PublicMenuView` that returns `{ available: false }` for inactive subscriptions. Add payment success/failure notification emails triggered by existing Stripe webhook handlers. Add a new API endpoint that fetches invoices from Stripe and a billing history table on the existing billing page.

**Tech Stack:** Django REST Framework, Stripe Python SDK, Celery, Next.js 14, TypeScript, React Query, Tailwind CSS, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-04-11-subscription-gate-design.md`

---

## Chunk 1: Backend Subscription Gate

### Task 1: Extract `is_subscription_active()` helper and refactor `check_subscription()`

**Files:**
- Modify: `backend/orders/services.py:313-338`
- Test: `backend/restaurants/tests/test_subscription_gate.py`

- [ ] **Step 1: Write tests for `is_subscription_active()`**

Add a new test class to `backend/restaurants/tests/test_subscription_gate.py`:

```python
@pytest.mark.django_db
class TestIsSubscriptionActive:
    def test_active_subscription_returns_true(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        assert OrderService.is_subscription_active(restaurant) is True

    def test_canceled_subscription_returns_false(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        assert OrderService.is_subscription_active(restaurant) is False

    def test_expired_trial_returns_false(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() - timedelta(days=1),
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        assert OrderService.is_subscription_active(restaurant) is False

    def test_active_trial_returns_true(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() + timedelta(days=7),
            current_period_start=timezone.now() - timedelta(days=7),
            current_period_end=timezone.now() + timedelta(days=7),
        )
        assert OrderService.is_subscription_active(restaurant) is True

    def test_no_subscription_returns_true(self):
        restaurant = RestaurantFactory()
        assert OrderService.is_subscription_active(restaurant) is True

    def test_past_due_returns_true(self):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="past_due",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        assert OrderService.is_subscription_active(restaurant) is True
```

Add this import at the top of the test file:

```python
from orders.services import OrderService
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_gate.py::TestIsSubscriptionActive -v`

Expected: FAIL — `AttributeError: type object 'OrderService' has no attribute 'is_subscription_active'`

- [ ] **Step 3: Implement `is_subscription_active()` and refactor `check_subscription()`**

In `backend/orders/services.py`, replace lines 313-338 (the `check_subscription` method and its section comment) with:

```python
    # ── Subscription Check ─────────────────────────────────────────

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

    @staticmethod
    def check_subscription(restaurant: Restaurant) -> Subscription | None:
        """Check that the restaurant's subscription is active.

        Raises PermissionDenied if subscription is inactive or trial expired.
        Returns the subscription (or None for legacy restaurants).
        """
        if not OrderService.is_subscription_active(restaurant):
            try:
                subscription = restaurant.subscription
                if subscription.status == "trialing":
                    raise PermissionDenied(
                        "Free trial has expired. Please subscribe to continue."
                    )
            except Subscription.DoesNotExist:
                pass
            raise PermissionDenied(
                "Subscription is not active. Please subscribe to continue."
            )
        try:
            return restaurant.subscription
        except Subscription.DoesNotExist:
            return None
```

- [ ] **Step 4: Run all subscription gate tests**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_gate.py -v`

Expected: ALL PASS (both `TestIsSubscriptionActive` and existing `TestSubscriptionGate` tests)

- [ ] **Step 5: Commit**

```bash
git add backend/orders/services.py backend/restaurants/tests/test_subscription_gate.py
git commit -m "refactor: extract is_subscription_active() helper from check_subscription()"
```

---

### Task 2: Add subscription check to `PublicMenuView`

**Files:**
- Modify: `backend/orders/views.py:21-25`
- Test: `backend/restaurants/tests/test_subscription_gate.py`

- [ ] **Step 1: Write tests for menu endpoint subscription gate**

Add to `backend/restaurants/tests/test_subscription_gate.py`:

```python
@pytest.mark.django_db
class TestPublicMenuSubscriptionGate:
    def test_menu_returns_available_true_when_active(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is True
        assert "categories" in response.data

    def test_menu_returns_available_false_when_canceled(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="canceled",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is False
        assert response.data["restaurant_name"] == restaurant.name
        assert "categories" not in response.data

    def test_menu_returns_available_false_when_trial_expired(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            trial_end=timezone.now() - timedelta(days=1),
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() - timedelta(days=1),
        )
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is False

    def test_menu_returns_available_true_when_no_subscription(self, api_client):
        restaurant = _setup_restaurant_with_menu()
        response = api_client.get(f"/api/order/{restaurant.slug}/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] is True
        assert "categories" in response.data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_gate.py::TestPublicMenuSubscriptionGate -v`

Expected: FAIL — `available` key not present in response

- [ ] **Step 3: Implement subscription check in `PublicMenuView`**

In `backend/orders/views.py`, replace the `PublicMenuView` class (lines 21-25):

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

- [ ] **Step 4: Run tests**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_gate.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/views.py backend/restaurants/tests/test_subscription_gate.py
git commit -m "feat: add subscription check to PublicMenuView"
```

---

## Chunk 2: Frontend Subscription Gate

### Task 3: Add frontend types and update API client

**Files:**
- Modify: `frontend/src/types/index.ts:95-102`
- Modify: `frontend/src/lib/api.ts:239-241`
- Modify: `frontend/src/hooks/use-menu.ts`

- [ ] **Step 1: Add `MenuUnavailable` type and update `PublicMenu`**

In `frontend/src/types/index.ts`, add before the `PublicMenu` interface (before line 95):

```ts
export interface MenuUnavailable {
  available: false;
  restaurant_name: string;
}
```

Update the existing `PublicMenu` interface (lines 95-102) to add `available`:

```ts
export interface PublicMenu {
  available: true;
  restaurant_name: string;
  tax_rate: string;
  payment_mode: "stripe" | "pos_collected";
  payment_model: "upfront" | "tab";
  payment_ready: boolean;
  categories: MenuCategory[];
}
```

- [ ] **Step 2: Update `fetchMenu` return type**

In `frontend/src/lib/api.ts`, update the `fetchMenu` function (line 239):

```ts
export async function fetchMenu(slug: string): Promise<PublicMenu | MenuUnavailable> {
  return apiFetch<PublicMenu | MenuUnavailable>(`/api/order/${slug}/menu/`);
}
```

Add `MenuUnavailable` to the imports from `@/types` at the top of the file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat: add MenuUnavailable type and update fetchMenu return type"
```

---

### Task 4: Handle unavailable state in `OrderPageClient`

**Files:**
- Modify: `frontend/src/app/order/[slug]/OrderPageClient.tsx:46-60`

- [ ] **Step 1: Add unavailable check**

In `frontend/src/app/order/[slug]/OrderPageClient.tsx`, add a check after the loading block (after line 52) and before the error block (line 54). Replace lines 54-59 with:

```tsx
  if (menu && menu.available === false) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-4 text-center">
        <h1 className="text-xl font-semibold mb-2">{menu.restaurant_name}</h1>
        <p className="text-muted-foreground">
          This restaurant is not currently accepting online orders.
        </p>
      </div>
    );
  }

  if (error || !menu) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Restaurant not found.</p>
      </div>
    );
  }
```

- [ ] **Step 2: Update menu property accesses to narrow the type**

Later in the component, accesses like `menu.payment_model`, `menu.categories`, `menu.tax_rate`, etc. need the type narrowed. Since we return early when `menu.available === false`, TypeScript already narrows `menu` to `PublicMenu` after that check. Verify the component compiles without type errors.

Run: `cd /Users/k.yook/projects/ai-qr-ordering/frontend && npx tsc --noEmit`

Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/order/[slug]/OrderPageClient.tsx
git commit -m "feat: show unavailable message when restaurant subscription is inactive"
```

---

## Chunk 3: Payment Failure Email

### Task 5: Add payment failure notification and Celery task

**Files:**
- Modify: `backend/restaurants/notifications.py`
- Modify: `backend/restaurants/tasks.py`
- Create: `backend/orders/templates/emails/payment_failed.html`

- [ ] **Step 1: Add `send_payment_failed_email()` to notifications**

Add to `backend/restaurants/notifications.py`:

```python
def send_payment_failed_email(restaurant) -> None:
    """Notify restaurant owner that their subscription payment failed."""
    owner = restaurant.owner
    if not owner.email:
        return

    context = {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_name": owner.first_name or owner.name or "",
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/payment_failed.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"Payment failed — {restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send payment failed email for %s", restaurant.slug)
```

- [ ] **Step 2: Add Celery task**

Add to `backend/restaurants/tasks.py`:

```python
@shared_task
def send_payment_failed_email_task(restaurant_id: str):
    """Send payment failed email after subscription goes past_due (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_payment_failed_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_payment_failed_email
    send_payment_failed_email(restaurant)
```

- [ ] **Step 3: Create email template**

Create `backend/orders/templates/emails/payment_failed.html` following the style of `subscription_activated.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Payment Failed</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;max-width:100%;">

<!-- Header -->
<tr><td style="background-color:#dc2626;padding:24px 32px;">
  <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;">Payment Failed</h1>
</td></tr>

<!-- Body -->
<tr><td style="padding:32px;">
  <p style="margin:0 0 16px;color:#18181b;font-size:16px;">Hi {{ owner_name|default:"there" }},</p>
  <p style="margin:0 0 24px;color:#52525b;font-size:14px;line-height:1.6;">
    Your subscription payment for <strong>{{ restaurant_name }}</strong> has failed. Please update your payment method to avoid service interruption.
  </p>
  <p style="margin:0 0 24px;color:#52525b;font-size:14px;line-height:1.6;">
    If your payment method is not updated, your restaurant will stop accepting online orders.
  </p>

  <p style="margin:0;text-align:center;">
    <a href="{{ frontend_url }}/account/restaurants/{{ restaurant_slug }}/billing" style="display:inline-block;padding:12px 24px;background-color:#18181b;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">Update Payment Method</a>
  </p>
</td></tr>

<!-- Footer -->
<tr><td style="padding:16px 32px;background-color:#fafafa;border-top:1px solid #e4e4e7;">
  <p style="margin:0;color:#a1a1aa;font-size:12px;text-align:center;">
    {{ restaurant_name }} &mdash; Powered by MenuChat
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
```

- [ ] **Step 4: Commit**

```bash
git add backend/restaurants/notifications.py backend/restaurants/tasks.py backend/orders/templates/emails/payment_failed.html
git commit -m "feat: add payment failure email notification and template"
```

---

### Task 6: Trigger payment failure email from webhook handler

**Files:**
- Modify: `backend/orders/services.py:676-702`
- Test: `backend/restaurants/tests/test_subscription_webhooks.py`

- [ ] **Step 1: Write test for payment failure email trigger**

Add to `backend/restaurants/tests/test_subscription_webhooks.py`:

```python
    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_failed_email_task.delay")
    def test_subscription_updated_to_past_due_sends_email(self, mock_email_task, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test456",
            stripe_customer_id="cus_test456",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test456",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "metadata": {"plan": "growth"},
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_called_once_with(str(restaurant.id))

    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_failed_email_task.delay")
    def test_subscription_updated_past_due_to_past_due_no_duplicate_email(self, mock_email_task, mock_construct, api_client):
        """No duplicate email if already past_due."""
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="past_due",
            stripe_subscription_id="sub_test789",
            stripe_customer_id="cus_test789",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test789",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "metadata": {"plan": "growth"},
                }
            },
        }

        api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        mock_email_task.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_webhooks.py::TestSubscriptionWebhooks::test_subscription_updated_to_past_due_sends_email -v`

Expected: FAIL — `send_payment_failed_email_task.delay` not called

- [ ] **Step 3: Update `_handle_subscription_updated` to trigger email**

In `backend/orders/services.py`, modify `_handle_subscription_updated` (lines 676-702). Capture the old status before saving, then dispatch email if transitioning to `past_due`:

```python
    @staticmethod
    def _handle_subscription_updated(sub_data: dict) -> None:
        try:
            sub = Subscription.objects.get(
                stripe_subscription_id=sub_data["id"]
            )
            old_status = sub.status
            sub.status = sub_data["status"]
            sub.cancel_at_period_end = sub_data.get(
                "cancel_at_period_end", False
            )

            if sub_data.get("current_period_start"):
                sub.current_period_start = datetime.fromtimestamp(
                    sub_data["current_period_start"], tz=UTC
                )
            if sub_data.get("current_period_end"):
                sub.current_period_end = datetime.fromtimestamp(
                    sub_data["current_period_end"], tz=UTC
                )

            plan = sub_data.get("metadata", {}).get("plan")
            if plan and plan in ("starter", "growth", "pro"):
                sub.plan = plan

            sub.save()

            # Send payment failed email on transition to past_due
            if sub.status == "past_due" and old_status != "past_due":
                from restaurants.tasks import send_payment_failed_email_task
                send_payment_failed_email_task.delay(str(sub.restaurant_id))

        except Subscription.DoesNotExist:
            pass
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_webhooks.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/services.py backend/restaurants/tests/test_subscription_webhooks.py
git commit -m "feat: trigger payment failure email when subscription transitions to past_due"
```

---

## Chunk 4: Payment Success Email

### Task 7: Add payment success notification and Celery task

**Files:**
- Modify: `backend/restaurants/notifications.py`
- Modify: `backend/restaurants/tasks.py`
- Create: `backend/orders/templates/emails/payment_success.html`

- [ ] **Step 1: Add `send_payment_success_email()` to notifications**

Add to `backend/restaurants/notifications.py`:

```python
def send_payment_success_email(restaurant, amount_cents: int, plan: str, period_end_timestamp: int) -> None:
    """Notify restaurant owner that their subscription payment was received."""
    owner = restaurant.owner
    if not owner.email:
        return

    plan_config = settings.SUBSCRIPTION_PLANS.get(plan, {})
    plan_name = plan_config.get("name", plan.title())
    amount = f"${amount_cents / 100:,.2f}"
    from datetime import datetime, UTC
    period_end = datetime.fromtimestamp(period_end_timestamp, tz=UTC).strftime("%B %d, %Y")

    context = {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "owner_name": owner.first_name or owner.name or "",
        "amount": amount,
        "plan_name": plan_name,
        "period_end": period_end,
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/payment_success.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"Payment received — {restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send payment success email for %s", restaurant.slug)
```

- [ ] **Step 2: Add Celery task**

Add to `backend/restaurants/tasks.py`:

```python
@shared_task
def send_payment_success_email_task(restaurant_id: str, amount_cents: int, plan: str, period_end_timestamp: int):
    """Send payment success email after invoice paid (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_payment_success_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_payment_success_email
    send_payment_success_email(restaurant, amount_cents, plan, period_end_timestamp)
```

- [ ] **Step 3: Create email template**

Create `backend/orders/templates/emails/payment_success.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Payment Received</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;max-width:100%;">

<!-- Header -->
<tr><td style="background-color:#16a34a;padding:24px 32px;">
  <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;">Payment Received</h1>
</td></tr>

<!-- Body -->
<tr><td style="padding:32px;">
  <p style="margin:0 0 16px;color:#18181b;font-size:16px;">Hi {{ owner_name|default:"there" }},</p>
  <p style="margin:0 0 24px;color:#52525b;font-size:14px;line-height:1.6;">
    Your payment of <strong>{{ amount }}</strong> for <strong>{{ restaurant_name }}</strong> ({{ plan_name }} plan) has been received.
  </p>

  <div style="padding:20px;background-color:#f0fdf4;border-radius:8px;border:1px solid #bbf7d0;margin-bottom:24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td style="padding:4px 0;color:#52525b;font-size:14px;">Amount</td>
      <td style="padding:4px 0;color:#18181b;font-size:14px;font-weight:500;text-align:right;">{{ amount }}</td>
    </tr>
    <tr>
      <td style="padding:4px 0;color:#52525b;font-size:14px;">Plan</td>
      <td style="padding:4px 0;color:#18181b;font-size:14px;font-weight:500;text-align:right;">{{ plan_name }}</td>
    </tr>
    <tr>
      <td style="padding:4px 0;color:#52525b;font-size:14px;">Next billing date</td>
      <td style="padding:4px 0;color:#18181b;font-size:14px;font-weight:500;text-align:right;">{{ period_end }}</td>
    </tr>
    </table>
  </div>

  <p style="margin:0;text-align:center;">
    <a href="{{ frontend_url }}/account/restaurants/{{ restaurant_slug }}/billing" style="display:inline-block;padding:12px 24px;background-color:#18181b;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">View Billing</a>
  </p>
</td></tr>

<!-- Footer -->
<tr><td style="padding:16px 32px;background-color:#fafafa;border-top:1px solid #e4e4e7;">
  <p style="margin:0;color:#a1a1aa;font-size:12px;text-align:center;">
    {{ restaurant_name }} &mdash; Powered by MenuChat
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
```

- [ ] **Step 4: Commit**

```bash
git add backend/restaurants/notifications.py backend/restaurants/tasks.py backend/orders/templates/emails/payment_success.html
git commit -m "feat: add payment success email notification and template"
```

---

### Task 8: Trigger payment success email from `_handle_invoice_paid`

**Files:**
- Modify: `backend/orders/services.py:832-844`
- Test: `backend/restaurants/tests/test_subscription_webhooks.py`

- [ ] **Step 1: Write test for payment success email trigger**

Add to `backend/restaurants/tests/test_subscription_webhooks.py`:

```python
    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_success_email_task.delay")
    def test_invoice_paid_sends_success_email(self, mock_email_task, mock_construct, api_client):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_invoice_test",
            stripe_customer_id="cus_invoice_test",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=50,
        )

        period_end_ts = int((timezone.now() + timedelta(days=30)).timestamp())
        mock_construct.return_value = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "subscription": "sub_invoice_test",
                    "amount_paid": 9900,
                    "currency": "usd",
                    "lines": {
                        "data": [
                            {
                                "period": {"end": period_end_ts},
                            }
                        ]
                    },
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_called_once_with(
            str(restaurant.id), 9900, "growth", period_end_ts
        )

    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_success_email_task.delay")
    def test_invoice_paid_without_subscription_skips_email(self, mock_email_task, mock_construct, api_client):
        """Non-subscription invoices should not trigger email."""
        mock_construct.return_value = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "subscription": None,
                    "amount_paid": 500,
                    "currency": "usd",
                }
            },
        }

        api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        mock_email_task.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_webhooks.py::TestSubscriptionWebhooks::test_invoice_paid_sends_success_email -v`

Expected: FAIL — `send_payment_success_email_task.delay` not called

- [ ] **Step 3: Update `_handle_invoice_paid` to trigger email**

In `backend/orders/services.py`, replace `_handle_invoice_paid` (lines 832-844):

```python
    @staticmethod
    def _handle_invoice_paid(invoice: dict) -> None:
        subscription_id = invoice.get("subscription")
        if not subscription_id:
            return
        try:
            sub = Subscription.objects.get(
                stripe_subscription_id=subscription_id
            )
            sub.order_count = 0
            sub.save(update_fields=["order_count"])

            # Send payment success email
            amount_cents = invoice.get("amount_paid", 0)
            lines = invoice.get("lines", {}).get("data", [])
            period_end = lines[0].get("period", {}).get("end", 0) if lines else 0

            from restaurants.tasks import send_payment_success_email_task
            send_payment_success_email_task.delay(
                str(sub.restaurant_id), amount_cents, sub.plan, period_end
            )
        except Subscription.DoesNotExist:
            pass
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_webhooks.py -v`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/services.py backend/restaurants/tests/test_subscription_webhooks.py
git commit -m "feat: trigger payment success email when invoice is paid"
```

---

## Chunk 5: Billing History

### Task 9: Add billing history API endpoint

**Files:**
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/urls.py`
- Test: `backend/restaurants/tests/test_subscription_api.py`

- [ ] **Step 1: Write test for billing history endpoint**

Add to `backend/restaurants/tests/test_subscription_api.py`:

```python
@pytest.mark.django_db
class TestBillingHistory:
    @patch("stripe.Invoice.list")
    def test_billing_history_returns_invoices(self, mock_invoice_list, api_client):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_hist_test",
            stripe_customer_id="cus_hist_test",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        api_client.force_authenticate(user=restaurant.owner)

        mock_invoice_list.return_value = {
            "data": [
                {
                    "id": "inv_001",
                    "created": 1712000000,
                    "amount_paid": 9900,
                    "currency": "usd",
                    "status": "paid",
                    "lines": {
                        "data": [
                            {
                                "description": "Growth plan",
                                "price": {"metadata": {"plan": "growth"}},
                            }
                        ]
                    },
                    "hosted_invoice_url": "https://invoice.stripe.com/inv_001",
                }
            ]
        }

        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/subscription/invoices/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == "inv_001"
        assert response.data[0]["amount"] == 9900
        assert response.data[0]["status"] == "paid"
        assert response.data[0]["receipt_url"] == "https://invoice.stripe.com/inv_001"

    def test_billing_history_requires_auth(self, api_client):
        restaurant = RestaurantFactory()
        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/subscription/invoices/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_owner_cannot_view_billing_history(self, api_client):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_customer_id="cus_other_test",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )
        other_user = UserFactory()
        api_client.force_authenticate(user=other_user)
        response = api_client.get(
            f"/api/restaurants/{restaurant.slug}/subscription/invoices/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

Add `UserFactory` to the imports at the top of the file:

```python
from restaurants.tests.factories import RestaurantFactory, UserFactory
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_api.py::TestBillingHistory::test_billing_history_returns_invoices -v`

Expected: FAIL — 404 (URL not found)

- [ ] **Step 3: Implement `BillingHistoryView`**

Add to `backend/restaurants/views.py`, after the `ReactivateSubscriptionView` class (after line 236):

```python
class BillingHistoryView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/subscription/invoices/ - List Stripe invoices."""

    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        try:
            subscription = restaurant.subscription
        except Subscription.DoesNotExist:
            return Response([])

        if not subscription.stripe_customer_id:
            return Response([])

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        invoices = stripe.Invoice.list(
            customer=subscription.stripe_customer_id,
            limit=12,
        )

        result = []
        for inv in invoices["data"]:
            # Extract plan name from line items
            plan_name = ""
            lines = inv.get("lines", {}).get("data", [])
            if lines:
                price_meta = lines[0].get("price", {}).get("metadata", {})
                plan_name = price_meta.get("plan", "").title()
                if not plan_name:
                    plan_name = lines[0].get("description", "")

            result.append({
                "id": inv["id"],
                "date": inv["created"],
                "amount": inv["amount_paid"],
                "currency": inv["currency"],
                "status": inv["status"],
                "plan": plan_name,
                "receipt_url": inv.get("hosted_invoice_url", ""),
            })

        return Response(result)
```

- [ ] **Step 4: Add URL pattern**

In `backend/restaurants/urls.py`, add the import for `BillingHistoryView` in the imports from `restaurants.views` and add the URL pattern after the `subscription/reactivate/` path (after line 101):

```python
    path(
        "restaurants/<slug:slug>/subscription/invoices/",
        BillingHistoryView.as_view(),
        name="subscription-invoices",
    ),
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/backend && python -m pytest restaurants/tests/test_subscription_api.py -v`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/views.py backend/restaurants/urls.py backend/restaurants/tests/test_subscription_api.py
git commit -m "feat: add billing history API endpoint fetching Stripe invoices"
```

---

### Task 10: Add frontend billing history hook and types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/use-billing-history.ts`

- [ ] **Step 1: Add `BillingInvoice` type**

Add to `frontend/src/types/index.ts` after the `Subscription` interface (after line 14):

```ts
export interface BillingInvoice {
  id: string;
  date: number;
  amount: number;
  currency: string;
  status: string;
  plan: string;
  receipt_url: string;
}
```

- [ ] **Step 2: Add `fetchBillingHistory` to API client**

Add to `frontend/src/lib/api.ts` near the other subscription-related functions:

```ts
export async function fetchBillingHistory(slug: string): Promise<BillingInvoice[]> {
  return apiFetch<BillingInvoice[]>(`/api/restaurants/${slug}/subscription/invoices/`);
}
```

Add `BillingInvoice` to the imports from `@/types` at the top of the file.

- [ ] **Step 3: Create `use-billing-history.ts` hook**

Create `frontend/src/hooks/use-billing-history.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { fetchBillingHistory } from "@/lib/api";

export function useBillingHistory(slug: string) {
  return useQuery({
    queryKey: ["billing-history", slug],
    queryFn: () => fetchBillingHistory(slug),
    enabled: !!slug,
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts frontend/src/hooks/use-billing-history.ts
git commit -m "feat: add billing history type, API function, and hook"
```

---

### Task 11: Add billing history table to billing page

**Files:**
- Modify: `frontend/src/app/account/restaurants/[slug]/billing/BillingPageClient.tsx`

- [ ] **Step 1: Add billing history section**

In `frontend/src/app/account/restaurants/[slug]/billing/BillingPageClient.tsx`:

Add import at the top:

```tsx
import { useBillingHistory } from "@/hooks/use-billing-history";
```

Inside the `BillingPage` component, add the hook call after the existing hooks (after line 67):

```tsx
  const { data: invoices, isLoading: invoicesLoading } = useBillingHistory(params.slug);
```

Add the billing history section after the plan selection grid's closing `</div>` (after line 282, before the final closing `</div>` tags):

```tsx
        {/* Billing History */}
        <h2 className="text-lg font-semibold mt-8 mb-4">Billing History</h2>
        <Card className="bg-card border border-border rounded-2xl overflow-hidden">
          {invoicesLoading ? (
            <div className="flex justify-center p-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
            </div>
          ) : !invoices || invoices.length === 0 ? (
            <p className="text-sm text-muted-foreground p-6">
              No billing history yet.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left p-4 font-medium text-muted-foreground">Date</th>
                  <th className="text-left p-4 font-medium text-muted-foreground">Amount</th>
                  <th className="text-left p-4 font-medium text-muted-foreground">Plan</th>
                  <th className="text-left p-4 font-medium text-muted-foreground">Status</th>
                  <th className="text-right p-4 font-medium text-muted-foreground">Receipt</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="border-b border-border last:border-0">
                    <td className="p-4">
                      {new Date(invoice.date * 1000).toLocaleDateString()}
                    </td>
                    <td className="p-4">
                      ${(invoice.amount / 100).toFixed(2)}
                    </td>
                    <td className="p-4">{invoice.plan}</td>
                    <td className="p-4">
                      <Badge
                        variant={invoice.status === "paid" ? "default" : "outline"}
                      >
                        {invoice.status}
                      </Badge>
                    </td>
                    <td className="p-4 text-right">
                      {invoice.receipt_url && (
                        <a
                          href={invoice.receipt_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline"
                        >
                          View
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /Users/k.yook/projects/ai-qr-ordering/frontend && npx tsc --noEmit`

Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/restaurants/[slug]/billing/BillingPageClient.tsx
git commit -m "feat: add billing history table to billing page"
```
