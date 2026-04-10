import logging

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

from .models import DeviceToken

logger = logging.getLogger(__name__)

# Initialize Firebase app once
if not firebase_admin._apps:
    if settings.FIREBASE_CREDENTIALS:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
    else:
        logger.warning("FIREBASE_CREDENTIALS not set — push notifications disabled")


def send_push_notification(
    user=None,
    order=None,
    title: str = "",
    body: str = "",
    data: dict | None = None,
) -> int:
    """Send push notification to all active devices for a user or order.

    Returns the number of successfully sent notifications.
    """
    if not firebase_admin._apps:
        logger.warning("Firebase not initialized, skipping push")
        return 0

    tokens = DeviceToken.objects.filter(is_active=True)
    if user:
        tokens = tokens.filter(user=user)
    elif order:
        tokens = tokens.filter(order=order)
    else:
        return 0

    sent = 0
    for device_token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=device_token.token,
        )
        try:
            messaging.send(message)
            sent += 1
        except messaging.UnregisteredError:
            logger.info(f"Deactivating unregistered token: {device_token.token[:8]}...")
            device_token.is_active = False
            device_token.save(update_fields=["is_active", "updated_at"])
        except Exception:
            logger.exception(f"Failed to send push to {device_token.token[:8]}...")

    return sent
