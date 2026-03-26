import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core import mail
from restaurants.models import Restaurant
from restaurants.notifications import send_payout_completed_email, send_payout_failed_email

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.mark.django_db
class TestPayoutNotifications:
    def test_send_payout_completed_email(self, restaurant):
        send_payout_completed_email(restaurant, Decimal("150.00"))
        assert len(mail.outbox) == 1
        assert "150.00" in mail.outbox[0].body
        assert mail.outbox[0].to == ["owner@test.com"]

    def test_send_payout_failed_email(self, restaurant):
        send_payout_failed_email(restaurant, Decimal("150.00"))
        assert len(mail.outbox) == 1
        assert "failed" in mail.outbox[0].subject.lower()
