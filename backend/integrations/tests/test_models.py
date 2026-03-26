import pytest
from integrations.tests.factories import POSConnectionFactory, POSSyncLogFactory
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestPOSConnection:
    def test_create_pos_connection(self):
        connection = POSConnectionFactory(pos_type="square")
        assert connection.pos_type == "square"
        assert connection.is_active is True
        assert connection.payment_mode == "stripe"
        assert connection.restaurant is not None

    def test_one_connection_per_restaurant(self):
        restaurant = RestaurantFactory()
        POSConnectionFactory(restaurant=restaurant)
        with pytest.raises(Exception):
            POSConnectionFactory(restaurant=restaurant)


@pytest.mark.django_db
class TestPOSSyncLog:
    def test_create_sync_log(self):
        log = POSSyncLogFactory()
        assert log.status == "pending"
        assert log.attempt_count == 0
        assert log.order is not None
        assert log.pos_connection is not None

    def test_ordering_by_created_at(self):
        log1 = POSSyncLogFactory()
        log2 = POSSyncLogFactory(pos_connection=log1.pos_connection)
        from integrations.models import POSSyncLog
        logs = list(POSSyncLog.objects.all())
        assert logs[0].id == log2.id  # most recent first
