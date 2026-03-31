"""
Custom DRF exception handler that ensures all errors return JSON responses.

Django's default 500 handler returns HTML, which is unhelpful for API clients.
This handler catches unhandled exceptions and returns a structured JSON error.
"""

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """
    Wrap the default DRF handler and catch any unhandled exceptions
    so that API consumers always receive a JSON body with an error code.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        # DRF already handled it (4xx, known exceptions).
        # Normalise shape: always include "code".
        if isinstance(response.data, dict) and "code" not in response.data:
            response.data["code"] = _status_to_code(response.status_code)
        return response

    # Unhandled exception — would have been a bare HTML 500.
    logger.exception("Unhandled API exception in %s", context.get("view"))

    return Response(
        {
            "code": "server_error",
            "detail": "An internal error occurred. Please try again later.",
        },
        status=500,
    )


def _status_to_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        429: "throttled",
    }.get(status_code, f"error_{status_code}")
