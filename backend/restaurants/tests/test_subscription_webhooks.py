import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status

from restaurants.models import Subscription
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestSubscriptionWebhooks:
    @patch("stripe.Webhook.construct_event")
    def test_checkout_completed_activates_subscription(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="starter",
            status="trialing",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=14),
        )

        mock_construct.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "subscription": "sub_new123",
                    "customer": "cus_test123",
                    "metadata": {
                        "restaurant_id": str(restaurant.id),
                        "plan": "growth",
                    },
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.stripe_subscription_id == "sub_new123"
        assert sub.plan == "growth"
        assert sub.status == "active"

    @patch("stripe.Webhook.construct_event")
    def test_subscription_updated_changes_status(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_growth_monthly",
                                    "metadata": {},
                                }
                            }
                        ]
                    },
                    "metadata": {"plan": "growth"},
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.status == "past_due"

    @patch("stripe.Webhook.construct_event")
    def test_subscription_deleted_marks_canceled(self, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test123",
            stripe_customer_id="cus_test123",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK

        sub.refresh_from_db()
        assert sub.status == "canceled"

    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_failed_email_task.delay")
    def test_subscription_updated_to_past_due_sends_email(self, mock_email_task, mock_construct, api_client):
        restaurant = RestaurantFactory()
        sub = Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_test456",
            stripe_customer_id="cus_test456",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test456",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "metadata": {"plan": "growth"},
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_called_once_with(str(restaurant.id))

    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_failed_email_task.delay")
    def test_subscription_updated_past_due_to_past_due_no_duplicate_email(self, mock_email_task, mock_construct, api_client):
        """No duplicate email if already past_due."""
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="past_due",
            stripe_subscription_id="sub_test789",
            stripe_customer_id="cus_test789",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        mock_construct.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test789",
                    "status": "past_due",
                    "current_period_start": int(timezone.now().timestamp()),
                    "current_period_end": int((timezone.now() + timedelta(days=30)).timestamp()),
                    "cancel_at_period_end": False,
                    "metadata": {"plan": "growth"},
                }
            },
        }

        api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        mock_email_task.assert_not_called()

    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_success_email_task.delay")
    def test_invoice_paid_sends_success_email(self, mock_email_task, mock_construct, api_client):
        restaurant = RestaurantFactory()
        Subscription.objects.create(
            restaurant=restaurant,
            plan="growth",
            status="active",
            stripe_subscription_id="sub_invoice_test",
            stripe_customer_id="cus_invoice_test",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            order_count=50,
        )

        period_end_ts = int((timezone.now() + timedelta(days=30)).timestamp())
        mock_construct.return_value = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "subscription": "sub_invoice_test",
                    "amount_paid": 9900,
                    "currency": "usd",
                    "lines": {
                        "data": [
                            {
                                "period": {"end": period_end_ts},
                            }
                        ]
                    },
                }
            },
        }

        response = api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        assert response.status_code == status.HTTP_200_OK
        mock_email_task.assert_called_once_with(
            str(restaurant.id), 9900, "growth", period_end_ts
        )

    @patch("stripe.Webhook.construct_event")
    @patch("restaurants.tasks.send_payment_success_email_task.delay")
    def test_invoice_paid_without_subscription_skips_email(self, mock_email_task, mock_construct, api_client):
        """Non-subscription invoices should not trigger email."""
        mock_construct.return_value = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "subscription": None,
                    "amount_paid": 500,
                    "currency": "usd",
                }
            },
        }

        api_client.post(
            "/api/webhooks/stripe/",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_sig",
        )
        mock_email_task.assert_not_called()
