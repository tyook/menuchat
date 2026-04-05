import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_welcome_email_task(user_id: str):
    """Send welcome email to a newly registered user (async)."""
    from accounts.models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning("send_welcome_email_task: user %s not found", user_id)
        return

    from accounts.notifications import send_welcome_email
    send_welcome_email(user)
