import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from config.asgi import application


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestKitchenWebSocket:
    async def test_connect_to_kitchen(self):
        restaurant = await self._create_restaurant("ws-test")
        communicator = WebsocketCommunicator(application, f"/ws/kitchen/{restaurant.slug}/")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_receive_order_broadcast(self):
        restaurant = await self._create_restaurant("ws-broadcast")
        communicator = WebsocketCommunicator(application, f"/ws/kitchen/{restaurant.slug}/")
        connected, _ = await communicator.connect()
        assert connected

        # Simulate broadcasting an order
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"kitchen_{restaurant.slug}",
            {
                "type": "order_update",
                "data": {
                    "id": "test-uuid",
                    "status": "confirmed",
                    "items": [],
                },
            },
        )

        response = await communicator.receive_json_from(timeout=5)
        assert response["id"] == "test-uuid"
        assert response["status"] == "confirmed"
        await communicator.disconnect()

    @staticmethod
    async def _create_restaurant(slug):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        from channels.db import database_sync_to_async

        from restaurants.models import Restaurant

        @database_sync_to_async
        def create():
            owner = User.objects.create_user(email=f"{slug}@example.com", password="testpass123")
            return Restaurant.objects.create(name=f"WS Test {slug}", slug=slug, owner=owner)

        return await create()
