"""
AI recommendation agent that suggests menu items based on user preferences,
order history, and the restaurant's current menu.
"""

from typing import Any

from pydantic import BaseModel

from ai.base_agent import BaseAgent
from orders.llm.recommendation_schemas import Recommendation

INSTRUCTIONS = """\
You are a friendly food recommendation assistant for a restaurant. Given the \
restaurant's menu, customer preferences, and optionally their order history, \
suggest menu items the customer would enjoy.

Rules:
- Only recommend items from the provided menu (use real menu_item_id and variant_id values)
- Recommend 3-5 items unless fewer are available
- Respect dietary preferences and allergies — NEVER recommend items that conflict \
with listed allergies
- If order history is provided, suggest items they haven't tried yet, or popular \
items similar to what they've enjoyed before
- If no history is available, recommend popular or signature items that match \
their dietary preferences
- For each recommendation, give a brief, natural reason (1 sentence)
- Write the greeting in the customer's preferred language if provided, \
otherwise use English
- Keep the greeting warm but concise (1-2 sentences)
"""


class RecommendationAgent(BaseAgent):
    default_model = "gpt-4o-mini"

    def get_name(self) -> str:
        return "RecommendationAgent"

    def get_instructions(self) -> str:
        return INSTRUCTIONS

    def get_output_schema(self) -> type[BaseModel] | None:
        return Recommendation

    def get_context(self, **kwargs: Any) -> dict[str, str]:
        context = {}
        if "menu_context" in kwargs:
            context["restaurant_menu"] = kwargs["menu_context"]
        if "preferences" in kwargs:
            context["customer_preferences"] = kwargs["preferences"]
        if "order_history" in kwargs:
            context["order_history"] = kwargs["order_history"]
        if "recommendation_context" in kwargs:
            context["customer_request"] = kwargs["recommendation_context"]
        return context

    def prompt(self, **kwargs: Any) -> str:
        return "Recommend menu items for this customer based on the provided context."
