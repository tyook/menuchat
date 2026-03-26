import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.utils import timezone
from orders.models import Order
from restaurants.models import ConnectedAccount, Payout, Restaurant
from restaurants.services.payout_service import PayoutService
from orders.services import OrderService

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(email="owner@test.com", password="testpass123")


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(name="Integration Test", slug="integration-test", owner=owner)


@pytest.fixture
def connected_account(restaurant):
    return ConnectedAccount.objects.create(
        restaurant=restaurant,
        stripe_account_id="acct_integ123",
        onboarding_complete=True,
        payouts_enabled=True,
        charges_enabled=True,
    )


@pytest.mark.django_db
class TestFullPayoutFlow:
    @patch("restaurants.services.payout_service.redis_client")
    @patch("restaurants.services.payout_service.stripe.Transfer.create")
    def test_full_flow_order_to_payout(self, mock_transfer, mock_redis, connected_account, restaurant):
        """Test: order paid → T+2 passes → daily job transfers → webhook completes."""
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock

        # 1. Create paid orders (3 days ago = past T+2)
        for i in range(3):
            Order.objects.create(
                restaurant=restaurant,
                raw_input="test order",
                status="confirmed",
                payment_status="paid",
                payout_status="pending",
                subtotal=Decimal("20.00"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total_price=Decimal("20.00"),
                paid_at=timezone.now() - timedelta(days=3),
            )

        # 2. Run payout job
        mock_transfer.return_value = MagicMock(id="tr_integ123")
        PayoutService.process_restaurant_payout(restaurant)

        # 3. Verify payout created
        payout = Payout.objects.get(restaurant=restaurant)
        assert payout.amount == Decimal("60.00")
        assert payout.orders_count == 3
        assert payout.status == "pending"

        # 4. All orders marked as transferred
        assert Order.objects.filter(
            restaurant=restaurant, payout_status="transferred"
        ).count() == 3

        # 5. Simulate transfer.created webhook
        OrderService._handle_transfer_created(
            {"object": {"id": "tr_integ123"}}
        )
        payout.refresh_from_db()
        assert payout.status == "in_transit"

        # 6. Simulate payout.paid webhook
        OrderService._handle_payout_paid({
            "object": {"id": "po_integ123", "amount": 6000, "currency": "usd"},
            "account": "acct_integ123",
        })
        payout.refresh_from_db()
        assert payout.status == "completed"
        assert payout.stripe_payout_id == "po_integ123"

        # 7. All orders marked as paid_out
        assert Order.objects.filter(
            restaurant=restaurant, payout_status="paid_out"
        ).count() == 3
