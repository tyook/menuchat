import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_welcome_email(user) -> None:
    """Send welcome email to a newly registered user."""
    if not user.email:
        return

    context = {
        "user_name": user.first_name or user.name or "",
        "is_restaurant_owner": user.is_restaurant_owner,
        "frontend_url": settings.FRONTEND_URL,
    }
    html_message = render_to_string("emails/welcome.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject="Welcome to MenuChat!",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send welcome email to %s", user.email)
