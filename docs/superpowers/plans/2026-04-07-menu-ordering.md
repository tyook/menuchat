# Menu Ordering Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a menu browsing UI so customers can tap to add items directly, alongside the existing voice/chat ordering.

**Architecture:** Extend the existing `/order/[slug]` page with a new `ordering` step containing tabbed Menu/Voice views. Both tabs feed into the same Zustand order store and shared cart. No backend changes needed.

**Tech Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Zustand, React Query, Lucide icons

**Spec:** `docs/superpowers/specs/2026-04-07-menu-ordering-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/app/order/[slug]/components/OrderingStep.tsx` | Tab container (Menu / Voice tabs), manages `activeTab` state, renders both tabs and CartBottomBar |
| `frontend/src/app/order/[slug]/components/MenuBrowseTab.tsx` | Full menu browsing with category bar, item list, inline expansion for variants/modifiers |
| `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx` | Refactored voice/text input from InputStep, with inline loading and confirmation |
| `frontend/src/app/order/[slug]/components/CategoryBar.tsx` | Sticky horizontal scrollable category pills with IntersectionObserver sync |
| `frontend/src/app/order/[slug]/components/MenuItemCard.tsx` | Single menu item: collapsed view + expandable variant/modifier/quantity selection |
| `frontend/src/app/order/[slug]/components/CartBottomBar.tsx` | Fixed bottom bar showing item count, total, and "Review Order" button |

### Modified Files
| File | Changes |
|------|---------|
| `frontend/src/stores/order-store.ts` | Add `'ordering'` to `OrderStep` type, add `addItemFromMenu()` action |
| `frontend/src/hooks/use-parse-order.ts` | Remove `setStep("cart")` from onSuccess, change onError fallback to `"ordering"` |
| `frontend/src/app/order/[slug]/page.tsx` | Import `OrderingStep`, render for `step === "ordering"`, remove `MenuModal`/`InputStep`/`LoadingStep` imports |
| `frontend/src/app/order/[slug]/components/WelcomeStep.tsx` | Change `setStep("input")` to `setStep("ordering")` |
| `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx` | Change `setStep("input")` to `setStep("ordering")` in "Go Back" and "Add More" buttons |
| `frontend/src/app/layout.tsx` | Add `viewport-fit=cover` to viewport metadata |

### Deprecated (no longer imported, can delete later)
| File | Reason |
|------|--------|
| `frontend/src/app/order/[slug]/components/InputStep.tsx` | Replaced by VoiceChatTab |
| `frontend/src/app/order/[slug]/components/LoadingStep.tsx` | Loading now inline in VoiceChatTab |
| `frontend/src/app/order/[slug]/components/MenuModal.tsx` | Replaced by MenuBrowseTab |

---

## Chunk 1: Store & Hook Changes

### Task 1: Update OrderStep type and add addItemFromMenu action

**Files:**
- Modify: `frontend/src/stores/order-store.ts`

- [ ] **Step 1: Update the OrderStep type**

In `frontend/src/stores/order-store.ts`, change line 3:

```typescript
// Before:
type OrderStep = "welcome" | "input" | "loading" | "cart" | "payment" | "submitted";

// After (keep "input" | "loading" temporarily so existing consumers compile):
type OrderStep = "welcome" | "ordering" | "input" | "loading" | "cart" | "payment" | "submitted";
```

- [ ] **Step 2: Add addItemFromMenu to the interface and implementation**

Add to the `OrderState` interface after `addItem`:

```typescript
addItemFromMenu: (
  item: MenuItem,
  variant: MenuItemVariant,
  modifiers: MenuItemModifier[],
  quantity: number,
) => void;
```

Add the import at the top:

```typescript
import type { ParsedOrderItem, MenuItem, MenuItemVariant, MenuItemModifier } from "@/types";
```

Add the implementation inside `create<OrderState>`, after the `addItem` action:

