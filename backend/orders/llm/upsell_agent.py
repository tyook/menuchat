"""
Upsell recommendation agent.

Suggests 1-2 additional menu items based on the customer's cart contents
and the restaurant's menu. Prefers items flagged as is_upsellable.
"""

from typing import Any

from pydantic import BaseModel, Field

from ai.base_agent import BaseAgent


class UpsellSuggestion(BaseModel):
    menu_item_id: int
    name: str
    reason: str


class UpsellRecommendations(BaseModel):
    suggestions: list[UpsellSuggestion] = Field(
        default_factory=list, max_length=2
    )


INSTRUCTIONS = """\
You are an upsell recommendation assistant for a restaurant. Given the \
customer's current cart items and the full restaurant menu, suggest 1-2 \
additional items the customer might enjoy.

Rules:
- Suggest items that COMPLEMENT what the customer already ordered (e.g. \
a drink with a meal, a dessert after an entree, a side dish).
- NEVER suggest items the customer already has in their cart.
- Prefer items marked [UPSELLABLE] — these are items the restaurant \
specifically wants to promote.
- If no items are marked [UPSELLABLE], choose the best complementary \
items from the full menu.
- Return at most 2 suggestions.
- Each suggestion must include the menu_item_id from the menu, the item \
name, and a short reason (1 sentence) explaining why it pairs well.
- Only use menu_item_id values from the provided menu. Never invent IDs.
"""


class UpsellRecommendationAgent(BaseAgent):
    default_model = "gpt-4o-mini"

    def get_name(self) -> str:
        return "UpsellRecommendationAgent"

    def get_instructions(self) -> str:
        return INSTRUCTIONS

    def get_output_schema(self) -> type[BaseModel] | None:
        return UpsellRecommendations

    def get_context(self, **kwargs: Any) -> dict[str, str]:
        context = {}
        if "cart_summary" in kwargs:
            context["customer_cart"] = kwargs["cart_summary"]
        if "menu_context" in kwargs:
            context["restaurant_menu"] = kwargs["menu_context"]
        return context

    def prompt(self, **kwargs: Any) -> str:
        return (
            "Based on what the customer has in their cart, suggest 1-2 "
            "complementary items they might enjoy."
        )
