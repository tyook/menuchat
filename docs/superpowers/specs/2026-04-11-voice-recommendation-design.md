# Voice-Based Menu Recommendation Agent

**Date:** 2026-04-11
**Status:** Approved

## Overview

Enable the voice ordering agent to detect recommendation requests and respond with browsable, actionable menu item cards inline in the chat UI. When a user asks "what's popular?", "recommend something spicy", or "food for 4 people", the agent returns up to 3 recommended menu items displayed as expandable cards with full detail, variant/modifier pickers, and add-to-cart functionality.

## Goals

- Users can ask for recommendations via voice or text in the same flow they use for ordering
- Recommendations are personalized based on the logged-in user's dietary preferences and allergies (from their profile)
- Guest users receive unfiltered recommendations based on menu data (featured items, descriptions)
- Restaurant owners can mark items as "Featured" to influence recommendations
- Users can review recommended items (image, description, price, variants, modifiers) and add them to cart individually

## Non-Goals

- No TTS/spoken response — visual cards only
- No conversational follow-ups — each request is stateless and independent
- No persistent preference extraction from conversation — profile data only
- No order-count-based popularity analytics (future enhancement)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Intent detection | LLM-based, inside the agent | More accurate than keyword matching; single round-trip |
| Response display | Inline expandable cards (Option C) | Compact browsing + full detail on tap; matches existing MenuItemCard pattern |
| Profile source | Server-side User model (`dietary_preferences`, `allergies`) | Already exists at `/api/auth/me/`; no frontend extraction needed |
| Guest handling | No dietary filtering, recommend from menu data | Agent never asks the user questions; simplest UX |
| Featured items | Owner-controlled `is_featured` boolean on MenuItem | Simple, no analytics dependency; owner controls narrative |
| Quantity support | Agent sets `quantity` per recommendation | Handles "food for N people" requests; pre-fills quantity picker |
| Architecture | Extend existing agent + endpoint (Approach A) | Minimal new infrastructure; one agent, one endpoint, one round-trip |

## Architecture

### Backend

#### 1. Unified Agent (`OrderAgent`)

Replaces `OrderParsingAgent`. Same agent handles both order parsing and recommendation detection based on user intent.

**Instructions cover:**
- Order parsing (existing rules, unchanged)
- Recommendation detection: when user asks for suggestions, popular items, or help choosing
- "Auto-order" style requests ("food for 4 people") treated as recommendations with appropriate quantities

**Response model:**

```python
# backend/orders/llm/base.py

class AgentResponse(BaseModel):
    intent: Literal["order", "recommendation"]
    
    # Populated when intent == "order"
    order: ParsedOrder | None = None
    
    # Populated when intent == "recommendation"
    recommendations: list[RecommendedItem] | None = None
```

The `RecommendedItem` schema gains a `quantity` field (default 1).

#### 2. `is_featured` on MenuItem

```python
# backend/restaurants/models.py - MenuItem
is_featured = models.BooleanField(default=False)
```

- New migration adding the boolean column with `default=False`
- Follows the same pattern as the existing `is_upsellable` field

#### 3. Menu Context Enhancement

`build_menu_context()` adds a `[FEATURED]` marker to featured items, following the existing `[SOLD OUT]` and `[UPSELLABLE]` marker pattern:

```
  - Pad Thai (item_id: 42) [FEATURED]
    Description: Classic stir-fried rice noodles...
```

#### 4. Service Layer Flow

`OrderService.parse_order()` is modified:

1. Calls unified `OrderAgent` (instead of `OrderParsingAgent`)
2. Checks `agent_response.intent`
3. If `"order"` — existing `validate_and_price_order()` flow, unchanged
4. If `"recommendation"` — calls `RecommendationService.get_recommendations()` with user's profile data, returns enriched recommendation items

The view layer passes `request.user` to `parse_order()` so the service can access `user.dietary_preferences` and `user.allergies`.

#### 5. Recommendation Service Enhancement

`RecommendationService.get_recommendations()` is enriched to return:
- All variants for each recommended item (not just the default)
- All modifiers for each recommended item
- The `is_featured` flag
- Agent-suggested `quantity`

This gives the frontend everything it needs to render the full expandable card without extra API calls.

### API Response Shape

Same endpoint: `POST /api/orders/{slug}/parse/`

**Response when intent is "order"** (existing shape + `type` discriminator):

```json
{
  "type": "order",
  "items": [...],
  "unavailable_items": [...],
  "allergies": [...],
  "total_price": "24.99",
  "language": "en"
}
```

**Response when intent is "recommendation":**

```json
{
  "type": "recommendation",
  "items": [
    {
      "menu_item_id": 42,
      "name": "Pad Thai",
      "description": "Classic stir-fried rice noodles with shrimp...",
      "image_url": "https://...",
      "variant_id": 101,
      "variant_label": "Regular",
      "variant_price": "14.99",
      "quantity": 2,
      "reason": "Our most popular dish — great for sharing",
      "is_featured": true,
      "modifiers": [
        { "id": 5, "name": "Extra Shrimp", "price_adjustment": "3.00" }
      ],
      "variants": [
        { "id": 101, "label": "Regular", "price": "14.99", "is_default": true },
        { "id": 102, "label": "Large", "price": "18.99", "is_default": false }
      ]
    }
  ]
}
```

### Frontend

#### 1. `useParseOrder` Hook

Updated to handle both response types:
- If `type === "order"` — existing flow: call `setParsedResult()`, show "Added X items" confirmation
- If `type === "recommendation"` — return recommendations for the component to render (not added to order store)

#### 2. VoiceChatTab Recommendation Cards

Recommendations are stored in `useState` local to `VoiceChatTab` (transient UI state).