```typescript
addItemFromMenu: (menuItem, variant, modifiers, quantity) =>
  set((state) => {
    const lineTotal = (
      (parseFloat(variant.price) +
        modifiers.reduce((sum, m) => sum + parseFloat(m.price_adjustment), 0)) *
      quantity
    ).toFixed(2);
    const newItem: ParsedOrderItem = {
      menu_item_id: menuItem.id,
      name: menuItem.name,
      variant: { id: variant.id, label: variant.label, price: variant.price },
      quantity,
      modifiers,
      special_requests: "",
      line_total: lineTotal,
    };
    const newItems = [...state.parsedItems, newItem];
    const newTotal = newItems
      .reduce((sum, i) => sum + parseFloat(i.line_total), 0)
      .toFixed(2);
    return { parsedItems: newItems, totalPrice: newTotal };
  }),
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -30`

Expected: Clean build — `"input"` and `"loading"` are kept temporarily in the union so existing consumers still compile.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/order-store.ts
git commit -m "feat(store): add ordering step and addItemFromMenu action"
```

---

### Task 2: Update useParseOrder hook

**Files:**
- Modify: `frontend/src/hooks/use-parse-order.ts`

- [ ] **Step 1: Remove step transitions from the hook**

Replace the full content of `frontend/src/hooks/use-parse-order.ts`:

```typescript
import { useMutation } from "@tanstack/react-query";
import { parseOrder } from "@/lib/api";
import { useOrderStore } from "@/stores/order-store";

export function useParseOrder(slug: string) {
  const setParsedResult = useOrderStore((s) => s.setParsedResult);
  const setError = useOrderStore((s) => s.setError);

  return useMutation({
    mutationFn: (rawInput: string) => parseOrder(slug, rawInput),
    onSuccess: (result) => {
      setParsedResult(result.items, result.allergies ?? [], result.total_price, result.language);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Failed to parse order");
    },
  });
}
```

Key changes: removed `setStep` import and both `setStep("cart")` (onSuccess) and `setStep("input")` (onError) calls. The VoiceChatTab will handle its own UI state for loading/confirmation.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep use-parse-order`

Expected: No errors in this file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-parse-order.ts
git commit -m "refactor(hooks): remove step transitions from useParseOrder

VoiceChatTab will manage its own loading/confirmation UI inline."
```

---

### Task 3: Update WelcomeStep and ConfirmationStep references

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`
- Modify: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`

- [ ] **Step 1: Update WelcomeStep**

In `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`, change `setStep("input")` to `setStep("ordering")` (line 40).

- [ ] **Step 2: Update ConfirmationStep**

In `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`, change both occurrences of `setStep("input")` to `setStep("ordering")`:
- Line 113: the "Go Back" button in the empty-items case
- Line 238: the "Add More" button

- [ ] **Step 3: Verify TypeScript compiles for these files**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -E "(WelcomeStep|ConfirmationStep)"`

Expected: No errors in these files.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/WelcomeStep.tsx" "frontend/src/app/order/[slug]/components/ConfirmationStep.tsx"
git commit -m "refactor: update step references from input to ordering"
```

---

## Chunk 2: New Components — CartBottomBar, CategoryBar, MenuItemCard

### Task 4: Create CartBottomBar component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/CartBottomBar.tsx`

- [ ] **Step 1: Create the CartBottomBar component**

Write `frontend/src/app/order/[slug]/components/CartBottomBar.tsx`:

```tsx
"use client";

import { ShoppingCart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useOrderStore } from "@/stores/order-store";

export function CartBottomBar() {
  const parsedItems = useOrderStore((s) => s.parsedItems);
  const totalPrice = useOrderStore((s) => s.totalPrice);
  const setStep = useOrderStore((s) => s.setStep);

  const itemCount = parsedItems.reduce((sum, item) => sum + item.quantity, 0);
  const hasItems = itemCount > 0;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur-sm"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <ShoppingCart className="h-5 w-5 text-muted-foreground shrink-0" />
          <span className="text-sm text-muted-foreground truncate">
            {hasItems
              ? `${itemCount} item${itemCount !== 1 ? "s" : ""}`
              : "Cart is empty"}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm font-semibold text-foreground">
            ${totalPrice}
          </span>
          <Button
            variant="gradient"
            size="sm"
            className={hasItems ? "glow-primary" : ""}
            disabled={!hasItems}
            onClick={() => setStep("cart")}
          >
            Review Order
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep CartBottomBar`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/CartBottomBar.tsx"
git commit -m "feat: add CartBottomBar component

