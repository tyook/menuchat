import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.utils import timezone
from restaurants.services.payout_service import PayoutService
from restaurants.models import ConnectedAccount, Payout, Restaurant
from orders.models import Order

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
        onboarding_complete=True,
        payouts_enabled=True,
        charges_enabled=True,
    )


@pytest.fixture
def settled_paid_order(restaurant):
    """An order paid 3 days ago (past T+2 window)."""
    return Order.objects.create(
        restaurant=restaurant,
        raw_input="test order",
        status="confirmed",
        payment_status="paid",
        payout_status="pending",
        subtotal=Decimal("10.00"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total_price=Decimal("10.00"),
        paid_at=timezone.now() - timedelta(days=3),
    )


@pytest.mark.django_db
class TestPayoutServiceProcessRestaurant:
    @patch("restaurants.services.payout_service.redis_client")
    @patch("restaurants.services.payout_service.stripe.Transfer.create")
    def test_creates_transfer_for_settled_orders(
        self, mock_transfer, mock_redis, connected_account, settled_paid_order
    ):
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock
        mock_transfer.return_value = MagicMock(id="tr_test123")

        PayoutService.process_restaurant_payout(connected_account.restaurant)

        mock_transfer.assert_called_once()
        call_kwargs = mock_transfer.call_args[1]
        assert call_kwargs["amount"] == 1000  # $10.00 in cents
        assert call_kwargs["destination"] == "acct_test123"

        payout = Payout.objects.get(restaurant=connected_account.restaurant)
        assert payout.amount == Decimal("10.00")
        assert payout.status == "pending"
        assert payout.stripe_transfer_id == "tr_test123"

        settled_paid_order.refresh_from_db()
        assert settled_paid_order.payout_status == "transferred"
        assert settled_paid_order.payout == payout

    @patch("restaurants.services.payout_service.redis_client")
    def test_skips_restaurant_without_connected_account(self, mock_redis, restaurant):
        PayoutService.process_restaurant_payout(restaurant)
        assert Payout.objects.count() == 0

    @patch("restaurants.services.payout_service.redis_client")
    def test_skips_unsettled_orders(self, mock_redis, connected_account, restaurant):
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock

        Order.objects.create(
            restaurant=restaurant,
            raw_input="test order",
            status="confirmed",
            payment_status="paid",
            payout_status="pending",
            subtotal=Decimal("10.00"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total_price=Decimal("10.00"),
            paid_at=timezone.now() - timedelta(days=1),
        )
        PayoutService.process_restaurant_payout(restaurant)
        assert Payout.objects.count() == 0

    @patch("restaurants.services.payout_service.redis_client")
    @patch("restaurants.services.payout_service.stripe.Transfer.create")
    def test_deducts_pending_refund_balance(
        self, mock_transfer, mock_redis, connected_account, settled_paid_order
    ):
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock

        connected_account.pending_refund_balance = Decimal("3.00")
        connected_account.save()
        mock_transfer.return_value = MagicMock(id="tr_test456")

        PayoutService.process_restaurant_payout(connected_account.restaurant)

        call_kwargs = mock_transfer.call_args[1]
        assert call_kwargs["amount"] == 700  # $10.00 - $3.00 refund = $7.00

        connected_account.refresh_from_db()
        assert connected_account.pending_refund_balance == Decimal("0")
