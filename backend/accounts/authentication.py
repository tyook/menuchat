from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


class CookieJWTAuthentication(JWTAuthentication):
    """Read JWT from httpOnly cookie, fall back to Authorization header."""

    def authenticate(self, request):
        # Try cookie first
        raw_token = request.COOKIES.get("access_token")
        if raw_token:
            try:
                validated_token = AccessToken(raw_token)
                user = self.get_user(validated_token)
                return (user, validated_token)
            except (InvalidToken, TokenError):
                return None

        # Fall back to Authorization header
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except (InvalidToken, TokenError):
            return None
