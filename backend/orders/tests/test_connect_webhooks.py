from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from restaurants.models import ConnectedAccount, Payout, Restaurant

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Test Restaurant", slug="test-restaurant", owner=owner)


@pytest.fixture
def connected_account(restaurant):
    return ConnectedAccount.objects.create(
        restaurant=restaurant,
        stripe_account_id="acct_test123",
        onboarding_complete=False,
        payouts_enabled=False,
        charges_enabled=False,
    )


@pytest.mark.django_db
class TestAccountUpdatedWebhook:
    def test_updates_connected_account(self, connected_account):
        from orders.services import OrderService

        event_data = {
            "type": "account.updated",
            "account": "acct_test123",
            "data": {
                "object": {
                    "id": "acct_test123",
                    "payouts_enabled": True,
                    "charges_enabled": True,
                    "details_submitted": True,
                }
            },
        }

        OrderService._handle_account_updated(event_data["data"])

        connected_account.refresh_from_db()
        assert connected_account.payouts_enabled is True
        assert connected_account.charges_enabled is True
        assert connected_account.onboarding_complete is True


@pytest.fixture
def payout(restaurant):
    return Payout.objects.create(
        restaurant=restaurant,
        stripe_transfer_id="tr_test123",
        amount=Decimal("50.00"),
        currency="usd",
        status="pending",
        orders_count=3,
        period_start="2026-03-25",
        period_end="2026-03-25",
    )


@pytest.mark.django_db
class TestTransferCreatedWebhook:
    def test_sets_payout_in_transit(self, payout):
        from orders.services import OrderService

        OrderService._handle_transfer_created(
            {"object": {"id": "tr_test123"}}
        )
        payout.refresh_from_db()
        assert payout.status == "in_transit"


@pytest.mark.django_db
class TestTransferFailedWebhook:
    def test_sets_payout_failed(self, payout):
        from orders.services import OrderService

        OrderService._handle_transfer_failed(
            {"object": {"id": "tr_test123"}}
        )
        payout.refresh_from_db()
        assert payout.status == "failed"


@pytest.mark.django_db
class TestPayoutPaidWebhook:
    def test_sets_payout_completed(self, payout, connected_account):
        from orders.services import OrderService

        payout.status = "in_transit"
        payout.save()

        OrderService._handle_payout_paid({
            "object": {
                "id": "po_test123",
                "destination": "ba_xxx",
                "amount": 5000,
                "currency": "usd",
            },
            "account": "acct_test123",
        })
        payout.refresh_from_db()
        assert payout.status == "completed"
        assert payout.stripe_payout_id == "po_test123"
