from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status

from orders.models import Tab, TabPayment
from orders.tests.factories import OrderFactory, TabFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestTabPayFull:
    @patch("orders.tab_payment_service.stripe")
    def test_create_full_tab_payment(self, mock_stripe, api_client):
        restaurant = RestaurantFactory(slug="tab-pay-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        OrderFactory(
            restaurant=restaurant,
            tab=tab,
            subtotal=Decimal("20.00"),
            tax_amount=Decimal("1.78"),
            total_price=Decimal("21.78"),
            status="confirmed",
            payment_status="deferred",
        )
        mock_intent = MagicMock()
        mock_intent.id = "pi_tab_123"
        mock_intent.client_secret = "pi_tab_123_secret"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        response = api_client.post(
            "/api/order/tab-pay-test/tab/pay/",
            {"tab_id": str(tab.id), "type": "full"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["client_secret"] == "pi_tab_123_secret"
        assert response.data["payment_id"]

        payment = TabPayment.objects.get(id=response.data["payment_id"])
        assert payment.amount == Decimal("21.78")
        assert payment.stripe_payment_intent_id == "pi_tab_123"


@pytest.mark.django_db
class TestTabPaySplitEven:
    @patch("orders.tab_payment_service.stripe")
    def test_create_split_even_payment(self, mock_stripe, api_client):
        restaurant = RestaurantFactory(slug="tab-split-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        OrderFactory(
            restaurant=restaurant,
            tab=tab,
            subtotal=Decimal("40.00"),
            tax_amount=Decimal("3.55"),
            total_price=Decimal("43.55"),
            status="confirmed",
            payment_status="deferred",
        )
        mock_intent = MagicMock()
        mock_intent.id = "pi_split_1"
        mock_intent.client_secret = "pi_split_1_secret"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        response = api_client.post(
            "/api/order/tab-split-test/tab/pay/",
            {"tab_id": str(tab.id), "type": "split_even", "split_count": 2},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        payment = TabPayment.objects.get(id=response.data["payment_id"])
        assert payment.amount == Decimal("21.78")
        assert payment.split_count == 2


@pytest.mark.django_db
class TestTabPayRejectsOpenTab:
    def test_cannot_pay_open_tab(self, api_client):
        restaurant = RestaurantFactory(slug="tab-pay-open", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3")

        response = api_client.post(
            "/api/order/tab-pay-open/tab/pay/",
            {"tab_id": str(tab.id), "type": "full"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTabConfirmPayment:
    @patch("orders.tab_payment_service.stripe")
    def test_confirm_tab_payment(self, mock_stripe, api_client):
        restaurant = RestaurantFactory(slug="tab-confirm-test", payment_model="tab")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        OrderFactory(
            restaurant=restaurant,
            tab=tab,
            subtotal=Decimal("20.00"),
            tax_amount=Decimal("1.78"),
            total_price=Decimal("21.78"),
            status="confirmed",
            payment_status="deferred",
        )
        payment = TabPayment.objects.create(
            tab=tab,
            type="full",
            amount=Decimal("21.78"),
            tax_amount=Decimal("1.78"),
            stripe_payment_intent_id="pi_tab_confirm",
        )
        mock_intent = MagicMock()
        mock_intent.status = "succeeded"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent

        response = api_client.post(
            f"/api/order/tab-confirm-test/tab/confirm-payment/{payment.id}/"
        )

        assert response.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.payment_status == "paid"
        assert payment.paid_at is not None
        tab.refresh_from_db()
        assert tab.status == "closed"


@pytest.mark.django_db
class TestTabPaymentWebhook:
    @patch("orders.services.stripe.Webhook.construct_event")
    def test_tab_payment_succeeded_webhook(self, mock_construct, api_client):
        restaurant = RestaurantFactory(slug="tab-webhook-test")
        tab = TabFactory(restaurant=restaurant, table_identifier="A3", status="closing")
        order = OrderFactory(
            restaurant=restaurant,
            tab=tab,
            subtotal=Decimal("20.00"),
            tax_amount=Decimal("1.78"),
            total_price=Decimal("21.78"),
            status="confirmed",
            payment_status="deferred",
        )
        payment = TabPayment.objects.create(
            tab=tab,
            type="full",
            amount=Decimal("21.78"),
            tax_amount=Decimal("1.78"),
            stripe_payment_intent_id="pi_tab_webhook_test",
            payment_status="pending",
        )
        mock_construct.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_tab_webhook_test"}},
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=b"raw_payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )

        assert response.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.payment_status == "paid"
        tab.refresh_from_db()
        assert tab.status == "closed"
        order.refresh_from_db()
        assert order.payment_status == "paid"
        assert order.paid_at is not None