**Collapsed card (per item):**
- Thumbnail image (50x50), item name, price, short reason, chevron indicator
- If `quantity > 1`, show quantity badge (e.g., "x2")

**Expanded card (tap to expand in-place):**
- Full-size image (tappable for lightbox via existing `ImageLightbox` component)
- Full description text
- Recommendation reason (italic)
- Variant picker (radio pills — same pattern as `MenuItemCard`)
- Modifier checkboxes with price adjustments (same pattern as `MenuItemCard`)
- Quantity picker (pre-filled with agent's suggested quantity)
- "Add to Cart — $X.XX" button

**Add to Cart:** Calls existing `addItemFromMenu()` on the order store. After adding, the card shows a green checkmark for 1.2s (same feedback pattern as `MenuItemCard`).

**Lifecycle:** Recommendation cards persist until the user submits a new voice/text input. A new submission (whether order or recommendation) replaces the previous cards.

**Loading state:** The existing dot-pulse animation shows "Thinking..." instead of "Understanding your order..." (since the input could trigger either flow).

#### 3. Owner Dashboard — `is_featured` Toggle

A toggle/switch labeled "Featured" in the menu item editor within `MenuManagementPageClient.tsx`. Follows the same pattern as existing boolean toggles in the dashboard.

The `ParsedMenuEditor` (for AI-uploaded menus) also accepts `is_featured`.

Data flows through existing menu CRUD endpoints — no new endpoint needed.

## Data Flow

```
User speaks/types "What's popular here?"
    |
    v
VoiceChatTab → useParseOrder → POST /api/orders/{slug}/parse/
    |
    v
View: passes request.user + raw_input to OrderService.parse_order()
    |
    v
OrderService: builds menu context → calls OrderAgent
    |
    v
OrderAgent: detects recommendation intent → returns AgentResponse(intent="recommendation", recommendations=[...])
    |
    v
OrderService: calls RecommendationService.get_recommendations() with user profile
    |
    v
RecommendationService: builds preferences context from user.dietary_preferences + user.allergies
    → runs RecommendationAgent with menu context + preferences + order history
    → validates items against DB, enriches with all variants/modifiers
    → returns recommendation items
    |
    v
View: returns { type: "recommendation", items: [...] }
    |
    v
useParseOrder: detects type === "recommendation", returns data (does NOT call setParsedResult)
    |
    v
VoiceChatTab: stores recommendations in local useState, renders expandable cards
    |
    v
User taps card → expands → selects variant/modifiers/quantity → taps "Add to Cart"
    |
    v
addItemFromMenu() on order store (existing cart logic)
```

## Files Changed

### Backend
| File | Change |
|------|--------|
| `backend/restaurants/models.py` | Add `is_featured` boolean field to `MenuItem` |
| `backend/restaurants/migrations/XXXX_menu_item_is_featured.py` | New migration |
| `backend/orders/llm/base.py` | Add `AgentResponse` union model with `intent` discriminator |
| `backend/orders/llm/agent.py` | Rename to `OrderAgent`, expand instructions for recommendation detection |
| `backend/orders/llm/menu_context.py` | Add `[FEATURED]` marker for featured items |
| `backend/orders/llm/recommendation_schemas.py` | Add `quantity` field to `RecommendedItem` |
| `backend/orders/recommendation_service.py` | Enrich response with all variants, modifiers, `is_featured` |
| `backend/orders/services.py` | `parse_order()` handles both intents, passes `user` for profile data |
| `backend/restaurants/serializers/restaurant_serializers.py` | Expose `is_featured` in `PublicMenuItemSerializer` |
| `backend/restaurants/serializers/menu_upload_serializers.py` | Accept `is_featured` in menu upload |
| `backend/restaurants/views.py` | Pass `is_featured` through menu item CRUD |

### Frontend
| File | Change |
|------|--------|
| `frontend/src/types/index.ts` | Add `RecommendationItem` type, update `ParsedOrderResponse` to union |
| `frontend/src/hooks/use-parse-order.ts` | Handle both `type: "order"` and `type: "recommendation"` |
| `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx` | Add recommendation card rendering (collapsed + expanded) |
| `frontend/src/app/order/[slug]/components/RecommendationCard.tsx` | New component for expandable recommendation card |
| `frontend/src/app/account/restaurants/[slug]/menu/MenuManagementPageClient.tsx` | Add `is_featured` toggle |
| `frontend/src/components/parsed-menu-editor.tsx` | Accept `is_featured` field |
| `frontend/src/lib/api.ts` | Update `parseOrder` return type |

## Testing

### Backend
- Agent intent detection — mock agent, verify `"recommendation"` intent for recommendation-style inputs and `"order"` for order-style inputs
- Recommendation with profile — verify dietary preferences and allergies from user model are passed and respected
- Recommendation without profile (guest) — verify unfiltered results returned
- `is_featured` in menu context — verify `[FEATURED]` marker appears in context string
- Response shape — verify `type` discriminator and correct field population for both intents
- Quantity in recommendations — verify "food for N people" style returns quantities > 1

### Frontend
- RecommendationCard renders collapsed and expanded states correctly
- "Add to Cart" from recommendation card calls `addItemFromMenu` with correct data
- `useParseOrder` handles both response types without error
- Variant/modifier selection updates the "Add to Cart" price correctly

### Manual QA
- Voice input: "What's popular?" → shows recommendation cards
- Voice input: "I'll have the pad thai" → adds to cart (existing flow)
- Voice input: "Food for 4 people" → shows recommendations with quantities > 1
- Guest user: recommendations appear without dietary filtering
- Logged-in user with allergies: conflicting items excluded
- Owner toggles "Featured" on items → agent recommends them
