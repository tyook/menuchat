"""JWT authentication middleware for Django Channels WebSocket connections.

Reads the token from:
1. Query string (?token=<jwt>)
2. The ``access_token`` httpOnly cookie (sent automatically by the browser)
"""

from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_str: str):
    try:
        validated = AccessToken(token_str)
        return User.objects.get(id=validated["user_id"])
    except Exception:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """Populate scope["user"] from a JWT access token."""

    async def __call__(self, scope, receive, send):
        token = None

        # 1. Try query string
        qs = parse_qs(scope.get("query_string", b"").decode())
        token_list = qs.get("token", [])
        if token_list and token_list[0]:
            token = token_list[0]

        # 2. Fall back to httpOnly cookie
        if not token:
            headers = dict(scope.get("headers", []))
            cookie_header = headers.get(b"cookie", b"").decode()
            if cookie_header:
                cookie = SimpleCookie(cookie_header)
                if "access_token" in cookie:
                    token = cookie["access_token"].value

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)
