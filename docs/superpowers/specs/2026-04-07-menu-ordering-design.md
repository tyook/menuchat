# Menu Ordering Design

**Date:** 2026-04-07
**Status:** Approved

## Problem

Currently, the only way customers can order food is via voice/chat input, which gets parsed by an LLM. Customers should also be able to browse the menu and add items directly — a familiar, deterministic ordering flow that complements the AI-powered voice/chat.

## Decisions

| Decision | Choice |
|---|---|
| Menu + chat coexistence | Side by side, shared cart |
| Layout | Tabbed view (Menu / Voice/Chat tabs) |
| Variant/modifier selection | Inline expansion (no modal) |
| Category navigation | Sticky horizontal pill bar |
| Cart visibility | Always-visible bottom bar |
| Implementation approach | Extend existing order page |
| Mobile strategy | `100dvh`, safe-area insets, 44px touch targets, scroll containment |

## Architecture

### Page Flow Change

The existing step flow changes from:

```
welcome → input → loading → cart → payment → submitted
```

To:

```
welcome → ordering → cart → payment → submitted
```

The new `ordering` step contains two tabs:
- **Menu tab** → `MenuBrowseTab` component (new)
- **Voice/Chat tab** → `VoiceChatTab` component (refactored from existing `InputStep`)

Both tabs add items to the same `useOrderStore`. Tapping "Review Order" in the bottom bar transitions to the existing `ConfirmationStep` (cart).

### No Backend Changes

The existing `ConfirmOrderView` and `CreatePaymentView` already accept structured items. They don't care whether items came from LLM parsing or manual menu selection. The existing `GET /api/order/{slug}/menu/` endpoint provides all the data needed for menu browsing.

## New Components

### MenuBrowseTab

Layout (top to bottom within the ordering step):

1. **Tab bar** — "Menu" | "Voice/Chat" toggle, below restaurant name
2. **Category pills** — Sticky horizontal scroll bar with snap scrolling. Highlights active category based on scroll position via `IntersectionObserver`. Tapping scrolls to section. Note: programmatic scroll (from pill tap) must suppress the `IntersectionObserver` callback via a ref flag to prevent pill highlight flickering during scroll animation.
3. **Menu items list** — Scrollable area taking remaining viewport height. Grouped by category with section headers.
4. **Cart bottom bar** — Fixed to bottom. Shows item count, total price, "Review Order" button. Always visible, greyed out when empty.

#### Menu Item Card (Collapsed)

- Item name (left), price (right)
- Description below name (truncated to 1 line)
- Image thumbnail if `image_url` exists (small, right-aligned)
- "+ Add" button on the right

#### Menu Item Card (Expanded — after tapping item with variants/modifiers)

- Full description
- Variant selector: radio-style pills (e.g., `Small ○ | Medium ● | Large ○`)
- Modifier checkboxes (e.g., `☐ Extra cheese +$1.50`)
- Quantity selector: `[ - ] 1 [ + ]`
- "Add to Cart" button
- Tapping another item or tapping again collapses it

#### Data Flow

- Uses existing `useMenu(slug)` hook to fetch menu data
- On "Add to Cart": creates a `ParsedOrderItem` and calls `addItemFromMenu()` on `useOrderStore`
- No backend call needed — item data comes directly from the menu response
- Price formula: `line_total = (variant.price + sum(selected_modifier.price_adjustment)) * quantity` — validated server-side on confirm

### VoiceChatTab

Refactored from existing `InputStep` to work as a tab:

- Same mic orb, textarea fallback, `useParseOrder` hook
- When LLM returns parsed items, they get added to `useOrderStore` via `addItem()`
- The store's `setParsedResult` already merges new items with existing ones (additive behavior). The key change is: **do not transition to cart step after parsing**. The `useParseOrder` hook's `onSuccess` currently calls `setStep("cart")` — this must be modified to stay on the `ordering` step and show inline confirmation instead.
- Shows brief inline confirmation: "Added 2x Margherita, 1x Carbonara" with checkmarks
- Input clears, ready for another voice/text entry
- Loading state during LLM parsing shown as an **inline spinner/animation within the VoiceChatTab** (replaces the standalone `LoadingStep` component which is no longer needed)

