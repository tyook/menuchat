"""
Unified order agent using agno.

Handles both order parsing and recommendation intent detection.
When the user asks for recommendations, it returns a recommendation context
string. When the user places an order, it returns a ParsedOrder.
"""

from typing import Any

from pydantic import BaseModel

from ai.base_agent import BaseAgent
from orders.llm.base import AgentResponse

INSTRUCTIONS = """\
You are an order-taking assistant for a restaurant. Given a customer's natural \
language input and the restaurant's menu, determine whether the customer is \
placing an order or asking for recommendations.

## Intent Detection

Set "intent" to "order" when the customer names specific items they want to order.
Set "intent" to "recommendation" when the customer asks for suggestions, popular \
items, help choosing, or wants you to pick items for them (e.g. "what's good?", \
"recommend something spicy", "food for 4 people", "what should I get?").

## When intent is "order"

Populate the "order" field with a ParsedOrder:
- Only use menu_item_id, variant_id, and modifier_id values from the menu provided
- If the customer doesn't specify a variant, use the DEFAULT variant
- If quantity is not specified, assume 1
- Keep special_requests brief and in English
- Detect the language the customer wrote/spoke in and set the "language" field
- If something the customer asked for is not on the menu, skip it (do NOT invent IDs)
- If an item is marked [SOLD OUT], still include it in the response using its \
menu_item_id and default variant. The system will notify the customer that it \
is unavailable. Do NOT substitute a sold-out item with a different item.
- If the customer mentions any food allergies (e.g. "I'm allergic to peanuts", \
"no shellfish, I have an allergy"), extract them into the "allergies" list as \
short labels (e.g. ["Peanuts", "Shellfish"]). Only include actual allergies, \
not plain preferences like "no onions".

## When intent is "recommendation"

Populate the "recommendation_context" field with a brief summary of what the \
customer is looking for (e.g. "popular items", "spicy dishes for 4 people", \
"vegetarian options", "desserts"). This context will be passed to a separate \
recommendation agent. Do NOT populate the "order" field.
"""


class OrderAgent(BaseAgent):
    default_model = "gpt-4o-mini"

    def get_name(self) -> str:
        return "OrderAgent"

    def get_instructions(self) -> str:
        return INSTRUCTIONS

    def get_output_schema(self) -> type[BaseModel] | None:
        return AgentResponse

    def get_context(self, **kwargs: Any) -> dict[str, str]:
        context = {}
        if "raw_input" in kwargs:
            context["customer_order"] = kwargs["raw_input"]
        if "menu_context" in kwargs:
            context["restaurant_menu"] = kwargs["menu_context"]
        return context

    def prompt(self, **kwargs: Any) -> str:
        return "Analyze the customer's input and respond with the appropriate intent."