Fixed bottom bar showing item count, total, and Review Order button.
Disabled when cart is empty. Uses safe-area-inset-bottom for notched devices."
```

---

### Task 5: Create CategoryBar component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/CategoryBar.tsx`

- [ ] **Step 1: Create the CategoryBar component**

Write `frontend/src/app/order/[slug]/components/CategoryBar.tsx`:

```tsx
"use client";

import { useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

interface CategoryBarProps {
  categories: { id: number; name: string }[];
  activeCategoryId: number | null;
  onCategoryClick: (categoryId: number) => void;
}

export function CategoryBar({
  categories,
  activeCategoryId,
  onCategoryClick,
}: CategoryBarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pillRefs = useRef<Map<number, HTMLButtonElement>>(new Map());

  // Scroll the active pill into view
  useEffect(() => {
    if (activeCategoryId == null) return;
    const pill = pillRefs.current.get(activeCategoryId);
    if (pill && scrollRef.current) {
      pill.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }, [activeCategoryId]);

  const setPillRef = useCallback(
    (id: number) => (el: HTMLButtonElement | null) => {
      if (el) pillRefs.current.set(id, el);
      else pillRefs.current.delete(id);
    },
    [],
  );

  return (
    <div
      ref={scrollRef}
      className="flex gap-2 overflow-x-auto scrollbar-hide py-2 px-4 -mx-4"
      style={{ WebkitOverflowScrolling: "touch", scrollSnapType: "x mandatory" }}
    >
      {categories.map((cat) => (
        <button
          key={cat.id}
          ref={setPillRef(cat.id)}
          onClick={() => onCategoryClick(cat.id)}
          className={cn(
            "shrink-0 rounded-full px-4 py-2 text-sm font-medium transition-colors min-h-[36px]",
            "snap-start",
            activeCategoryId === cat.id
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:bg-muted/80",
          )}
        >
          {cat.name}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep CategoryBar`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/CategoryBar.tsx"
git commit -m "feat: add CategoryBar component

Horizontal scrollable category pills with active state highlighting.
Auto-scrolls active pill into view."
```

---

### Task 6: Create MenuItemCard component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/MenuItemCard.tsx`

- [ ] **Step 1: Create the MenuItemCard component**