## Store Changes

### useOrderStore Extensions

1. **`addItemFromMenu(item, variant, modifiers, quantity)`** — New action that creates a `ParsedOrderItem` from menu data directly (no LLM). Maps `MenuItem` + `MenuItemVariant` + `MenuItemModifier[]` into the same shape that `parseOrder` returns.

2. **Step enum change** — New `'ordering'` value replaces the `'input'` → `'loading'` transition. Flow: `welcome → ordering → cart → payment → submitted`.

**UI state (`activeTab`, `expandedItemId`) stays in local `useState`** within `OrderingStep`, not in the Zustand store. These are UI-only concerns and tab content is preserved in DOM (not unmounted), so local state is sufficient.

## Mobile-First Layout Strategy

### Viewport

- Use `100dvh` (dynamic viewport height) instead of `100vh` — handles mobile browser chrome
- Add `viewport-fit=cover` to viewport meta tag for edge-to-edge rendering on notched devices
- Safe-area padding: `pb-[env(safe-area-inset-bottom)]` on cart bottom bar

### Touch Targets

- All tappable elements minimum 44px height (Apple HIG / Material guidelines)
- Category pills: 36px+ height with generous horizontal padding
- "+ Add" buttons: large enough tap area, not crammed next to other actions
- No hover-dependent interactions — everything works on tap

### Scrolling

- Outer container fixed (`h-[100dvh]`, `overflow: hidden`)
- Menu items area is the only scrollable zone (`overflow-y: auto`, `-webkit-overflow-scrolling: touch`)
- Category bar and cart bottom bar stay fixed — no scroll jank
- `IntersectionObserver` on category headers to update active pill as user scrolls

### Performance

- Menu items rendered as flat list (menus typically <100 items, no virtualization needed)
- Images lazy-loaded with `loading="lazy"` and fixed aspect ratio to prevent layout shift
- Tab content preserved in DOM when switching (not unmounted) to keep scroll position

### Keyboard Handling

- On mobile, when keyboard opens the viewport shrinks. Text input stays above keyboard naturally with `100dvh` + fixed bottom positioning
- No special keyboard avoidance needed

## Files to Modify

### New Files
- `frontend/src/app/order/[slug]/components/MenuBrowseTab.tsx`
- `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx`
- `frontend/src/app/order/[slug]/components/CategoryBar.tsx`
- `frontend/src/app/order/[slug]/components/MenuItemCard.tsx`
- `frontend/src/app/order/[slug]/components/CartBottomBar.tsx`
- `frontend/src/app/order/[slug]/components/OrderingStep.tsx`

### Modified Files
- `frontend/src/stores/order-store.ts` — new `addItemFromMenu` action, add `'ordering'` to step enum
- `frontend/src/hooks/use-parse-order.ts` — remove `setStep("cart")` from `onSuccess`, stay on `ordering` step
- `frontend/src/app/order/[slug]/page.tsx` — render `OrderingStep` for the `ordering` step, remove `MenuModal` (now redundant)
- `frontend/src/app/order/[slug]/components/WelcomeStep.tsx` — transition to `ordering` instead of `input`

### Deprecated Files
- `frontend/src/app/order/[slug]/components/InputStep.tsx` — replaced by `VoiceChatTab`
- `frontend/src/app/order/[slug]/components/LoadingStep.tsx` — loading state now inline within `VoiceChatTab`
- `frontend/src/app/order/[slug]/components/MenuModal.tsx` — replaced by `MenuBrowseTab`

### Cart Bottom Bar Behavior
- Always visible at the bottom of the ordering step
- When cart is empty: shows "Review Order" button in disabled/muted state (non-interactive), displays "$0.00"
- When cart has items: shows item count, total price, and enabled "Review Order" button
