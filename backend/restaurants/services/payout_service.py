import logging
from datetime import timedelta
from decimal import Decimal

import redis
import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from orders.models import Order
from restaurants.models import ConnectedAccount, Payout

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)
redis_client = redis.from_url(settings.CELERY_BROKER_URL)


class PayoutService:
    @staticmethod
    def process_restaurant_payout(restaurant):
        try:
            account = restaurant.connected_account
        except ConnectedAccount.DoesNotExist:
            return

        if not account.payouts_enabled:
            return

        lock_key = f"payout-lock-{restaurant.id}"
        lock = redis_client.lock(lock_key, timeout=300)
        if not lock.acquire(blocking=False):
            logger.warning(f"Payout lock already held for restaurant {restaurant.id}, skipping")
            return

        try:
            PayoutService._process_payout(restaurant, account)
        finally:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    @staticmethod
    def _process_payout(restaurant, account):
        settlement_days = settings.PAYOUT_CONFIG["settlement_days"]
        cutoff = timezone.now() - timedelta(days=settlement_days)

        eligible_orders = Order.objects.filter(
            restaurant=restaurant,
            payment_status="paid",
            payout_status="pending",
            paid_at__lte=cutoff,
        )

        total = eligible_orders.aggregate(total=Sum("total_price"))["total"]
        if not total or total <= 0:
            return

        refund_deduction = min(account.pending_refund_balance, total)
        transfer_amount = total - refund_deduction

        if transfer_amount <= 0:
            account.pending_refund_balance -= total
            account.save(update_fields=["pending_refund_balance"])
            return

        transfer_amount_cents = int(transfer_amount * 100)
        today = timezone.now().date().isoformat()
        order_ids = list(eligible_orders.values_list("id", flat=True))

        payout = None
        try:
            with transaction.atomic():
                payout = Payout.objects.create(
                    restaurant=restaurant,
                    stripe_transfer_id="pending",
                    amount=transfer_amount,
                    currency=restaurant.currency.lower(),
                    orders_count=len(order_ids),
                    period_start=eligible_orders.order_by("paid_at").first().paid_at.date(),
                    period_end=eligible_orders.order_by("-paid_at").first().paid_at.date(),
                    fee_amount=Decimal("0"),
                )

                transfer = stripe.Transfer.create(
                    amount=transfer_amount_cents,
                    currency=restaurant.currency.lower(),
                    destination=account.stripe_account_id,
                    idempotency_key=f"payout-{restaurant.id}-{today}",
                    metadata={
                        "restaurant_id": str(restaurant.id),
                        "payout_id": str(payout.id),
                    },
                )

                payout.stripe_transfer_id = transfer.id
                payout.save(update_fields=["stripe_transfer_id"])

                eligible_orders.update(
                    payout_status="transferred",
                    payout=payout,
                )

                if refund_deduction > 0:
                    account.pending_refund_balance -= refund_deduction
                    account.save(update_fields=["pending_refund_balance"])

        except stripe.error.StripeError as e:
            logger.error(
                f"Payout failed for restaurant {restaurant.id}: {e}",
                exc_info=True,
            )
            if payout and payout.pk:
                payout.status = "failed"
                payout.save(update_fields=["status"])

    @staticmethod
    def process_all_payouts():
        accounts = ConnectedAccount.objects.filter(
            payouts_enabled=True
        ).select_related("restaurant")

        for account in accounts:
            try:
                PayoutService.process_restaurant_payout(account.restaurant)
            except Exception as e:
                logger.error(
                    f"Unexpected error processing payout for restaurant {account.restaurant.id}: {e}",
                    exc_info=True,
                )