Write `frontend/src/app/order/[slug]/components/MenuItemCard.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Plus, Minus, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useOrderStore } from "@/stores/order-store";
import type { MenuItem, MenuItemVariant, MenuItemModifier } from "@/types";

interface MenuItemCardProps {
  item: MenuItem;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

export function MenuItemCard({ item, isExpanded, onToggleExpand }: MenuItemCardProps) {
  const addItemFromMenu = useOrderStore((s) => s.addItemFromMenu);
  const defaultVariant = item.variants.find((v) => v.is_default) || item.variants[0];

  const [selectedVariant, setSelectedVariant] = useState<MenuItemVariant>(defaultVariant);
  const [selectedModifiers, setSelectedModifiers] = useState<MenuItemModifier[]>([]);
  const [quantity, setQuantity] = useState(1);
  const [justAdded, setJustAdded] = useState(false);

  const hasOptions = item.variants.length > 1 || item.modifiers.length > 0;

  const handleQuickAdd = () => {
    if (hasOptions) {
      onToggleExpand();
      return;
    }
    addItemFromMenu(item, defaultVariant, [], 1);
    showAddedFeedback();
  };

  const handleAddToCart = () => {
    addItemFromMenu(item, selectedVariant, selectedModifiers, quantity);
    showAddedFeedback();
    // Reset for next add
    setQuantity(1);
    setSelectedModifiers([]);
    setSelectedVariant(defaultVariant);
    onToggleExpand();
  };

  const showAddedFeedback = () => {
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 1200);
  };

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

  return (
    <div className="glass-card rounded-xl overflow-hidden transition-all duration-200">
      {/* Collapsed row */}
      <button
        className="w-full flex items-center gap-3 p-4 text-left min-h-[56px]"
        onClick={hasOptions ? onToggleExpand : handleQuickAdd}
      >
        {item.image_url && (
          <img
            src={item.image_url}
            alt={item.name}
            loading="lazy"
            className="w-12 h-12 rounded-lg object-cover shrink-0"
          />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{item.name}</p>
          {item.description && (
            <p className="text-xs text-muted-foreground truncate">{item.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-medium text-primary">
            ${defaultVariant?.price}
          </span>
          {justAdded ? (
            <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
              <Check className="h-4 w-4 text-green-500" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
              <Plus className="h-4 w-4 text-primary" />
            </div>
          )}
        </div>
      </button>

      {/* Expanded options */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-border/50 pt-3 animate-fade-in-up">
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

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep MenuItemCard`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/MenuItemCard.tsx"
git commit -m "feat: add MenuItemCard component

Collapsed view with name/price/add button. Expands inline for
variant selection, modifier checkboxes, and quantity picker.
Quick-add for items with no options."
```

---

## Chunk 3: Tab Components and Page Integration

### Task 7: Create MenuBrowseTab component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/MenuBrowseTab.tsx`

- [ ] **Step 1: Create the MenuBrowseTab component**

Write `frontend/src/app/order/[slug]/components/MenuBrowseTab.tsx`:

```tsx
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { CategoryBar } from "./CategoryBar";
import { MenuItemCard } from "./MenuItemCard";
import type { MenuCategory } from "@/types";

interface MenuBrowseTabProps {
  categories: MenuCategory[];
}

export function MenuBrowseTab({ categories }: MenuBrowseTabProps) {
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(
    categories[0]?.id ?? null,
  );
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
  const suppressObserverRef = useRef(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const categoryRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const suppressTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const setCategoryRef = useCallback(
    (id: number) => (el: HTMLDivElement | null) => {
      if (el) categoryRefs.current.set(id, el);
      else categoryRefs.current.delete(id);
    },
    [],
  );

  // IntersectionObserver to track which category is in view
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container || categories.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (suppressObserverRef.current) return;
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = Number(entry.target.getAttribute("data-category-id"));
            if (!isNaN(id)) setActiveCategoryId(id);
          }
        }
      },
      {
        root: container,
        rootMargin: "-20% 0px -70% 0px",
        threshold: 0,
      },
    );

    categoryRefs.current.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [categories]);

  const handleCategoryClick = (categoryId: number) => {
    const el = categoryRefs.current.get(categoryId);
    if (!el) return;

    // Suppress observer during programmatic scroll
    suppressObserverRef.current = true;
    setActiveCategoryId(categoryId);

    el.scrollIntoView({ behavior: "smooth", block: "start" });

    clearTimeout(suppressTimerRef.current);
    suppressTimerRef.current = setTimeout(() => {
      suppressObserverRef.current = false;
    }, 800);
  };

  const handleToggleExpand = (itemId: number) => {
    setExpandedItemId((prev) => (prev === itemId ? null : itemId));
  };

  if (categories.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-muted-foreground">No menu items available.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sticky category bar */}
      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border/50">
        <CategoryBar
          categories={categories.map((c) => ({ id: c.id, name: c.name }))}
          activeCategoryId={activeCategoryId}
          onCategoryClick={handleCategoryClick}
        />
      </div>

      {/* Scrollable menu items */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 pb-24"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        {categories.map((category) => (
          <div
            key={category.id}
            ref={setCategoryRef(category.id)}
            data-category-id={category.id}
            className="pt-4"
          >
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">
              {category.name}
            </h3>
            <div className="space-y-2">
              {category.items.map((item) => (
                <MenuItemCard
                  key={item.id}
                  item={item}
                  isExpanded={expandedItemId === item.id}
                  onToggleExpand={() => handleToggleExpand(item.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep MenuBrowseTab`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/MenuBrowseTab.tsx"
