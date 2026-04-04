from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework import status

from orders.llm.upsell_agent import UpsellRecommendations, UpsellSuggestion
from orders.tests.factories import OrderFactory, OrderItemFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestUpsellSuggestionsEndpoint:
    @pytest.fixture
    def menu_setup(self):
        restaurant = RestaurantFactory(slug="upsell-test")
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version, name="Mains")
        dessert_cat = MenuCategoryFactory(version=version, name="Desserts")

        burger = MenuItemFactory(category=cat, name="Burger")
        burger_variant = MenuItemVariantFactory(
            menu_item=burger, label="Regular", price=Decimal("12.99"), is_default=True
        )

        fries = MenuItemFactory(category=cat, name="Fries", is_upsellable=True)
        fries_variant = MenuItemVariantFactory(
            menu_item=fries, label="Regular", price=Decimal("4.99"), is_default=True
        )

        cake = MenuItemFactory(category=dessert_cat, name="Chocolate Cake", is_upsellable=True)
        cake_variant = MenuItemVariantFactory(
            menu_item=cake, label="Slice", price=Decimal("6.99"), is_default=True
        )

        order = OrderFactory(restaurant=restaurant, status="pending_payment")
        OrderItemFactory(order=order, menu_item=burger, variant=burger_variant, quantity=1)

        return {
            "restaurant": restaurant,
            "order": order,
            "burger": burger,
            "fries": fries,
            "cake": cake,
        }

    @patch("orders.llm.upsell_agent.UpsellRecommendationAgent.run")
    def test_upsell_returns_suggestions(self, mock_run, api_client, menu_setup):
        mock_run.return_value = UpsellRecommendations(
            suggestions=[
                UpsellSuggestion(
                    menu_item_id=menu_setup["fries"].id,
                    name="Fries",
                    reason="Fries go great with a burger!",
                ),
                UpsellSuggestion(
                    menu_item_id=menu_setup["cake"].id,
                    name="Chocolate Cake",
                    reason="Perfect dessert to finish your meal.",
                ),
            ]
        )

        order = menu_setup["order"]
        response = api_client.post(
            f"/api/order/upsell-test/upsell-suggestions/{order.id}/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        suggestions = response.data["suggestions"]
        assert len(suggestions) == 2
        assert suggestions[0]["name"] == "Fries"
        assert suggestions[0]["price"] == "4.99"
        assert suggestions[0]["reason"] == "Fries go great with a burger!"
        assert suggestions[1]["name"] == "Chocolate Cake"

    @patch("orders.llm.upsell_agent.UpsellRecommendationAgent.run")
    def test_upsell_filters_cart_items(self, mock_run, api_client, menu_setup):
        """Items already in the cart should not appear as upsell suggestions."""
        mock_run.return_value = UpsellRecommendations(
            suggestions=[
                UpsellSuggestion(
                    menu_item_id=menu_setup["burger"].id,
                    name="Burger",
                    reason="Have another burger!",
                ),
                UpsellSuggestion(
                    menu_item_id=menu_setup["fries"].id,
                    name="Fries",
                    reason="Fries go great with a burger!",
                ),
            ]
        )

        order = menu_setup["order"]
        response = api_client.post(
            f"/api/order/upsell-test/upsell-suggestions/{order.id}/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        suggestions = response.data["suggestions"]
        # Burger should be filtered out since it's already in the cart
        assert len(suggestions) == 1
        assert suggestions[0]["name"] == "Fries"

    @patch("orders.llm.upsell_agent.UpsellRecommendationAgent.run")
    def test_upsell_filters_invalid_item_ids(self, mock_run, api_client, menu_setup):
        """Invalid menu item IDs from the AI should be silently skipped."""
        mock_run.return_value = UpsellRecommendations(
            suggestions=[
                UpsellSuggestion(
                    menu_item_id=99999,
                    name="Ghost Item",
                    reason="This doesn't exist.",
                ),
            ]
        )

        order = menu_setup["order"]
        response = api_client.post(
            f"/api/order/upsell-test/upsell-suggestions/{order.id}/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["suggestions"]) == 0

    def test_upsell_returns_404_for_wrong_restaurant(self, api_client, menu_setup):
        order = menu_setup["order"]
        response = api_client.post(
            f"/api/order/wrong-slug/upsell-suggestions/{order.id}/",
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("orders.llm.upsell_agent.UpsellRecommendationAgent.run")
    def test_upsell_returns_max_2_suggestions(self, mock_run, api_client, menu_setup):
        """Even if the AI returns more, we cap at 2."""
        mock_run.return_value = UpsellRecommendations(
            suggestions=[
                UpsellSuggestion(
                    menu_item_id=menu_setup["fries"].id,
                    name="Fries",
                    reason="Great side.",
                ),
                UpsellSuggestion(
                    menu_item_id=menu_setup["cake"].id,
                    name="Chocolate Cake",
                    reason="Sweet ending.",
                ),
            ]
        )

        order = menu_setup["order"]
        response = api_client.post(
            f"/api/order/upsell-test/upsell-suggestions/{order.id}/",
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["suggestions"]) <= 2
