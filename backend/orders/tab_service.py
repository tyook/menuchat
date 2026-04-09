from django.db import transaction
from django.utils import timezone
from integrations.models import POSConnection
from orders.models import Tab, TabPayment


class TabService:
    @staticmethod
    def get_payment_config(restaurant):
        """Resolve both payment_mode and payment_model for a restaurant."""
        try:
            pos = POSConnection.objects.get(restaurant=restaurant, is_active=True)
            payment_mode = pos.payment_mode
        except POSConnection.DoesNotExist:
            payment_mode = "stripe"
        return {"payment_mode": payment_mode, "payment_model": restaurant.payment_model}

    @staticmethod
    def get_or_create_tab(restaurant, table_identifier):
        """Get the open tab for a table, or create one. Raises ValueError if tab is closing."""
        with transaction.atomic():
            existing = (
                Tab.objects.select_for_update()
                .filter(restaurant=restaurant, table_identifier=table_identifier, status__in=["open", "closing"])
                .first()
            )
            if existing:
                if existing.status == "closing":
                    raise ValueError("Tab is closing — no new orders allowed")
                return existing
            return Tab.objects.create(restaurant=restaurant, table_identifier=table_identifier)

    @staticmethod
    def get_open_tab(restaurant, table_identifier):
        """Get the open or closing tab for a table, or None."""
        return Tab.objects.filter(
            restaurant=restaurant, table_identifier=table_identifier, status__in=["open", "closing"]
        ).first()

    @staticmethod
    def close_tab(tab):
        """Initiate closing a tab."""
        if tab.status == "open":
            tab.status = "closing"
            tab.save(update_fields=["status"])

    @staticmethod
    def finalize_tab(tab):
        """Close a tab after all payments are collected."""
        tab.status = "closed"
        tab.closed_at = timezone.now()
        tab.save(update_fields=["status", "closed_at"])
        tab.orders.filter(payment_status="deferred").update(payment_status="paid", paid_at=timezone.now())

    @staticmethod
    def force_close_unpaid(tab):
        """Staff force-closes a tab without payment."""
        tab.status = "closed"
        tab.closed_at = timezone.now()
        tab.save(update_fields=["status", "closed_at"])
