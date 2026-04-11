# Voice-Based Menu Recommendation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the voice ordering agent to detect recommendation requests and display browsable, add-to-cart menu item cards inline in the chat UI.

**Architecture:** Extend the existing `OrderParsingAgent` into a unified `OrderAgent` that detects intent (order vs. recommendation). Order intent follows the existing flow. Recommendation intent delegates to the existing `RecommendationService`, which is enhanced to return all variants/modifiers per item. The frontend renders recommendations as inline expandable cards in the voice chat.

**Tech Stack:** Django, agno (LLM framework), Pydantic, Next.js 14, React, Zustand, Tailwind CSS, shadcn/ui

**Spec:** `docs/superpowers/specs/2026-04-11-voice-recommendation-design.md`

---

## File Structure

### Backend — New Files
- `backend/restaurants/migrations/XXXX_menu_item_is_featured.py` — Migration for `is_featured` field

### Backend — Modified Files
- `backend/restaurants/models.py` — Add `is_featured` to `MenuItem` (line 161, after `is_upsellable`)
- `backend/orders/llm/base.py` — Add `AgentResponse` model
- `backend/orders/llm/agent.py` — Rename class to `OrderAgent`, expand instructions for intent detection
- `backend/orders/llm/__init__.py` — Update re-export from `OrderParsingAgent` to `OrderAgent`
- `backend/orders/llm/menu_context.py` — Add `[FEATURED]` marker (line 29-31, alongside `[SOLD OUT]` and `[UPSELLABLE]`)
- `backend/orders/llm/recommendation_schemas.py` — Add `quantity` field to `RecommendedItem`
- `backend/orders/recommendation_service.py` — Enrich response with variants, modifiers, `is_featured`, `quantity`; accept `recommendation_context` and `max_items`
- `backend/orders/services.py` — `parse_order()` handles both intents, accepts `user` param
- `backend/orders/views.py` — Add auth class to `ParseOrderView`, pass `request.user`
- `backend/restaurants/serializers/restaurant_serializers.py` — Add `is_featured` to `MenuItemSerializer` and `PublicMenuItemSerializer`
- `backend/orders/tests/test_llm.py` — Update tests for renamed agent, add intent detection tests
- `backend/orders/tests/test_api_orders.py` — Update `OrderParsingAgent.run` mock patches to `OrderAgent.run`
- `backend/restaurants/tests/test_subscription_gate.py` — Update `OrderParsingAgent.run` mock patches to `OrderAgent.run`
- `backend/restaurants/serializers/menu_upload_serializers.py` — Add `is_featured` to `ParsedItemInput`
- `backend/restaurants/tests/factories.py` — No change needed (factory uses model defaults)

### Frontend — New Files
- `frontend/src/app/order/[slug]/components/RecommendationCard.tsx` — Expandable recommendation card component

### Frontend — Modified Files
- `frontend/src/types/index.ts` — Add `RecommendationItem` type, `RecommendationResponse`, update `ParseOrderResult` union; add `is_featured` to `MenuItem` and `ParsedMenuItem`
- `frontend/src/lib/api.ts` — Update `parseOrder` return type
- `frontend/src/hooks/use-parse-order.ts` — Guard `onSuccess` with type check
- `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx` — Handle recommendation responses, render cards
- `frontend/src/hooks/use-admin-menu.ts` — Add `useToggleFeatured` hook
- `frontend/src/app/account/restaurants/[slug]/menu/MenuManagementPageClient.tsx` — Add `is_featured` toggle
- `frontend/src/components/parsed-menu-editor.tsx` — Add `is_featured` checkbox for AI-uploaded menus

### Backend — No Changes Needed (Automatic)
- `backend/restaurants/views.py` — CRUD views use `MenuItemSerializer` via DRF generics; `is_featured` passes through automatically once the serializer is updated

---

## Chunk 1: Backend — Model, Schema, and Menu Context

### Task 1: Add `is_featured` field to MenuItem model

**Files:**
- Modify: `backend/restaurants/models.py:160-161`
- Test: `backend/orders/tests/test_llm.py`

- [ ] **Step 1: Add `is_featured` field to the MenuItem model**

In `backend/restaurants/models.py`, add `is_featured` after `is_upsellable` (line 160):

```python
    is_upsellable = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
```

- [ ] **Step 2: Generate the migration**

Run: `cd backend && python manage.py makemigrations restaurants -n menu_item_is_featured`
Expected: Creates `backend/restaurants/migrations/XXXX_menu_item_is_featured.py`

- [ ] **Step 3: Apply the migration**

Run: `cd backend && python manage.py migrate`
Expected: `Applying restaurants.XXXX_menu_item_is_featured... OK`

