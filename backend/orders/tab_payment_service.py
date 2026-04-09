from decimal import ROUND_HALF_UP, Decimal

import stripe
from django.conf import settings
from django.utils import timezone

from orders.models import Tab, TabPayment
from orders.tab_service import TabService


class TabPaymentService:
    @staticmethod
    def create_payment(tab, payment_type, split_count=None, item_ids=None, user=None):
        if tab.status != "closing":
            raise ValueError("Tab must be in 'closing' status to accept payments")

        amount = TabPaymentService._calculate_amount(tab, payment_type, split_count, item_ids)
        tax_portion = TabPaymentService._calculate_tax_portion(tab, amount)

        payment = TabPayment.objects.create(
            tab=tab,
            type=payment_type,
            amount=amount,
            tax_amount=tax_portion,
            split_count=split_count,
        )

        if item_ids:
            from orders.models import OrderItem
            payment.items.set(OrderItem.objects.filter(id__in=item_ids))

        stripe.api_key = settings.STRIPE_SECRET_KEY
        restaurant = tab.restaurant

        intent_params = {
            "amount": int(amount * 100),
            "currency": restaurant.currency.lower(),
            "automatic_payment_methods": {"enabled": True},
            "metadata": {
                "tab_id": str(tab.id),
                "tab_payment_id": str(payment.id),
                "restaurant_id": str(restaurant.id),
            },
        }

        from restaurants.models import ConnectedAccount
        try:
            connected = ConnectedAccount.objects.get(restaurant=restaurant, onboarding_complete=True)
            intent_params["transfer_data"] = {"destination": connected.stripe_account_id}
        except ConnectedAccount.DoesNotExist:
            pass

        intent = stripe.PaymentIntent.create(**intent_params)
        payment.stripe_payment_intent_id = intent.id
        payment.save(update_fields=["stripe_payment_intent_id"])

        return payment, intent.client_secret

    @staticmethod
    def confirm_payment(payment):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)

        if intent.status == "succeeded":
            payment.payment_status = "paid"
            payment.paid_at = timezone.now()
            payment.save(update_fields=["payment_status", "paid_at"])

            tab = payment.tab
            if tab.amount_remaining <= 0:
                TabService.finalize_tab(tab)
            return True

        if intent.status in ("canceled", "requires_payment_method"):
            payment.payment_status = "failed"
            payment.save(update_fields=["payment_status"])

        return False

    @staticmethod
    def _calculate_amount(tab, payment_type, split_count=None, item_ids=None):
        remaining = tab.amount_remaining

        if payment_type == "full":
            return remaining
        elif payment_type == "split_even":
            existing_paid = (
                tab.payments
                .filter(type="split_even", split_count=split_count)
                .exclude(payment_status="failed")
                .count()
            )
            is_last = (existing_paid + 1) == split_count
            if is_last:
                return remaining
            per_person = (tab.total / split_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return per_person
        elif payment_type == "pay_by_item":
            from orders.models import OrderItem
            items = OrderItem.objects.filter(id__in=item_ids)
            item_total = sum(
                (i.variant.price + sum(m.price_adjustment for m in i.modifiers.all())) * i.quantity
                for i in items
            )
            if tab.subtotal > 0:
                tax_ratio = tab.tax_amount / tab.subtotal
                tax = (item_total * tax_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                return item_total + tax
            return item_total

        raise ValueError(f"Unknown payment type: {payment_type}")

    @staticmethod
    def _calculate_tax_portion(tab, amount):
        if tab.total > 0:
            ratio = tab.tax_amount / tab.total
            return (amount * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")
