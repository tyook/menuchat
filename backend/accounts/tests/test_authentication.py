import pytest
from django.test import RequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.authentication import CookieJWTAuthentication
from accounts.tests.factories import UserFactory


@pytest.fixture
def auth():
    return CookieJWTAuthentication()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.mark.django_db
class TestCookieJWTAuthentication:
    def test_authenticates_from_cookie(self, auth, rf):
        user = UserFactory()
        token = RefreshToken.for_user(user)
        request = rf.get("/")
        request.COOKIES["access_token"] = str(token.access_token)
        result_user, _ = auth.authenticate(request)
        assert result_user.id == user.id

    def test_falls_back_to_authorization_header(self, auth, rf):
        user = UserFactory()
        token = RefreshToken.for_user(user)
        request = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        result_user, _ = auth.authenticate(request)
        assert result_user.id == user.id

    def test_returns_none_when_no_token(self, auth, rf):
        request = rf.get("/")
        result = auth.authenticate(request)
        assert result is None

    def test_returns_none_for_invalid_cookie(self, auth, rf):
        request = rf.get("/")
        request.COOKIES["access_token"] = "invalid-token"
        result = auth.authenticate(request)
        assert result is None
