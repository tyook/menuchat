from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from orders.llm.agent import OrderParsingAgent
from orders.llm.base import AgentResponse, ParsedOrder, ParsedOrderItem
from orders.llm.menu_context import build_menu_context
from orders.llm.recommendation_schemas import Recommendation, RecommendedItem
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemModifierFactory,
    MenuItemVariantFactory,
    MenuVersionFactory,
    RestaurantFactory,
)


class TestAgentResponse:
    def test_order_intent(self):
        order = ParsedOrder(
            items=[ParsedOrderItem(menu_item_id=1, variant_id=10, quantity=1)],
            language="en",
        )
        response = AgentResponse(intent="order", order=order)
        assert response.intent == "order"
        assert response.order is not None
        assert response.recommendation_context is None

    def test_recommendation_intent(self):
        response = AgentResponse(
            intent="recommendation",
            recommendation_context="popular items for 4 people",
        )
        assert response.intent == "recommendation"
        assert response.order is None
        assert response.recommendation_context == "popular items for 4 people"


class TestRecommendedItemQuantity:
    def test_quantity_defaults_to_one(self):
        item = RecommendedItem(menu_item_id=1, variant_id=10, reason="Great choice")
        assert item.quantity == 1

    def test_quantity_can_be_set(self):
        item = RecommendedItem(menu_item_id=1, variant_id=10, reason="For sharing", quantity=3)
        assert item.quantity == 3


class TestParsedOrder:
    def test_parsed_order_model(self):
        item = ParsedOrderItem(
            menu_item_id=1,
            variant_id=10,
            quantity=2,
            modifier_ids=[100, 101],
            special_requests="no onions",
        )
        order = ParsedOrder(items=[item], language="en")
        assert len(order.items) == 1
        assert order.language == "en"

    def test_parsed_order_defaults(self):
        item = ParsedOrderItem(menu_item_id=1, variant_id=10, quantity=1)
        assert item.modifier_ids == []
        assert item.special_requests == ""

        order = ParsedOrder(items=[item])
        assert order.language == "en"


@pytest.mark.django_db
class TestMenuContext:
    def test_build_menu_context_includes_items_and_prices(self):
        restaurant = RestaurantFactory()
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version, name="Pizzas")
        item = MenuItemFactory(category=cat, name="Margherita")
        MenuItemVariantFactory(menu_item=item, label="Large", price=Decimal("14.99"))
        MenuItemModifierFactory(menu_item=item, name="Extra Cheese", price_adjustment=Decimal("2.00"))

        context = build_menu_context(restaurant)
        assert "Margherita" in context
        assert "14.99" in context
        assert "Extra Cheese" in context
        assert "Pizzas" in context

    def test_build_menu_context_excludes_inactive(self):
        restaurant = RestaurantFactory()
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version)
        MenuItemFactory(category=cat, name="Active Item", status="active")
        MenuItemFactory(category=cat, name="Hidden Item", status="inactive")

        context = build_menu_context(restaurant)
        assert "Active Item" in context
        assert "Hidden Item" not in context

    def test_build_menu_context_includes_featured_marker(self):
        restaurant = RestaurantFactory()
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version, name="Mains")
        item = MenuItemFactory(category=cat, name="Signature Burger", is_featured=True)
        MenuItemVariantFactory(menu_item=item, label="Regular", price=Decimal("12.99"))

        context = build_menu_context(restaurant)
        assert "[FEATURED]" in context
        assert "Signature Burger" in context

    def test_build_menu_context_no_featured_marker_when_false(self):
        restaurant = RestaurantFactory()
        version = MenuVersionFactory(restaurant=restaurant, is_active=True)
        cat = MenuCategoryFactory(version=version, name="Mains")
        item = MenuItemFactory(category=cat, name="Plain Burger", is_featured=False)
        MenuItemVariantFactory(menu_item=item, label="Regular", price=Decimal("10.99"))

        context = build_menu_context(restaurant)
        assert "[FEATURED]" not in context
        assert "Plain Burger" in context


class TestOrderParsingAgent:
    def test_agent_properties(self):
        agent = OrderParsingAgent()
        assert agent.get_name() == "OrderParsingAgent"
        assert agent.default_model == "gpt-4o-mini"
        assert agent.get_output_schema() is ParsedOrder
        assert "order-taking assistant" in agent.get_instructions()

    def test_agent_context_building(self):
        agent = OrderParsingAgent()
        context = agent.get_context(
            raw_input="Two pizzas please",
            menu_context="## Pizzas\n  - Margherita",
        )
        assert "customer_order" in context
        assert context["customer_order"] == "Two pizzas please"
        assert "restaurant_menu" in context
        assert "Margherita" in context["restaurant_menu"]

    def test_agent_context_xml_formatting(self):
        agent = OrderParsingAgent()
        context = agent.get_context(
            raw_input="One burger",
            menu_context="## Burgers",
        )
        xml = agent._format_context(context)
        assert "<customer_order>" in xml
        assert "</customer_order>" in xml
        assert "<restaurant_menu>" in xml
        assert "</restaurant_menu>" in xml

    @patch("ai.base_agent.Agent")
    def test_agent_run_calls_agno(self, mock_agent_class):
        """Verify that run() creates an agno Agent and calls run() on it."""
        mock_parsed = ParsedOrder(
            items=[
                ParsedOrderItem(
                    menu_item_id=1,
                    variant_id=10,
                    quantity=2,
                )
            ],
            language="en",
        )
        mock_run_output = MagicMock()
        mock_run_output.content = mock_parsed

        mock_agent_instance = MagicMock()
        mock_agent_instance.run.return_value = mock_run_output
        mock_agent_class.return_value = mock_agent_instance

        result = OrderParsingAgent.run(
            raw_input="Two large margheritas",
            menu_context="menu context here",
        )

        assert result == mock_parsed
        assert result.items[0].menu_item_id == 1
        assert result.items[0].quantity == 2
        assert result.language == "en"
        mock_agent_instance.run.assert_called_once()