git commit -m "feat: add MenuBrowseTab component

Full menu browsing with category navigation via IntersectionObserver
(uses ref-based suppression to prevent flicker during programmatic scroll),
inline item expansion for variants/modifiers."
```

---

### Task 8: Create VoiceChatTab component

**Files:**
- Create: `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx`

- [ ] **Step 1: Create the VoiceChatTab component**

This is a refactored version of `InputStep` that works as a tab — no step transitions, inline loading/confirmation.

Write `frontend/src/app/order/[slug]/components/VoiceChatTab.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Send, Check } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useOrderStore } from "@/stores/order-store";
import { usePreferencesStore } from "@/stores/preferences-store";
import { useSpeechRecognition } from "@/hooks/use-speech-recognition";
import { useParseOrder } from "@/hooks/use-parse-order";
import { SPEECH_LANGUAGES } from "@/lib/constants";

interface VoiceChatTabProps {
  slug: string;
}

export function VoiceChatTab({ slug }: VoiceChatTabProps) {
  const { setRawInput } = useOrderStore();
  const { preferredLanguage } = usePreferencesStore();
  const [input, setInput] = useState("");
  const [speechLang, setSpeechLang] = useState(preferredLanguage);
  const [addedMessage, setAddedMessage] = useState<string | null>(null);
  const { isListening, transcript, startListening, stopListening, isSupported } =
    useSpeechRecognition({ lang: speechLang || undefined });

  const parseOrderMutation = useParseOrder(slug);

  const currentInput = isListening ? transcript : input;

  const handleSubmit = async () => {
    const text = currentInput.trim();
    if (!text || parseOrderMutation.isPending) return;

    setRawInput(text);
    setInput("");

    parseOrderMutation.mutate(text, {
      onSuccess: (result) => {
        const count = result.items.reduce((sum, i) => sum + i.quantity, 0);
        const names = result.items.map((i) => `${i.quantity}x ${i.name}`).join(", ");
        setAddedMessage(`Added ${names} (${count} item${count !== 1 ? "s" : ""})`);
        setTimeout(() => setAddedMessage(null), 3000);
      },
    });
  };

  const toggleVoice = () => {
    if (isListening) {
      stopListening();
      setInput(transcript);
    } else {
      startListening();
    }
  };

  const waveHeights = [28, 36, 24, 40, 32, 20, 38, 26, 34, 22, 30, 40, 24, 36, 28, 32];

  return (
    <div className="flex flex-col items-center gap-8 px-4 py-10 pb-24">
      {/* Header */}
      <div className="text-center animate-fade-in-up">
        <h2 className="text-2xl font-semibold tracking-tight mb-2">What would you like?</h2>
        <p className="text-sm text-muted-foreground">
          Speak or type your order naturally
        </p>
      </div>

      {/* Microphone orb section */}
      {isSupported && (
        <div className="relative flex flex-col items-center gap-4 animate-fade-in-up-delay-1">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[55%] w-[300px] h-[300px] bg-[radial-gradient(circle,rgba(124,58,237,0.2),rgba(99,102,241,0.08)_50%,transparent_70%)] rounded-full pointer-events-none" />

          {isListening && (
            <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground animate-fade-in-up">
              Listening...
            </p>
          )}

          <div className="relative flex items-center justify-center">
            {isListening && (
              <>
                <div
                  className="absolute top-1/2 left-1/2 border border-primary/15 rounded-full animate-pulse-ring"
                  style={{ width: 160, height: 160 }}
                />
                <div
                  className="absolute top-1/2 left-1/2 border border-primary/15 rounded-full animate-pulse-ring-delayed"
                  style={{ width: 200, height: 200 }}
                />
              </>
            )}

            <button
              onClick={toggleVoice}
              disabled={parseOrderMutation.isPending}
              className="relative w-[120px] h-[120px] rounded-full flex items-center justify-center gradient-primary glow-primary-lg transition-all duration-300 hover:scale-105 active:scale-95 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
              aria-label={isListening ? "Stop recording" : "Start recording"}
            >
              {isListening ? (
                <div className="flex items-center gap-[3px]">
                  {waveHeights.map((h, i) => (
                    <div
                      key={i}
                      className="w-[3px] rounded-full bg-primary-foreground/80 animate-waveform"
                      style={
                        {
                          "--wave-height": `${h}px`,
                          animationDelay: `${i * 0.075}s`,
                          height: "12px",
                        } as React.CSSProperties
                      }
                    />
                  ))}
                </div>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="40"
                  height="40"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-primary-foreground"
                >
                  <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" x2="12" y1="19" y2="22" />
                </svg>
              )}
            </button>
          </div>

          <select
            value={speechLang}
            onChange={(e) => setSpeechLang(e.target.value)}
            disabled={isListening || parseOrderMutation.isPending}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-xs text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 disabled:opacity-50"
          >
            {SPEECH_LANGUAGES.map((lang) => (
              <option key={lang.code} value={lang.code}>
                {lang.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Live transcript display */}
      {isListening && (
        <div className="w-full glass-card rounded-2xl p-4 min-h-[80px] animate-fade-in-up">
          <p className="text-foreground/70 text-sm leading-relaxed">
            {transcript || (
              <span className="text-muted-foreground italic">Start speaking…</span>
            )}
            <span className="w-0.5 h-4 bg-primary/70 animate-blink-cursor inline-block ml-1 align-middle" />
          </p>
        </div>
      )}

      {/* Inline loading indicator */}
      {parseOrderMutation.isPending && (
        <div className="w-full glass-card rounded-2xl p-4 animate-fade-in-up">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-pulse" style={{ animationDelay: "0s" }} />
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-pulse" style={{ animationDelay: "0.2s" }} />
              <span className="w-2 h-2 rounded-full bg-primary/50 animate-pulse" style={{ animationDelay: "0.4s" }} />
            </div>
            <p className="text-sm text-muted-foreground">Understanding your order...</p>
          </div>
        </div>
      )}

      {/* Success confirmation */}
      {addedMessage && (
        <div className="w-full glass-card rounded-2xl p-4 animate-fade-in-up border border-green-500/20 bg-green-500/5">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500 shrink-0" />
            <p className="text-sm text-green-400">{addedMessage}</p>
          </div>
        </div>
      )}

      {/* Text input */}
      {!isListening && (
        <div className="w-full animate-fade-in-up-delay-2">
          <div className="glass-card rounded-xl p-1 flex items-end gap-2">
            <Textarea
              value={currentInput}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Or type your order here…"
              rows={3}
              disabled={isListening || parseOrderMutation.isPending}
              className="flex-1 resize-none border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 text-sm placeholder:text-muted-foreground/60 disabled:opacity-50"
            />
            <button
              onClick={handleSubmit}
              disabled={!currentInput.trim() || parseOrderMutation.isPending}
              className="mb-1 mr-1 p-2.5 bg-primary/20 rounded-lg text-primary hover:bg-primary/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary/50"
              aria-label="Submit order"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      )}

      {/* Error display */}
      {parseOrderMutation.isError && (
        <p className="text-destructive text-sm">
          {parseOrderMutation.error instanceof Error
            ? parseOrderMutation.error.message
            : "Failed to parse order"}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep VoiceChatTab`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/VoiceChatTab.tsx"
git commit -m "feat: add VoiceChatTab component

Refactored from InputStep to work as a tab. Inline loading indicator
replaces LoadingStep. Shows confirmation message after successful parse.
No step transitions — items added to shared cart silently."
```

---

### Task 9: Create OrderingStep container

**Files:**
- Create: `frontend/src/app/order/[slug]/components/OrderingStep.tsx`

- [ ] **Step 1: Create the OrderingStep component**

Write `frontend/src/app/order/[slug]/components/OrderingStep.tsx`:

```tsx
"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { MenuBrowseTab } from "./MenuBrowseTab";
import { VoiceChatTab } from "./VoiceChatTab";
import { CartBottomBar } from "./CartBottomBar";
import type { MenuCategory } from "@/types";

interface OrderingStepProps {
  slug: string;
  categories: MenuCategory[];
}

type ActiveTab = "menu" | "voice";

export function OrderingStep({ slug, categories }: OrderingStepProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("menu");

  return (
    <div
      className="flex flex-col bg-background"
      style={{ height: "100dvh" }}
    >
      {/* Tab bar */}
      <div className="shrink-0 border-b border-border bg-background/95 backdrop-blur-sm pt-14 px-4">
        <div className="max-w-lg mx-auto flex">
          <button
            onClick={() => setActiveTab("menu")}
            className={cn(
              "flex-1 py-3 text-sm font-medium text-center transition-colors border-b-2",
              activeTab === "menu"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            Menu
          </button>
          <button
            onClick={() => setActiveTab("voice")}
            className={cn(
              "flex-1 py-3 text-sm font-medium text-center transition-colors border-b-2",
              activeTab === "voice"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            Voice / Chat
          </button>
        </div>
      </div>

      {/* Tab content — both kept mounted to preserve state */}
      <div className="flex-1 overflow-hidden relative">
        <div
          className={cn(
            "absolute inset-0 overflow-y-auto",
            activeTab === "menu" ? "visible" : "invisible",
          )}
        >
          <div className="max-w-lg mx-auto">
            <MenuBrowseTab categories={categories} />
          </div>
        </div>
        <div
          className={cn(
            "absolute inset-0 overflow-y-auto",
            activeTab === "voice" ? "visible" : "invisible",
          )}
        >
          <div className="max-w-lg mx-auto">
            <VoiceChatTab slug={slug} />
          </div>
        </div>
      </div>

      {/* Persistent cart bottom bar */}
      <CartBottomBar />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep OrderingStep`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/order/[slug]/components/OrderingStep.tsx"
git commit -m "feat: add OrderingStep tab container

Renders Menu and Voice/Chat tabs with both kept mounted for state
preservation. Uses 100dvh for mobile viewport. Includes CartBottomBar."
```

---

### Task 10: Update the order page to use OrderingStep

**Files:**
- Modify: `frontend/src/app/order/[slug]/page.tsx`

- [ ] **Step 1: Update imports and step rendering**

In `frontend/src/app/order/[slug]/page.tsx`:

Replace the imports section (lines 1-18) with:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Settings, User } from "lucide-react";
import { useOrderStore } from "@/stores/order-store";
import { useAuthStore } from "@/stores/auth-store";
import { useMenu } from "@/hooks/use-menu";
import { Button } from "@/components/ui/button";
import { PreferencesDialog } from "@/components/PreferencesDialog";
import { WelcomeStep } from "./components/WelcomeStep";
import { OrderingStep } from "./components/OrderingStep";
import { ConfirmationStep } from "./components/ConfirmationStep";
import { PaymentStep } from "./components/PaymentStep";
import { SubmittedStep } from "./components/SubmittedStep";
```

Replace the step rendering section (lines 77-82) with:

```tsx
      {step === "welcome" && <WelcomeStep restaurantName={menu.restaurant_name} />}
      {step === "ordering" && <OrderingStep slug={slug} categories={menu.categories} />}
      {step === "cart" && <ConfirmationStep slug={slug} taxRate={menu.tax_rate} paymentMode={menu.payment_mode ?? "stripe"} />}
      {step === "payment" && <PaymentStep taxRate={menu.tax_rate} />}
      {step === "submitted" && <SubmittedStep slug={slug} />}
```

Also remove the `<MenuModal>` from the header section (line 75). The full header `div` (lines 57-76) becomes:

```tsx
      <div className="fixed top-4 right-4 z-40 flex items-center gap-2">
        {mounted && (isAuthenticated ? (
          <Link href="/account/profile" className="text-sm text-muted-foreground hover:text-foreground">
            <User className="h-5 w-5" />
          </Link>
        ) : (
          <Link href="/account/login" className="text-sm text-muted-foreground hover:text-foreground">
            Sign in
          </Link>
        ))}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setPrefsOpen(true)}
          title="Preferences"
        >
          <Settings className="h-5 w-5" />
        </Button>
      </div>
```

- [ ] **Step 2: Narrow the OrderStep type**

Now that all consumers of `"input"` and `"loading"` have been removed or updated, clean up the temporary type in `frontend/src/stores/order-store.ts`:

```typescript
// Remove the temporary values:
type OrderStep = "welcome" | "ordering" | "cart" | "payment" | "submitted";
```

- [ ] **Step 3: Verify full TypeScript compilation passes**

Run: `cd frontend && npx tsc --noEmit`

Expected: Clean build with no errors.

- [ ] **Step 4: Commit**

```bash
git add "frontend/src/app/order/[slug]/page.tsx" frontend/src/stores/order-store.ts
git commit -m "feat: integrate OrderingStep into order page

Replace InputStep/LoadingStep/MenuModal with unified OrderingStep.
Tab-based Menu + Voice/Chat ordering with shared cart.
Remove deprecated 'input' and 'loading' step types."
```

---

## Chunk 4: Viewport and Cleanup

### Task 11: Add viewport-fit=cover metadata

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Add viewport export**

In `frontend/src/app/layout.tsx`, add after the existing `metadata` export (after line 30):

```tsx
export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
};
```

This tells Next.js to add `viewport-fit=cover` to the viewport meta tag for edge-to-edge rendering on notched devices.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat: add viewport-fit=cover for notched devices"
```

---

### Task 12: Add scrollbar-hide utility

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Check if scrollbar-hide already exists**

Run: `grep "scrollbar-hide" frontend/src/app/globals.css`

If it doesn't exist, add this utility class to `globals.css` (inside the `@layer utilities` block if one exists, or at the end of the file):

```css
/* Hide scrollbar for category bar horizontal scroll */
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat: add scrollbar-hide utility for category bar"
```

---

### Task 13: Manual smoke test

- [ ] **Step 1: Start the frontend dev server**

Run: `cd frontend && npm run dev`

- [ ] **Step 2: Test the full ordering flow in browser**

Open `http://localhost:3001/order/<a-valid-restaurant-slug>` and verify:

1. Welcome page loads, "Start Ordering" button works
2. Lands on ordering step with Menu/Voice tabs
3. **Menu tab:**
   - Category pills are visible and horizontally scrollable
   - Scrolling the menu updates the active category pill
   - Tapping a category pill scrolls to that section
   - Items without variants: tapping adds directly (green check flash)
   - Items with variants: tapping expands inline options
   - Can select variant, toggle modifiers, adjust quantity
   - "Add $X.XX" button works and collapses the card
4. **Voice/Chat tab:**
   - Mic orb and text input are present
   - Typing and submitting shows inline loading dots
   - After parse completes, shows green confirmation message
   - Items appear in cart bottom bar count
5. **Cart bottom bar:**
   - Shows "Cart is empty" and disabled button initially
   - After adding items, shows count and total
   - "Review Order" button transitions to confirmation step
6. **Confirmation step:**
   - Shows all items from both menu and voice
   - "Add More" button returns to ordering step (menu tab)
   - "Go Back" on empty cart returns to ordering step
7. **Mobile viewport:** Resize browser to mobile width, verify layout is comfortable

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address issues found during smoke test"
```

(Only if fixes were needed.)
