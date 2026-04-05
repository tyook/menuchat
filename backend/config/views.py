import logging

from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """GET /api/health/ - Unauthenticated service health check."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = self._check_db()
        redis_ok = self._check_redis()

        payload = {"status": "ok", "db": db_ok, "redis": redis_ok}

        if not db_ok or not redis_ok:
            payload["status"] = "degraded"
            return Response(payload, status=503)

        return Response(payload)

    @staticmethod
    def _check_db():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            logger.exception("Health check: DB unreachable")
            return False

    @staticmethod
    def _check_redis():
        try:
            import redis
            from django.conf import settings

            url = settings.CELERY_BROKER_URL
            r = redis.Redis.from_url(url)
            r.ping()
            return True
        except Exception:
            logger.exception("Health check: Redis unreachable")
            return False
