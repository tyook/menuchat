import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from integrations.adapters.toast import ToastAdapter
from integrations.models import POSConnection, POSSyncLog
from integrations.services import POSDispatchService
from integrations.encryption import encrypt_token
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestToastDispatchRouting:
    """Verify POSDispatchService routes Toast connections to ToastAdapter."""

    @pytest.fixture(autouse=True)
    def enable_toast(self, settings):
        settings.TOAST_POS_ENABLED = True

    def test_get_adapter_returns_toast_adapter(self):
        connection = POSConnectionFactory(pos_type="toast")
        adapter = POSDispatchService._get_adapter(connection)
        assert isinstance(adapter, ToastAdapter)

    @patch("integrations.adapters.toast.ToastAdapter.push_order")
    def test_dispatch_toast_order_success(self, mock_push):
        from integrations.adapters.base import PushResult
        mock_push.return_value = PushResult(
            success=True, external_order_id="toast-guid-abc"
        )

        connection = POSConnectionFactory(
            pos_type="toast",
            external_location_id="restaurant-guid-123",
            oauth_access_token=encrypt_token("tok"),
        )
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"
        assert order.external_order_id == "toast-guid-abc"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "success"

    @patch("integrations.adapters.toast.ToastAdapter.push_order")
    def test_dispatch_toast_order_failure_retries(self, mock_push):
        from integrations.adapters.base import PushResult
        mock_push.return_value = PushResult(
            success=False, error_message="Toast: Restaurant closed"
        )

        connection = POSConnectionFactory(
            pos_type="toast",
            external_location_id="restaurant-guid-123",
            oauth_access_token=encrypt_token("tok"),
        )
        order = OrderFactory(restaurant=connection.restaurant)

        with pytest.raises(Exception, match="POS dispatch failed"):
            POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "retrying"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "retrying"
        assert "Restaurant closed" in log.last_error
