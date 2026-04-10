from unittest.mock import patch, MagicMock
from django.test import TestCase
from accounts.models import User
from notifications.models import DeviceToken
from notifications.services import send_push_notification


class PushNotificationServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.device = DeviceToken.objects.create(
            user=self.user, token="fcm-token-123", platform="ios"
        )

    @patch("notifications.services.messaging")
    def test_send_push_to_user(self, mock_messaging):
        mock_messaging.send.return_value = "projects/test/messages/123"
        result = send_push_notification(
            user=self.user,
            title="Order Ready",
            body="Your order #42 is ready for pickup",
        )
        assert result == 1
        mock_messaging.send.assert_called_once()
        call_args = mock_messaging.send.call_args[0][0]
        assert call_args.token == "fcm-token-123"
        assert call_args.notification.title == "Order Ready"

    @patch("notifications.services.messaging")
    def test_deactivates_invalid_token(self, mock_messaging):
        from firebase_admin.messaging import UnregisteredError
        mock_messaging.send.side_effect = UnregisteredError("invalid")
        send_push_notification(
            user=self.user,
            title="Test",
            body="Test",
        )
        self.device.refresh_from_db()
        assert self.device.is_active is False

    @patch("notifications.services.messaging")
    def test_skips_inactive_tokens(self, mock_messaging):
        self.device.is_active = False
        self.device.save()
        result = send_push_notification(
            user=self.user, title="Test", body="Test"
        )
        assert result == 0
        mock_messaging.send.assert_not_called()
