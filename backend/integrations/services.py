import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from integrations.adapters.base import BasePOSAdapter
from integrations.adapters.noop import NoopAdapter
from integrations.adapters.square import SquareAdapter
from integrations.adapters.toast import ToastAdapter, ToastAPIError
from integrations.models import POSConnection, POSSyncLog
from orders.models import Order

logger = logging.getLogger(__name__)


class POSDispatchError(Exception):
    pass


class POSDispatchService:
    @staticmethod
    def dispatch(order_id: str) -> None:
        order = Order.objects.select_related("restaurant").get(id=order_id)

        try:
            connection = POSConnection.objects.get(restaurant=order.restaurant, is_active=True)
        except POSConnection.DoesNotExist:
            connection = None

        if not connection or connection.pos_type == POSConnection.POSType.NONE:
            Order.objects.filter(id=order.id).update(pos_sync_status="not_applicable")
            return

        # Feature flag: skip Toast dispatch if disabled
        if (
            connection.pos_type == POSConnection.POSType.TOAST
            and not getattr(settings, "TOAST_POS_ENABLED", False)
        ):
            Order.objects.filter(id=order.id).update(pos_sync_status="not_applicable")
            return

        log = POSSyncLog.objects.create(
            order=order,
            pos_connection=connection,
            status=POSSyncLog.Status.PENDING,
        )

        adapter = POSDispatchService._get_adapter(connection)
        result = adapter.push_order(order)

        if result.success:
            log.status = POSSyncLog.Status.SUCCESS
            log.external_order_id = result.external_order_id
            log.attempt_count += 1
            log.save()

            Order.objects.filter(id=order.id).update(
                pos_sync_status="synced",
                external_order_id=result.external_order_id,
            )
        else:
            log.status = POSSyncLog.Status.RETRYING
            log.last_error = result.error_message
            log.attempt_count += 1
            log.save()

            Order.objects.filter(id=order.id).update(
                pos_sync_status="retrying",
            )
            raise POSDispatchError(f"POS dispatch failed: {result.error_message}")

    @staticmethod
    def _get_adapter(connection: POSConnection) -> BasePOSAdapter:
        adapter_map = {
            POSConnection.POSType.NONE: NoopAdapter,
            POSConnection.POSType.SQUARE: SquareAdapter,
            POSConnection.POSType.TOAST: ToastAdapter,
        }
        adapter_class = adapter_map.get(connection.pos_type, NoopAdapter)
        return adapter_class(connection)

    @staticmethod
    def mark_failed(order_id: str) -> None:
        """Called after all retries are exhausted."""
        Order.objects.filter(id=order_id).update(pos_sync_status="failed")
        POSSyncLog.objects.filter(order_id=order_id, status=POSSyncLog.Status.RETRYING).update(
            status=POSSyncLog.Status.FAILED
        )


class ToastErrorTranslator:
    """Translates Toast API error messages to user-friendly strings."""

    _PATTERNS = {
        "restaurant is closed": "The restaurant is currently closed. Please try again during business hours.",
        "item is unavailable": "One or more items in your order are currently unavailable.",
        "out of stock": "One or more items in your order are out of stock.",
        "invalid order": "There was a problem with your order. Please try again.",
    }
    _DEFAULT = "We couldn't process your order with the restaurant right now. Please try again shortly."

    @staticmethod
    def translate(error_message: str) -> str:
        """Return a user-friendly message for a Toast error."""
        lower = (error_message or "").lower()
        for pattern, friendly in ToastErrorTranslator._PATTERNS.items():
            if pattern in lower:
                return friendly
        return ToastErrorTranslator._DEFAULT

    @staticmethod
    def get_user_friendly_error(order_id: str) -> str | None:
        """Look up the latest sync error for an order and translate it."""
        log = (
            POSSyncLog.objects.filter(order_id=order_id)
            .exclude(last_error__isnull=True)
            .exclude(last_error="")
            .order_by("-created_at")
            .first()
        )
        if log and log.last_error:
            return ToastErrorTranslator.translate(log.last_error)
        return None


