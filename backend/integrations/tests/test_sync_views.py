import pytest
from unittest.mock import patch
from rest_framework import status

from integrations.models import POSSyncLog
from integrations.tests.factories import POSConnectionFactory, POSSyncLogFactory
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestPOSSyncLogAPI:
    @pytest.fixture
    def setup(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="sync-test")
        connection = POSConnectionFactory(restaurant=restaurant)
        api_client.force_authenticate(user=user)
        return {
            "user": user,
            "restaurant": restaurant,
            "connection": connection,
            "client": api_client,
        }

    def test_list_sync_logs(self, setup):
        order = OrderFactory(restaurant=setup["restaurant"])
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="success")
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="failed")

        response = setup["client"].get("/api/restaurants/sync-test/pos/sync-logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_filter_sync_logs_by_status(self, setup):
        order = OrderFactory(restaurant=setup["restaurant"])
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="success")
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="failed")

        response = setup["client"].get(
            "/api/restaurants/sync-test/pos/sync-logs/?status=failed"
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["status"] == "failed"

    @patch("integrations.views.dispatch_order_to_pos")
    def test_retry_single_order(self, mock_task, setup):
        order = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        log = POSSyncLogFactory(
            order=order, pos_connection=setup["connection"], status="failed"
        )

        response = setup["client"].post(
            f"/api/restaurants/sync-test/pos/retry/{order.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_task.delay.assert_called_once_with(str(order.id))

    @patch("integrations.views.dispatch_order_to_pos")
    def test_retry_all_failed(self, mock_task, setup):
        order1 = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        order2 = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        order3 = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="synced")
        POSSyncLogFactory(order=order1, pos_connection=setup["connection"], status="failed")
        POSSyncLogFactory(order=order2, pos_connection=setup["connection"], status="failed")
        POSSyncLogFactory(order=order3, pos_connection=setup["connection"], status="success")

        response = setup["client"].post(
            "/api/restaurants/sync-test/pos/retry-all/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert mock_task.delay.call_count == 2

    def test_mark_manually_resolved(self, setup):
        order = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        log = POSSyncLogFactory(
            order=order, pos_connection=setup["connection"], status="failed"
        )

        response = setup["client"].patch(
            f"/api/restaurants/sync-test/pos/sync-logs/{log.id}/",
            {"status": "manually_resolved"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        log.refresh_from_db()
        assert log.status == "manually_resolved"
        order.refresh_from_db()
        assert order.pos_sync_status == "manually_resolved"