- [ ] **Step 4: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/migrations/*_menu_item_is_featured.py
git commit -m "feat: add is_featured boolean field to MenuItem model"
```

### Task 2: Add `[FEATURED]` marker to menu context

**Files:**
- Modify: `backend/orders/llm/menu_context.py:28-31`
- Test: `backend/orders/tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/orders/tests/test_llm.py` in `TestMenuContext`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest orders/tests/test_llm.py::TestMenuContext::test_build_menu_context_includes_featured_marker orders/tests/test_llm.py::TestMenuContext::test_build_menu_context_no_featured_marker_when_false -v`
Expected: FAIL — `[FEATURED]` not in context

- [ ] **Step 3: Add `[FEATURED]` marker to `build_menu_context()`**

In `backend/orders/llm/menu_context.py`, modify the marker-building block (around line 28-31):

```python
        for item in visible_items:
            markers = ""
            if item.status == MenuItem.Status.SOLD_OUT:
                markers += " [SOLD OUT]"
            if item.is_upsellable:
                markers += " [UPSELLABLE]"
            if item.is_featured:
                markers += " [FEATURED]"
            lines.append(f"  - {item.name} (item_id: {item.id}){markers}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest orders/tests/test_llm.py::TestMenuContext -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/llm/menu_context.py backend/orders/tests/test_llm.py
git commit -m "feat: add [FEATURED] marker to menu context for LLM"
```

### Task 3: Add `AgentResponse` model and update `RecommendedItem` with quantity

**Files:**
- Modify: `backend/orders/llm/base.py`
- Modify: `backend/orders/llm/recommendation_schemas.py`
- Test: `backend/orders/tests/test_llm.py`

- [ ] **Step 1: Write failing tests for the new models**

Add to `backend/orders/tests/test_llm.py`:

```python
from orders.llm.base import AgentResponse, ParsedOrder, ParsedOrderItem
from orders.llm.recommendation_schemas import RecommendedItem, Recommendation


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest orders/tests/test_llm.py::TestAgentResponse orders/tests/test_llm.py::TestRecommendedItemQuantity -v`
Expected: FAIL — `AgentResponse` not importable

- [ ] **Step 3: Add `AgentResponse` to `base.py`**

Add to `backend/orders/llm/base.py`:

```python
from typing import Literal


class AgentResponse(BaseModel):
    """Union response from the OrderAgent — either an order or a recommendation intent."""
    intent: Literal["order", "recommendation"]
    order: ParsedOrder | None = None
    recommendation_context: str | None = None
```

- [ ] **Step 4: Add `quantity` to `RecommendedItem`**

In `backend/orders/llm/recommendation_schemas.py`:

```python
class RecommendedItem(BaseModel):
    menu_item_id: int
    variant_id: int
    reason: str = Field(description="Brief explanation of why this item is recommended")
    quantity: int = Field(default=1, description="Suggested quantity for this item")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest orders/tests/test_llm.py::TestAgentResponse orders/tests/test_llm.py::TestRecommendedItemQuantity -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/orders/llm/base.py backend/orders/llm/recommendation_schemas.py backend/orders/tests/test_llm.py
git commit -m "feat: add AgentResponse model and quantity field to RecommendedItem"
```

### Task 4: Rename `OrderParsingAgent` to `OrderAgent` with intent detection

**Files:**
- Modify: `backend/orders/llm/agent.py`
- Modify: `backend/orders/tests/test_llm.py`

- [ ] **Step 1: Write failing tests for the renamed agent**

Update `backend/orders/tests/test_llm.py`. Replace the `TestOrderParsingAgent` class:

```python
from orders.llm.agent import OrderAgent
from orders.llm.base import AgentResponse, ParsedOrder, ParsedOrderItem


class TestOrderAgent:
    def test_agent_properties(self):
        agent = OrderAgent()
        assert agent.get_name() == "OrderAgent"
        assert agent.default_model == "gpt-4o-mini"
        assert agent.get_output_schema() is AgentResponse
        assert "order-taking assistant" in agent.get_instructions()
        assert "recommendation" in agent.get_instructions().lower()

    def test_agent_context_building(self):
        agent = OrderAgent()
        context = agent.get_context(
            raw_input="Two pizzas please",
            menu_context="## Pizzas\n  - Margherita",
        )
        assert "customer_order" in context
        assert context["customer_order"] == "Two pizzas please"
        assert "restaurant_menu" in context

    def test_agent_context_xml_formatting(self):
        agent = OrderAgent()
        context = agent.get_context(
            raw_input="One burger",
            menu_context="## Burgers",
        )
        xml = agent._format_context(context)
        assert "<customer_order>" in xml
        assert "<restaurant_menu>" in xml

    @patch("ai.base_agent.Agent")
    def test_agent_run_order_intent(self, mock_agent_class):
        """Verify that run() returns an AgentResponse for order intents."""
        mock_parsed = AgentResponse(
            intent="order",
            order=ParsedOrder(
                items=[ParsedOrderItem(menu_item_id=1, variant_id=10, quantity=2)],
                language="en",
            ),
        )
        mock_run_output = MagicMock()
        mock_run_output.content = mock_parsed
        mock_agent_instance = MagicMock()
        mock_agent_instance.run.return_value = mock_run_output
        mock_agent_class.return_value = mock_agent_instance

        result = OrderAgent.run(
            raw_input="Two large margheritas",
            menu_context="menu context here",
        )

        assert result.intent == "order"
        assert result.order.items[0].menu_item_id == 1
        assert result.order.items[0].quantity == 2

    @patch("ai.base_agent.Agent")
    def test_agent_run_recommendation_intent(self, mock_agent_class):
        """Verify that run() returns recommendation context for recommendation intents."""
        mock_parsed = AgentResponse(
            intent="recommendation",
            recommendation_context="popular items, spicy preference",
        )
        mock_run_output = MagicMock()
        mock_run_output.content = mock_parsed
        mock_agent_instance = MagicMock()
        mock_agent_instance.run.return_value = mock_run_output
        mock_agent_class.return_value = mock_agent_instance

        result = OrderAgent.run(
            raw_input="What's popular here?",
            menu_context="menu context here",
        )

        assert result.intent == "recommendation"
        assert "popular" in result.recommendation_context
```

Also update the import at the top of the file — remove `OrderParsingAgent`, add `OrderAgent`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest orders/tests/test_llm.py::TestOrderAgent -v`
Expected: FAIL — `OrderAgent` not importable

- [ ] **Step 3: Rename and expand the agent**

Replace the contents of `backend/orders/llm/agent.py`:

```python
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
You are an order-taking and recommendation assistant for a restaurant. Given a \
customer's natural language input and the restaurant's menu, determine whether \
the customer is placing an order or asking for recommendations.

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest orders/tests/test_llm.py::TestOrderAgent -v`
Expected: All PASS

- [ ] **Step 5: Update `__init__.py` re-exports**

In `backend/orders/llm/__init__.py`, update to export `OrderAgent` instead of `OrderParsingAgent`:

```python
from orders.llm.agent import OrderAgent
from orders.llm.base import ParsedOrder, ParsedOrderItem
from orders.llm.menu_context import build_menu_context

__all__ = [
    "ParsedOrder",
    "ParsedOrderItem",
    "OrderAgent",
    "build_menu_context",
]
```

- [ ] **Step 6: Run ALL tests to check nothing else broke**

Run: `cd backend && pytest orders/tests/test_llm.py -v`
Expected: All PASS (the old `TestOrderParsingAgent` class was replaced)

- [ ] **Step 7: Commit**

```bash
git add backend/orders/llm/agent.py backend/orders/llm/__init__.py backend/orders/tests/test_llm.py
git commit -m "feat: rename OrderParsingAgent to OrderAgent with intent detection"
```

---

## Chunk 2: Backend — Service Layer and API

### Task 5: Enhance `RecommendationService` with full item data

**Files:**
- Modify: `backend/orders/recommendation_service.py`

- [ ] **Step 1: Update `get_recommendations()` to accept `recommendation_context` and `max_items`, and return enriched items**

In `backend/orders/recommendation_service.py`, update the method signature and enrichment logic:

```python
    @classmethod
    def get_recommendations(
        cls,
        restaurant: Restaurant,
        user=None,
        dietary_preferences: list[str] | None = None,
        allergies: list[str] | None = None,
        language: str = "en",
        recommendation_context: str | None = None,
        max_items: int | None = None,
    ) -> dict:
```

Add `recommendation_context` to the kwargs passed to the agent:

```python
        if recommendation_context:
            kwargs["recommendation_context"] = recommendation_context
```

Update the `RecommendationAgent.get_context()` to accept this (already handles arbitrary kwargs via `**kwargs`).

Replace the existing validated items loop with the enriched version below. Note: this changes field names from `menu_item_name`/`menu_item_description` to `name`/`description` to match the spec's API response shape. No existing frontend code consumes the old field names (the recommendation endpoint is only used by the existing recommendation page, which re-fetches menu data separately). The `greeting` field is preserved in the return dict for backward compatibility.

```python
        validated_items = []
        for rec in result.items:
            try:
                item = MenuItem.objects.select_related("category__version").get(
                    id=rec.menu_item_id, status=MenuItem.Status.ACTIVE
                )
                variant = MenuItemVariant.objects.get(
                    id=rec.variant_id, menu_item=item
                )
                all_variants = [
                    {
                        "id": v.id,
                        "label": v.label,
                        "price": str(v.price),
                        "is_default": v.is_default,
                    }
                    for v in item.variants.all()
                ]
                all_modifiers = [
                    {
                        "id": m.id,
                        "name": m.name,
                        "price_adjustment": str(m.price_adjustment),
                    }
                    for m in item.modifiers.all()
                ]
                validated_items.append(
                    {
                        "menu_item_id": item.id,
                        "name": item.name,
                        "description": item.description or "",
                        "image_url": item.image_url or "",
                        "variant_id": variant.id,
                        "variant_label": variant.label,
                        "variant_price": str(variant.price),
                        "quantity": rec.quantity,
                        "reason": rec.reason,
                        "is_featured": item.is_featured,
                        "variants": all_variants,
                        "modifiers": all_modifiers,
                    }
                )
            except (MenuItem.DoesNotExist, MenuItemVariant.DoesNotExist):
                logger.warning(
                    "Recommendation referenced invalid item_id=%s variant_id=%s, skipping",
                    rec.menu_item_id,
                    rec.variant_id,
                )
                continue

            if max_items and len(validated_items) >= max_items:
                break

        # Still return `greeting` for backward compatibility with existing callers.
        # The voice recommendation flow in parse_order() drops the greeting —
        # it only uses `rec_result["items"]`.
        return {
            "items": validated_items,
            "greeting": result.greeting,
        }
```

Note: The existing `get_recommendations()` returns `{"items": ..., "greeting": ...}`. The enriched version keeps this same return shape. The `greeting` field is intentionally preserved for backward compatibility with any existing callers, but `parse_order()` drops it when constructing the voice recommendation response (see Task 7).

- [ ] **Step 2: Run existing tests to make sure nothing broke**

Run: `cd backend && pytest -v -k "recommend" --no-header`
Expected: PASS (existing tests still work since new params have defaults)

- [ ] **Step 3: Commit**

```bash
git add backend/orders/recommendation_service.py
git commit -m "feat: enrich recommendation response with variants, modifiers, quantity"
```

### Task 6: Update `RecommendationAgent` to accept `recommendation_context`

**Files:**
- Modify: `backend/orders/llm/recommendation_agent.py`

- [ ] **Step 1: Add `recommendation_context` to the agent's `get_context()`**

In `backend/orders/llm/recommendation_agent.py`, update `get_context()`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/orders/llm/recommendation_agent.py
git commit -m "feat: pass recommendation_context to RecommendationAgent"
```

### Task 7: Update `OrderService.parse_order()` to handle both intents

**Files:**
- Modify: `backend/orders/services.py:347-364`
- Modify: `backend/orders/views.py:24-36`

- [ ] **Step 1: Update `parse_order()` to accept `user` and handle recommendation intent**

In `backend/orders/services.py`, update the `parse_order` method:

```python
    @staticmethod
    def parse_order(restaurant: Restaurant, raw_input: str, user=None) -> dict:
        """Parse a natural language order via LLM and validate/price it.

        Checks subscription, runs LLM, validates against DB, increments count.
        Returns validated order dict or recommendation dict for frontend.
        """
        subscription = OrderService.check_subscription(restaurant)

        menu_context = build_menu_context(restaurant)
        agent_response = OrderAgent.run(
            raw_input=raw_input,
            menu_context=menu_context,
        )

        if agent_response.intent == "recommendation":
            # Do NOT increment order count for recommendations —
            # only actual orders consume the subscription quota.
            rec_result = RecommendationService.get_recommendations(
                restaurant=restaurant,
                user=user if user and user.is_authenticated else None,
                recommendation_context=agent_response.recommendation_context,
                max_items=3,
            )
            # Drop `greeting` from rec_result — the cards speak for themselves
            # in the voice chat UI (see spec: Non-Goals).
            return {
                "type": "recommendation",
                "items": rec_result["items"],
            }

        # intent == "order"
        parsed = agent_response.order
        result = OrderService.validate_and_price_order(restaurant, parsed)
        OrderService.increment_order_count(subscription)
        result["type"] = "order"
        return result
```

Update the top-level import — replace `from orders.llm.agent import OrderParsingAgent` (line 13) with:

```python
from orders.llm.agent import OrderAgent
from orders.recommendation_service import RecommendationService
```

Keep both as top-level imports. No local imports needed.

- [ ] **Step 2: Update `ParseOrderView` to pass `request.user`**

In `backend/orders/views.py`, update `ParseOrderView`:

```python
from accounts.authentication import CookieJWTAuthentication


class ParseOrderView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, slug):
        restaurant = OrderService.get_restaurant_by_slug(slug)

        serializer = ParseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = OrderService.parse_order(
            restaurant, serializer.validated_data["raw_input"], user=request.user
        )
        return Response(result)
```

- [ ] **Step 3: Update mock patches in existing test files**

The rename from `OrderParsingAgent` to `OrderAgent` breaks mock patches in two test files. Update them:

In `backend/orders/tests/test_api_orders.py`, replace all occurrences of:
```python
@patch("orders.services.OrderParsingAgent.run")
```
with:
```python
@patch("orders.services.OrderAgent.run")
```

In `backend/restaurants/tests/test_subscription_gate.py`, replace all occurrences of:
```python
@patch("orders.services.OrderParsingAgent.run")
```
with:
```python
@patch("orders.services.OrderAgent.run")
```

Also update the mock return values in these files: `OrderParsingAgent.run` currently returns a `ParsedOrder` directly, but `OrderAgent.run` now returns an `AgentResponse`. Wrap existing mock return values:

```python
# Before:
mock_run.return_value = ParsedOrder(items=[...], language="en")

# After:
from orders.llm.base import AgentResponse
mock_run.return_value = AgentResponse(
    intent="order",
    order=ParsedOrder(items=[...], language="en"),
)
```

- [ ] **Step 4: Run existing API tests**

Run: `cd backend && pytest orders/tests/ restaurants/tests/test_subscription_gate.py -v --no-header`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/orders/services.py backend/orders/views.py backend/orders/tests/test_api_orders.py backend/restaurants/tests/test_subscription_gate.py
git commit -m "feat: handle recommendation intent in parse_order endpoint"
```

### Task 8: Add `is_featured` to serializers

**Files:**
- Modify: `backend/restaurants/serializers/restaurant_serializers.py:164-177` (MenuItemSerializer)
- Modify: `backend/restaurants/serializers/restaurant_serializers.py:231-238` (PublicMenuItemSerializer)
- Modify: `backend/restaurants/serializers/menu_upload_serializers.py:55-59` (ParsedItemInput)

**Note:** The restaurant CRUD views (`MenuItemListCreateView`, `MenuItemDetailView` in `backend/restaurants/views.py`) use `MenuItemSerializer` via DRF generics. Once `is_featured` is added to the serializer's `fields`, it automatically passes through on create/update/retrieve — no view changes needed.

- [ ] **Step 1: Add `is_featured` to `MenuItemSerializer` fields**

In `backend/restaurants/serializers/restaurant_serializers.py`, update `MenuItemSerializer.Meta.fields` (line 165):

```python
        fields = [
            "id",
            "category_id",
            "name",
            "description",
            "image_url",
            "status",
            "is_upsellable",
            "is_featured",
            "sort_order",
            "variants",
            "modifiers",
        ]
```

- [ ] **Step 2: Add `is_featured` to `PublicMenuItemSerializer` fields**

In the same file, update `PublicMenuItemSerializer.Meta.fields` (line 238):

```python
        fields = ["id", "name", "description", "image_url", "is_sold_out", "is_featured", "variants", "modifiers"]
```

- [ ] **Step 3: Add `is_featured` to `ParsedItemInput` in menu upload serializers**

In `backend/restaurants/serializers/menu_upload_serializers.py`, update `ParsedItemInput` (line 55):

```python
class ParsedItemInput(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    image_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)
    is_featured = serializers.BooleanField(required=False, default=False)
    variants = ParsedVariantInput(many=True, min_length=1)
```

- [ ] **Step 4: Run existing tests**

Run: `cd backend && pytest restaurants/tests/ -v --no-header`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/serializers/restaurant_serializers.py backend/restaurants/serializers/menu_upload_serializers.py
git commit -m "feat: expose is_featured in menu item and menu upload serializers"
```

---

## Chunk 3: Frontend — Types, API, and Hook

### Task 9: Add recommendation types to frontend

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add `RecommendationItem` and `RecommendationResponse` types**

Add after the `ParsedOrderResponse` interface (line 130) in `frontend/src/types/index.ts`:

```typescript
export interface RecommendationItem {
  menu_item_id: number;
  name: string;
  description: string;
  image_url: string;
  variant_id: number;
  variant_label: string;
  variant_price: string;
  quantity: number;
  reason: string;
  is_featured: boolean;
  modifiers: MenuItemModifier[];
  variants: MenuItemVariant[];
}

export interface RecommendationResponse {
  type: "recommendation";
  items: RecommendationItem[];
}

export interface OrderParseResponse extends ParsedOrderResponse {
  type: "order";
}

export type ParseOrderResult = OrderParseResponse | RecommendationResponse;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add RecommendationItem and ParseOrderResult union types"
```

### Task 10: Update `parseOrder` API function return type

**Files:**
- Modify: `frontend/src/lib/api.ts:243-251`

- [ ] **Step 1: Update the return type**

In `frontend/src/lib/api.ts`, update the `parseOrder` function:

```typescript
export async function parseOrder(
  slug: string,
  rawInput: string
): Promise<ParseOrderResult> {
  return apiFetch<ParseOrderResult>(`/api/order/${slug}/parse/`, {
    method: "POST",
    body: JSON.stringify({ raw_input: rawInput }),
  });
}
```

Also add the import at the top — update the import from `@/types` to include `ParseOrderResult` (and remove `ParsedOrderResponse` from the import if it's only used here — check first).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: update parseOrder return type to ParseOrderResult union"
```

### Task 11: Update `useParseOrder` hook to branch on response type

**Files:**
- Modify: `frontend/src/hooks/use-parse-order.ts`

- [ ] **Step 1: Update the hook to guard on `type`**

Replace `frontend/src/hooks/use-parse-order.ts`:

```typescript
import { useMutation } from "@tanstack/react-query";
import { parseOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";
import type { ParseOrderResult } from "@/types";

export function useParseOrder(slug: string) {
  const setParsedResult = useOrderStore((s) => s.setParsedResult);
  const setError = useOrderStore((s) => s.setError);

  return useMutation({
    mutationFn: (rawInput: string) => parseOrder(slug, rawInput),
    onSuccess: (result: ParseOrderResult) => {
      if (result.type === "order") {
        setParsedResult(result.items, result.allergies ?? [], result.total_price, result.language);
      }
      // For "recommendation" type, VoiceChatTab handles it via its own onSuccess
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to parse order");
    },
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/use-parse-order.ts
git commit -m "feat: guard useParseOrder onSuccess with type check for recommendations"
```

---

## Chunk 4: Frontend — RecommendationCard Component

### Task 12: Create the `RecommendationCard` component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/RecommendationCard.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/app/order/[slug]/components/RecommendationCard.tsx`:

```tsx
"use client";

import { useState } from "react";
import { ChevronRight, Plus, Minus, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ImageLightbox } from "@/components/image-lightbox";
import { cn } from "@/lib/utils";
import { useOrderStore } from "@/stores/order-store";
import type { RecommendationItem, MenuItemVariant, MenuItemModifier } from "@/types";

interface RecommendationCardProps {
  item: RecommendationItem;
}

export function RecommendationCard({ item }: RecommendationCardProps) {
  const addItemFromMenu = useOrderStore((s) => s.addItemFromMenu);

  const defaultVariant = item.variants.find((v) => v.is_default) || item.variants[0];
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedVariant, setSelectedVariant] = useState<MenuItemVariant>(defaultVariant);
  const [selectedModifiers, setSelectedModifiers] = useState<MenuItemModifier[]>([]);
  const [quantity, setQuantity] = useState(item.quantity);
  const [justAdded, setJustAdded] = useState(false);

  const toggleModifier = (mod: MenuItemModifier) => {
    setSelectedModifiers((prev) =>
      prev.some((m) => m.id === mod.id)
        ? prev.filter((m) => m.id !== mod.id)
        : [...prev, mod],
    );
  };

  const lineTotal = (
    (parseFloat(selectedVariant.price) +
      selectedModifiers.reduce((sum, m) => sum + parseFloat(m.price_adjustment), 0)) *
    quantity
  ).toFixed(2);

  const handleAddToCart = () => {
    const menuItem = {
      id: item.menu_item_id,
      name: item.name,
      description: item.description,
      image_url: item.image_url,
      variants: item.variants,
      modifiers: item.modifiers,
    };
    addItemFromMenu(menuItem, selectedVariant, selectedModifiers, quantity);
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 1200);
    setIsExpanded(false);
    // Reset for next add
    setQuantity(item.quantity);
    setSelectedModifiers([]);
    setSelectedVariant(defaultVariant);
  };

  return (
    <div className="glass-card rounded-xl overflow-hidden transition-all duration-200">
      {/* Collapsed row */}
      <button
        className="w-full flex items-center gap-3 p-4 text-left min-h-[56px]"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {item.image_url && (
          <img
            src={item.image_url}
            alt={item.name}
            className="w-12 h-12 rounded-lg object-cover shrink-0"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-medium text-foreground truncate">{item.name}</p>
            {item.quantity > 1 && (
              <span className="shrink-0 text-[10px] font-semibold text-primary bg-primary/10 rounded-full px-1.5 py-0.5">
                x{item.quantity}
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate mt-0.5">{item.reason}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-medium text-primary">${defaultVariant?.price}</span>
          {justAdded ? (
            <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
              <Check className="h-4 w-4 text-green-500" />
            </div>
          ) : (
            <ChevronRight
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform",
                isExpanded && "rotate-90",
              )}
            />
          )}
        </div>
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-border/50 pt-3 animate-fade-in-up">
          {/* Full image */}
          {item.image_url && (
            <ImageLightbox
              src={item.image_url}
              alt={item.name}
              className="w-full h-40 rounded-lg object-cover"
            />
          )}

          {/* Description */}
          {item.description && (
            <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
          )}

          {/* Recommendation reason */}
          <p className="text-xs text-muted-foreground italic">{item.reason}</p>

          {/* Variant selector */}
          {item.variants.length > 1 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">Size / Option</p>
              <div className="flex flex-wrap gap-2">
                {item.variants.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => setSelectedVariant(v)}
                    className={cn(
                      "rounded-full px-3 py-1.5 text-xs font-medium transition-colors min-h-[32px]",
                      selectedVariant.id === v.id
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground hover:bg-muted/80",
                    )}
                  >
                    {v.label} — ${v.price}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Modifier checkboxes */}
          {item.modifiers.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">Add-ons</p>
              <div className="space-y-2">
                {item.modifiers.map((mod) => {
                  const isSelected = selectedModifiers.some((m) => m.id === mod.id);
                  return (
                    <button
                      key={mod.id}
                      onClick={() => toggleModifier(mod)}
                      className={cn(
                        "w-full flex items-center justify-between rounded-lg px-3 py-2 text-xs transition-colors min-h-[40px]",
                        isSelected
                          ? "bg-primary/10 text-foreground"
                          : "bg-muted/50 text-muted-foreground hover:bg-muted/80",
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <div
                          className={cn(
                            "w-4 h-4 rounded border flex items-center justify-center",
                            isSelected
                              ? "bg-primary border-primary"
                              : "border-muted-foreground/30",
                          )}
                        >
                          {isSelected && <Check className="h-3 w-3 text-primary-foreground" />}
                        </div>
                        {mod.name}
                      </span>
                      <span className="text-primary">+${mod.price_adjustment}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Quantity + Add to Cart */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8 rounded-lg"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
              >
                <Minus className="h-3 w-3" />
              </Button>
              <span className="text-sm font-semibold w-6 text-center">{quantity}</span>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8 rounded-lg bg-primary/20 text-primary border-transparent hover:bg-primary/30"
                onClick={() => setQuantity((q) => q + 1)}
              >
                <Plus className="h-3 w-3" />
              </Button>
            </div>
            <Button
              variant="gradient"
              size="sm"
              className="glow-primary"
              onClick={handleAddToCart}
            >
              Add ${lineTotal}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors related to `RecommendationCard`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/order/[slug]/components/RecommendationCard.tsx
git commit -m "feat: add RecommendationCard component for voice chat recommendations"
```

---

## Chunk 5: Frontend — VoiceChatTab Integration

### Task 13: Update VoiceChatTab to render recommendations

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx`

- [ ] **Step 1: Add recommendation state and update handleSubmit**

In `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx`:

Add import at top:

```typescript
import { RecommendationCard } from "./RecommendationCard";
import type { RecommendationItem } from "@/types";
```

Add state for recommendations (after the existing state declarations, around line 23):

```typescript
const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
```

Update `handleSubmit` to clear recommendations on new submission and handle both response types. Replace the `onSuccess` callback in `parseOrderMutation.mutate(text, { ... })`:

```typescript
    setUnavailableItems([]);
    setRecommendations([]);
    parseOrderMutation.mutate(text, {
      onSuccess: (result) => {
        if (result.type === "recommendation") {
          setRecommendations(result.items);
          return;
        }
        // type === "order"
        if (result.items.length > 0) {
          const count = result.items.reduce((sum, i) => sum + i.quantity, 0);
          const names = result.items.map((i) => `${i.quantity}x ${i.name}`).join(", ");
          setAddedMessage(`Added ${names} (${count} item${count !== 1 ? "s" : ""})`);
          setTimeout(() => setAddedMessage(null), 3000);
        }
        if (result.unavailable_items && result.unavailable_items.length > 0) {
          setUnavailableItems(result.unavailable_items);
          setTimeout(() => setUnavailableItems([]), 5000);
        }
      },
    });
```

- [ ] **Step 2: Update loading text**

Change the loading message (around line 180):

```tsx
<p className="text-sm text-muted-foreground">Thinking...</p>
```

(Replace "Understanding your order...")

- [ ] **Step 3: Add recommendation cards rendering**

Add after the success confirmation section (after the unavailable items banner, around line 211), before the text input:

```tsx
      {/* Recommendation cards */}
      {recommendations.length > 0 && (
        <div className="w-full space-y-2 animate-fade-in-up">
          <p className="text-xs font-medium text-muted-foreground px-1">
            Recommended for you
          </p>
          {recommendations.map((item) => (
            <RecommendationCard key={item.menu_item_id} item={item} />
          ))}
        </div>
      )}
```

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/order/[slug]/components/VoiceChatTab.tsx
git commit -m "feat: render recommendation cards in VoiceChatTab"
```

---

## Chunk 6: Frontend — Owner Dashboard `is_featured` Toggle

### Task 14: Add `useToggleFeatured` hook

**Files:**
- Modify: `frontend/src/hooks/use-admin-menu.ts`

- [ ] **Step 1: Add `is_featured` to `MenuItemFull` interface and add `useToggleFeatured` hook**

In `frontend/src/hooks/use-admin-menu.ts`:

Update the `MenuItemFull` interface (line 18-28) to add `is_featured`:

```typescript
interface MenuItemFull {
  id: number;
  name: string;
  description: string;
  image_url: string;
  status: MenuItemStatus;
  is_upsellable: boolean;
  is_featured: boolean;
  sort_order: number;
  variants: Variant[];
  modifiers: Modifier[];
}
```

Add the hook after `useToggleUpsellable` (follows identical pattern):

```typescript
export function useToggleFeatured(slug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ itemId, is_featured }: { itemId: number; is_featured: boolean }) =>
      apiFetch(`/api/restaurants/${slug}/items/${itemId}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_featured }),
      }),
    onMutate: async ({ itemId, is_featured }) => {
      await queryClient.cancelQueries({ queryKey: ["admin-menu", slug] });
      const previous = queryClient.getQueryData<AdminMenu>(["admin-menu", slug]);
      if (previous) {
        queryClient.setQueryData<AdminMenu>(["admin-menu", slug], {
          ...previous,
          categories: previous.categories.map((cat) => ({
            ...cat,
            items: cat.items.map((item) =>
              item.id === itemId ? { ...item, is_featured } : item
            ),
          })),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["admin-menu", slug], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/use-admin-menu.ts
git commit -m "feat: add useToggleFeatured hook for owner dashboard"
```

### Task 15: Add `is_featured` toggle to menu management dashboard

**Files:**
- Modify: `frontend/src/app/account/restaurants/[slug]/menu/MenuManagementPageClient.tsx`

- [ ] **Step 1: Import and wire up the toggle**

Add `useToggleFeatured` to the imports (line 19):

```typescript
import {
  useAdminMenu,
  useAddCategory,
  useAddMenuItem,
  useDeleteMenuItem,
  useSetMenuItemStatus,
  useToggleUpsellable,
  useToggleFeatured,
  useUpdateMenuItem,
  useUpdateMenuItemImage,
} from "@/hooks/use-admin-menu";
```

Add the hook call after `toggleUpsellable` (around line 58):

```typescript
  const toggleFeatured = useToggleFeatured(params.slug);
```

- [ ] **Step 2: Add the Featured checkbox next to the Upsellable checkbox**

Find the Upsellable checkbox block (around line 435-458). Add a Featured checkbox right after it, following the same pattern:

```tsx
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="flex items-center gap-1.5">
                                <Checkbox
                                  id={`featured-${item.id}`}
                                  checked={item.is_featured}
                                  onCheckedChange={(checked) =>
                                    toggleFeatured.mutate({
                                      itemId: item.id,
                                      is_featured: checked === true,
                                    })
                                  }
                                />
                                <Label
                                  htmlFor={`featured-${item.id}`}
                                  className="text-xs text-muted-foreground cursor-pointer"
                                >
                                  Featured
                                </Label>
                              </div>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Featured items are prioritized in AI recommendations.</p>
                            </TooltipContent>
                          </Tooltip>
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/account/restaurants/[slug]/menu/MenuManagementPageClient.tsx
git commit -m "feat: add Featured toggle to menu management dashboard"
```

### Task 16: Add `is_featured` to `MenuItem` frontend type

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add `is_featured` to the `MenuItem` interface**

In `frontend/src/types/index.ts`, update `MenuItem` (line 78-86):

```typescript
export interface MenuItem {
  id: number;
  name: string;
  description: string;
  image_url: string;
  is_sold_out?: boolean;
  is_featured?: boolean;
  variants: MenuItemVariant[];
  modifiers: MenuItemModifier[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add is_featured to MenuItem frontend type"
```

### Task 17: Add `is_featured` to `ParsedMenuItem` type and `ParsedMenuEditor`

**Files:**
- Modify: `frontend/src/types/index.ts:227-232` (ParsedMenuItem)
- Modify: `frontend/src/components/parsed-menu-editor.tsx`

- [ ] **Step 1: Add `is_featured` to the `ParsedMenuItem` type**

In `frontend/src/types/index.ts`, update `ParsedMenuItem`:

```typescript
export interface ParsedMenuItem {
  name: string;
  description: string | null;
  image_url: string | null;
  is_featured?: boolean;
  variants: ParsedMenuVariant[];
}
```

- [ ] **Step 2: Add a Featured checkbox to each item in `ParsedMenuEditor`**

In `frontend/src/components/parsed-menu-editor.tsx`, add a "Featured" checkbox for each item. Find the area where each item's name/description inputs are rendered (inside the item mapping loop). Add after the description input:

```tsx
<div className="flex items-center gap-2 mt-1">
  <input
    type="checkbox"
    id={`featured-${catIndex}-${itemIndex}`}
    checked={item.is_featured ?? false}
    onChange={(e) =>
      updateItem(catIndex, itemIndex, { is_featured: e.target.checked })
    }
    className="h-3.5 w-3.5 rounded border-muted-foreground/30"
  />
  <label
    htmlFor={`featured-${catIndex}-${itemIndex}`}
    className="text-xs text-muted-foreground cursor-pointer"
  >
    Featured
  </label>
</div>
```

- [ ] **Step 3: Verify it compiles**

Run: `cd frontend && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/parsed-menu-editor.tsx
git commit -m "feat: add is_featured to ParsedMenuEditor for AI-uploaded menus"
```

---

## Chunk 7: Manual QA and Final Verification

### Task 18: End-to-end manual testing

- [ ] **Step 1: Start the backend dev server**

Run: `cd backend && python manage.py runserver`

- [ ] **Step 2: Start the frontend dev server**

Run: `cd frontend && npm run dev`

- [ ] **Step 3: Test order flow (regression)**

Open `http://localhost:3001/order/<slug>`. Say or type "I'll have the pad thai." Verify items are added to cart as before.

- [ ] **Step 4: Test recommendation flow**

On the same page, say or type "What's popular here?" Verify:
- Loading shows "Thinking..."
- Recommendation cards appear (collapsed rows with thumbnail, name, price, reason)
- Tapping a card expands it to show full image, description, variant/modifier pickers, quantity
- Quantity pre-fills correctly
- "Add to Cart" button works and shows green checkmark

- [ ] **Step 5: Test group recommendation**

Say or type "Food for 4 people." Verify:
- Cards appear with quantities > 1 on some items
- Quantity badge shows (e.g., "x2")

- [ ] **Step 6: Test owner Featured toggle**

Go to `http://localhost:3001/account/restaurants/<slug>/menu`. Find a menu item and toggle the "Featured" checkbox. Verify it saves (page does not need refresh — optimistic update).

- [ ] **Step 7: Test guest vs authenticated recommendations**

Log out and try "What's popular?" as a guest — should still show recommendations (no dietary filtering). Log in (with dietary preferences set in profile) and try again — recommendations should respect allergies.

- [ ] **Step 8: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address issues found during manual QA"
```
