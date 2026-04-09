from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def broadcast_tab_update(tab, event_type, extra_data=None):
    """Broadcast a tab event to the table's WebSocket channel."""
    channel_layer = get_channel_layer()
    group_name = f"tab_{tab.id}"
    data = {
        "type": event_type,
        "tab_id": str(tab.id),
        "table_identifier": tab.table_identifier,
        "total": str(tab.total),
        "amount_paid": str(tab.amount_paid),
        "amount_remaining": str(tab.amount_remaining),
        "status": tab.status,
    }
    if extra_data:
        data.update(extra_data)
    async_to_sync(channel_layer.group_send)(
        group_name,
        {"type": "tab_update", "data": data},
    )