class MenuSyncService:
    """Syncs menu data from Toast POS into local MenuVersion/MenuItem models."""

    @staticmethod
    @transaction.atomic
    def sync_from_toast(restaurant_id: str) -> dict:
        """Fetch menu from Toast and create/replace a synced MenuVersion.

        Returns a dict with sync results: {synced_items: int, version_id: int}.
        Raises if TOAST_POS_ENABLED is False or no active Toast connection exists.
        """
        from restaurants.models import (
            MenuCategory,
            MenuItem,
            MenuItemVariant,
            MenuVersion,
            Restaurant,
        )

        if not getattr(settings, "TOAST_POS_ENABLED", False):
            raise ValueError("Toast POS integration is disabled.")

        restaurant = Restaurant.objects.get(id=restaurant_id)

        try:
            connection = POSConnection.objects.get(
                restaurant=restaurant,
                pos_type=POSConnection.POSType.TOAST,
                is_active=True,
            )
        except POSConnection.DoesNotExist:
            raise ValueError("No active Toast POS connection for this restaurant.")

        adapter = ToastAdapter(connection)
        toast_groups = adapter.get_menu_items()

        if not toast_groups:
            logger.info(
                "Toast menu sync returned no items",
                extra={
                    "event": "toast_menu_sync_empty",
                    "restaurant_id": str(restaurant_id),
                },
            )
            return {"synced_items": 0, "version_id": None}

        # Deactivate previous Toast-synced versions
        MenuVersion.objects.filter(
            restaurant=restaurant, source="toast_sync"
        ).update(is_active=False)

        version = MenuVersion.objects.create(
            restaurant=restaurant,
            name=f"Toast Sync - {timezone.now().strftime('%b %-d, %Y %H:%M')}",
            source="toast_sync",
            is_active=True,
        )

        # Deactivate all other versions so this one is the active menu
        MenuVersion.objects.filter(restaurant=restaurant).exclude(
            id=version.id
        ).update(is_active=False)

        total_items = 0
        for group_idx, group in enumerate(toast_groups):
            category = MenuCategory.objects.create(
                version=version,
                name=group["group_name"],
                sort_order=group_idx,
            )

            for item_idx, toast_item in enumerate(group["items"]):
                item = MenuItem.objects.create(
                    category=category,
                    name=toast_item["name"],
                    description=toast_item.get("description", ""),
                    is_active=True,
                    sort_order=item_idx,
                )
                MenuItemVariant.objects.create(
                    menu_item=item,
                    label="Regular",
                    price=Decimal(str(toast_item.get("price", 0))),
                    is_default=True,
                )
                total_items += 1

        logger.info(
            "Toast menu sync completed",
            extra={
                "event": "toast_menu_sync_success",
                "restaurant_id": str(restaurant_id),
                "synced_items": total_items,
                "version_id": version.id,
            },
        )

        return {"synced_items": total_items, "version_id": version.id}


class OrderStatusService:
    """Polls Toast POS for order status updates."""

    # Map Toast order statuses to internal MenuChat statuses
    TOAST_STATUS_MAP = {
        "OPEN": "confirmed",
        "IN_PROGRESS": "preparing",
        "READY": "ready",
        "COMPLETED": "completed",
        "CANCELLED": "completed",  # Treat cancellation as terminal
    }

    @staticmethod
    def poll_order_status(order_id: str) -> str | None:
        """Check Toast for updated order status.

        Returns the new status string if changed, None if unchanged or error.
        """
        if not getattr(settings, "TOAST_POS_ENABLED", False):
            return None

        order = Order.objects.select_related("restaurant").get(id=order_id)

        if not order.external_order_id or order.pos_sync_status != "synced":
            return None

        try:
            connection = POSConnection.objects.get(
                restaurant=order.restaurant,
                pos_type=POSConnection.POSType.TOAST,
                is_active=True,
            )
        except POSConnection.DoesNotExist:
            return None

        adapter = ToastAdapter(connection)
        toast_status = adapter.get_order_status(order.external_order_id)

        new_status = OrderStatusService.TOAST_STATUS_MAP.get(toast_status)
        if not new_status or new_status == order.status:
            return None

        # Only allow forward transitions
        status_order = ["confirmed", "preparing", "ready", "completed"]
        try:
            current_idx = status_order.index(order.status)
            new_idx = status_order.index(new_status)
        except ValueError:
            return None

        if new_idx <= current_idx:
            return None

        Order.objects.filter(id=order.id).update(status=new_status)

        logger.info(
            "Order status updated from Toast",
            extra={
                "event": "toast_order_status_update",
                "order_id": str(order_id),
                "old_status": order.status,
                "new_status": new_status,
                "toast_status": toast_status,
            },
        )

        return new_status
