import pytest
from unittest.mock import patch, MagicMock

from integrations.models import POSConnection, POSSyncLog
from integrations.services import POSDispatchService
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestPOSDispatchService:
    def test_dispatch_no_connection_sets_not_applicable(self):
        order = OrderFactory()
        POSDispatchService.dispatch(str(order.id))
        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"

    def test_dispatch_inactive_connection_sets_not_applicable(self):
        connection = POSConnectionFactory(is_active=False)
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))
        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"

    def test_dispatch_none_type_sets_not_applicable(self):
        connection = POSConnectionFactory(pos_type="none")
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))
        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"

    @patch("integrations.services.POSDispatchService._get_adapter")
    def test_dispatch_success(self, mock_get_adapter):
        from integrations.adapters.base import PushResult
        mock_adapter = MagicMock()
        mock_adapter.push_order.return_value = PushResult(
            success=True, external_order_id="sq_order_123"
        )
        mock_get_adapter.return_value = mock_adapter

        connection = POSConnectionFactory(pos_type="square")
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"
        assert order.external_order_id == "sq_order_123"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "success"
        assert log.external_order_id == "sq_order_123"

    @patch("integrations.services.POSDispatchService._get_adapter")
    def test_dispatch_failure(self, mock_get_adapter):
        from integrations.adapters.base import PushResult
        mock_adapter = MagicMock()
        mock_adapter.push_order.return_value = PushResult(
            success=False, error_message="API timeout"
        )
        mock_get_adapter.return_value = mock_adapter

        connection = POSConnectionFactory(pos_type="square")
        order = OrderFactory(restaurant=connection.restaurant)

        with pytest.raises(Exception, match="POS dispatch failed"):
            POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "retrying"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "retrying"
        assert log.last_error == "API timeout"
        assert log.attempt_count == 1
