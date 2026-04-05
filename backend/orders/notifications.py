import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from orders.models import Order

logger = logging.getLogger(__name__)


def _get_order_email_context(order: Order) -> dict:
    """Build shared template context for order email templates."""
    items = []
    special_requests = []
    for oi in order.items.select_related("menu_item", "variant").all():
        line_total = oi.variant.price * oi.quantity
        items.append({
            "name": oi.menu_item.name,
            "variant_label": oi.variant.label,
            "quantity": oi.quantity,
            "special_requests": oi.special_requests,
            "line_total": f"{line_total:.2f}",
        })
        if oi.special_requests:
            special_requests.append(f"{oi.menu_item.name}: {oi.special_requests}")

    return {
        "order_id": str(order.id),
        "restaurant_name": order.restaurant.name,
        "restaurant_slug": order.restaurant.slug,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "table_identifier": order.table_identifier or "",
        "items": items,
        "subtotal": f"{order.subtotal:.2f}",
        "tax_amount": f"{order.tax_amount:.2f}",
        "total_price": f"{order.total_price:.2f}",
        "estimated_wait": order.restaurant.estimated_minutes_per_order,
        "special_requests": special_requests,
        "frontend_url": settings.FRONTEND_URL,
    }


def send_order_confirmation_email(order: Order) -> None:
    """Send order confirmation email to the customer."""
    recipient = _resolve_customer_email(order)
    if not recipient:
        logger.info("No customer email for order %s, skipping confirmation email", order.id)
        return

    context = _get_order_email_context(order)
    html_message = render_to_string("emails/order_confirmation.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"Order confirmed — {order.restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send order confirmation email for order %s", order.id)


def send_new_order_alert_email(order: Order) -> None:
    """Send new order alert email to the restaurant owner."""
    recipient = order.restaurant.owner.email
    if not recipient:
        logger.info("No owner email for restaurant %s, skipping alert", order.restaurant.slug)
        return

    context = _get_order_email_context(order)
    html_message = render_to_string("emails/new_order_alert.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"New order received — {order.restaurant.name}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send new order alert for order %s", order.id)


def _resolve_customer_email(order: Order) -> str:
    """Resolve customer email: prefer order field, fall back to user account."""
    if order.customer_email:
        return order.customer_email
    if order.user and order.user.email:
        return order.user.email
    return ""
