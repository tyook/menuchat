from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from orders.serializers import OrderResponseSerializer


def broadcast_order_to_kitchen(order):
    """Send order data to the kitchen WebSocket group."""
    channel_layer = get_channel_layer()
    data = OrderResponseSerializer(order).data
    # Convert UUIDs and Decimals to strings for JSON
    data["id"] = str(data["id"])
    data["total_price"] = str(data["total_price"])

    async_to_sync(channel_layer.group_send)(
        f"kitchen_{order.restaurant.slug}",
        {
            "type": "order_update",
            "data": data,
        },
    )

    # Push notification to restaurant owner
    from notifications.services import send_push_notification
    send_push_notification(
        user=order.restaurant.owner,
        title="New Order",
        body=f"New order #{str(order.id)[:8]} received",
        data={"type": "new_order", "order_id": str(order.id)},
    )


def broadcast_order_to_customer(order):
    """Send queue update to the customer's WebSocket group."""
    from orders.queue_service import QueueService

    channel_layer = get_channel_layer()
    queue_info = QueueService.get_order_queue_info(order)

    async_to_sync(channel_layer.group_send)(
        f"customer_{order.id}",
        {
            "type": "queue_update",
            "data": queue_info,
        },
    )

    # Push notification when order is ready
    from notifications.services import send_push_notification
    if order.status == "ready":
        send_push_notification(
            user=order.user if order.user else None,
            order=order if not order.user else None,
            title="Order Ready!",
            body=f"Your order from {order.restaurant.name} is ready for pickup",
            data={"type": "order_ready", "order_id": str(order.id)},
        )
