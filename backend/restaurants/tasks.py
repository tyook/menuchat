import logging

from celery import shared_task
from config.celery import app

from restaurants.services.payout_service import PayoutService

logger = logging.getLogger(__name__)


@app.task(name="restaurants.tasks.process_daily_payouts")
def process_daily_payouts():
    logger.info("Starting daily payout processing")
    PayoutService.process_all_payouts()
    logger.info("Daily payout processing complete")


@shared_task
def send_merchant_welcome_email_task(restaurant_id: str):
    """Send merchant welcome email after restaurant creation (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_merchant_welcome_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_merchant_welcome_email
    send_merchant_welcome_email(restaurant)


@shared_task
def send_subscription_activated_email_task(restaurant_id: str, plan: str):
    """Send subscription activated email after checkout completes (async)."""
    from restaurants.models import Restaurant

    try:
        restaurant = Restaurant.objects.select_related("owner").get(id=restaurant_id)
    except Restaurant.DoesNotExist:
        logger.warning("send_subscription_activated_email_task: restaurant %s not found", restaurant_id)
        return

    from restaurants.notifications import send_subscription_activated_email
    send_subscription_activated_email(restaurant, plan)
