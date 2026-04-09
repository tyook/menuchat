"""
Service layer for AI-powered menu recommendations.

Gathers user preferences and order history, builds context for the
RecommendationAgent, and validates the returned item IDs against the database.
"""

import logging

from orders.llm.menu_context import build_menu_context
from orders.llm.recommendation_agent import RecommendationAgent
from orders.models import Order, OrderItem
from restaurants.models import MenuItem, MenuItemVariant, Restaurant

logger = logging.getLogger(__name__)


class RecommendationService:

    @staticmethod
    def _build_preferences_context(
        user=None,
        dietary_preferences: list[str] | None = None,
        allergies: list[str] | None = None,
        language: str = "en",
    ) -> str:
        """Build a text block describing the customer's preferences."""
        lines = []

        prefs = dietary_preferences or (user.dietary_preferences if user else [])
        allergy_list = allergies or (user.allergies if user else [])

        if prefs:
            lines.append(f"Dietary preferences: {', '.join(prefs)}")
        if allergy_list:
            lines.append(f"Allergies (MUST AVOID): {', '.join(allergy_list)}")
        if language and language != "en":
            lines.append(f"Preferred language: {language}")

        return "\n".join(lines) if lines else "No specific preferences provided."

    @staticmethod
    def _build_order_history_context(user, restaurant: Restaurant, limit: int = 10) -> str:
        """Build a text summary of the customer's recent orders at this restaurant."""
        if not user or not user.is_authenticated:
            return ""

        recent_orders = (
            Order.objects.filter(
                user=user,
                restaurant=restaurant,
                status__in=["confirmed", "preparing", "ready", "completed"],
            )
            .order_by("-created_at")[:limit]
        )

        if not recent_orders:
            return ""

        lines = ["Recent orders at this restaurant:"]
        for order in recent_orders:
            items = OrderItem.objects.filter(order=order).select_related(
                "menu_item", "variant"
            )
            item_names = [
                f"{item.menu_item.name} ({item.variant.label})" for item in items
            ]
            lines.append(f"- {order.created_at:%Y-%m-%d}: {', '.join(item_names)}")

        return "\n".join(lines)

    @classmethod
    def get_recommendations(
        cls,
        restaurant: Restaurant,
        user=None,
        dietary_preferences: list[str] | None = None,
        allergies: list[str] | None = None,
        language: str = "en",
    ) -> dict:
        """
        Generate AI-powered menu recommendations for a customer.

        Returns a dict with 'items' (validated recommendations) and 'greeting'.
        """
        menu_context = build_menu_context(restaurant)
        if not menu_context.strip() or menu_context.count("\n") < 3:
            return {"items": [], "greeting": "This restaurant's menu is not yet available."}

        preferences = cls._build_preferences_context(
            user=user,
            dietary_preferences=dietary_preferences,
            allergies=allergies,
            language=language,
        )
        order_history = cls._build_order_history_context(user, restaurant)

        kwargs = {"menu_context": menu_context, "preferences": preferences}
        if order_history:
            kwargs["order_history"] = order_history

        result = RecommendationAgent.run(**kwargs)

        # Validate recommended items against the database
        validated_items = []
        for rec in result.items:
            try:
                item = MenuItem.objects.select_related("category__version").get(
                    id=rec.menu_item_id, is_active=True
                )
                variant = MenuItemVariant.objects.get(
                    id=rec.variant_id, menu_item=item
                )
                validated_items.append(
                    {
                        "menu_item_id": item.id,
                        "menu_item_name": item.name,
                        "menu_item_description": item.description or "",
                        "variant_id": variant.id,
                        "variant_label": variant.label,
                        "variant_price": str(variant.price),
                        "image_url": item.image_url or "",
                        "reason": rec.reason,
                    }
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                logger.warning(
                    "Recommendation referenced invalid item_id=%s variant_id=%s, skipping",
                    rec.menu_item_id,
                    rec.variant_id,
                )
                continue

        return {
            "items": validated_items,
            "greeting": result.greeting,
        }
