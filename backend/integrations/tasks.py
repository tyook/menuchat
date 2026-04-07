import logging

from celery import shared_task
from django.conf import settings

from integrations.services import POSDispatchError, POSDispatchService

logger = logging.getLogger(__name__)

RETRY_DELAYS = getattr(settings, "POS_DISPATCH_RETRY_DELAYS", [30, 120, 600, 1800])
MENU_SYNC_INTERVAL = getattr(settings, "TOAST_MENU_SYNC_INTERVAL_SECONDS", 3600)  # 1 hour


@shared_task(
    bind=True,
    max_retries=len(RETRY_DELAYS),  # 4 retries = 5 total attempts (initial + 4 retries)
    acks_late=True,
)
def dispatch_order_to_pos(self, order_id: str) -> None:
    """Dispatch order to POS with idempotency check and exponential backoff."""
    # Idempotency: skip if already synced (prevents double dispatch from
    # ConfirmPaymentView + webhook both firing for the same order)
    from orders.models import Order
    if Order.objects.filter(id=order_id, pos_sync_status="synced").exists():
        return

    try:
        POSDispatchService.dispatch(order_id)
    except POSDispatchError as exc:
        retry_num = self.request.retries
        if retry_num < len(RETRY_DELAYS):
            countdown = RETRY_DELAYS[retry_num]
            logger.warning(
                "POS dispatch failed, retrying in %ds: order=%s error=%s",
                countdown,
                order_id,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.error("POS dispatch failed after all retries: order=%s", order_id)
            POSDispatchService.mark_failed(order_id)
    except Exception:
        logger.exception("Unexpected error in POS dispatch: order=%s", order_id)
        POSDispatchService.mark_failed(order_id)


@shared_task
def sync_toast_menu(restaurant_id: str) -> dict:
    """Sync menu from Toast POS for a specific restaurant."""
    if not getattr(settings, "TOAST_POS_ENABLED", False):
        return {"skipped": True, "reason": "TOAST_POS_ENABLED is False"}

    from integrations.services import MenuSyncService

    try:
        result = MenuSyncService.sync_from_toast(restaurant_id)
        return result
    except Exception:
        logger.exception("Toast menu sync failed: restaurant=%s", restaurant_id)
        return {"error": True, "restaurant_id": restaurant_id}


@shared_task
def sync_all_toast_menus() -> dict:
    """Sync menus for all restaurants with active Toast connections.

    Intended to run on a schedule (e.g. hourly via Celery Beat).
    """
    if not getattr(settings, "TOAST_POS_ENABLED", False):
        return {"skipped": True, "reason": "TOAST_POS_ENABLED is False"}

    from integrations.models import POSConnection

    connections = POSConnection.objects.filter(
        pos_type=POSConnection.POSType.TOAST, is_active=True
    ).values_list("restaurant_id", flat=True)

    dispatched = 0
    for restaurant_id in connections:
        sync_toast_menu.delay(str(restaurant_id))
        dispatched += 1

    return {"dispatched": dispatched}


@shared_task
def poll_toast_order_status(order_id: str) -> dict:
    """Poll Toast for updated order status."""
    if not getattr(settings, "TOAST_POS_ENABLED", False):
        return {"skipped": True}

    from integrations.services import OrderStatusService

    new_status = OrderStatusService.poll_order_status(order_id)
    if new_status:
        # Broadcast the status change to the customer
        from orders.broadcast import broadcast_order_to_customer
        from orders.models import Order

        order = Order.objects.get(id=order_id)
        broadcast_order_to_customer(order)

        return {"order_id": order_id, "new_status": new_status}

    return {"order_id": order_id, "unchanged": True}


@shared_task
def poll_all_toast_order_statuses() -> dict:
    """Poll status for all Toast-synced orders that are not yet completed.

    Intended to run on a schedule (e.g. every 2 minutes via Celery Beat).
    """
    if not getattr(settings, "TOAST_POS_ENABLED", False):
        return {"skipped": True}

    from orders.models import Order

    active_statuses = ["confirmed", "preparing", "ready"]
    orders = Order.objects.filter(
        pos_sync_status="synced",
        external_order_id__isnull=False,
        status__in=active_statuses,
    ).values_list("id", flat=True)

    dispatched = 0
    for order_id in orders:
        poll_toast_order_status.delay(str(order_id))
        dispatched += 1

    return {"dispatched": dispatched}
