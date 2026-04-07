"""Toast POS health monitoring and alerting.

Provides a periodic Celery task that checks Toast API error rates
and logs alerts when thresholds are breached.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Alert if error rate exceeds 5% over the check window.
ERROR_RATE_THRESHOLD = 0.05
CHECK_WINDOW_MINUTES = 5


@shared_task
def check_toast_health() -> None:
    """Check Toast POS sync error rate and alert if above threshold.

    Runs every 5 minutes via Celery Beat. Examines POSSyncLog entries
    for Toast connections within the check window.
    """
    if not getattr(settings, "TOAST_POS_ENABLED", False):
        return

    from integrations.models import POSConnection, POSSyncLog

    toast_connections = POSConnection.objects.filter(
        pos_type=POSConnection.POSType.TOAST,
        is_active=True,
    ).values_list("id", flat=True)

    if not toast_connections:
        return

    since = timezone.now() - timedelta(minutes=CHECK_WINDOW_MINUTES)
    logs = POSSyncLog.objects.filter(
        pos_connection_id__in=toast_connections,
        created_at__gte=since,
    )

    total = logs.count()
    if total == 0:
        logger.info(
            "Toast health check: no recent sync attempts",
            extra={"event": "toast_health_ok", "pos_type": "toast"},
        )
        return

    errors = logs.filter(
        status__in=[POSSyncLog.Status.FAILED, POSSyncLog.Status.RETRYING],
    ).count()
    error_rate = errors / total

    extra = {
        "event": "toast_health_check",
        "pos_type": "toast",
        "total_syncs": total,
        "error_count": errors,
        "error_rate": round(error_rate, 4),
        "window_minutes": CHECK_WINDOW_MINUTES,
    }

    if error_rate > ERROR_RATE_THRESHOLD:
        logger.critical(
            "ALERT: Toast POS error rate %.1f%% exceeds %.1f%% threshold",
            error_rate * 100,
            ERROR_RATE_THRESHOLD * 100,
            extra={**extra, "event": "toast_health_alert"},
        )
    else:
        logger.info("Toast health check: OK", extra=extra)
