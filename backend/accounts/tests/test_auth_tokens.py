import pytest
from django.test import TestCase
from rest_framework.test import APIClient


class TokenInResponseTest(TestCase):
    def setUp(self):
        from accounts.models import User
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )

    def test_login_returns_tokens_in_body(self):
        response = self.client.post("/api/auth/login/", {
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert response.status_code == 200
        assert "access_token" in response.data
        assert "refresh_token" in response.data
        assert isinstance(response.data["access_token"], str)
        assert isinstance(response.data["refresh_token"], str)

    def test_register_returns_tokens_in_body(self):
        response = self.client.post("/api/auth/register/", {
            "email": "new@example.com",
            "password": "newpass123",
            "first_name": "Test",
            "last_name": "User",
        })
        assert response.status_code == 201
        assert "access_token" in response.data
        assert "refresh_token" in response.data

    def test_refresh_returns_new_access_token(self):
        login = self.client.post("/api/auth/login/", {
            "email": "test@example.com",
            "password": "testpass123",
        })
        refresh_token = login.data["refresh_token"]
        response = self.client.post("/api/auth/refresh/", {
            "refresh_token": refresh_token,
        })
        assert response.status_code == 200
        assert "access_token" in response.data
