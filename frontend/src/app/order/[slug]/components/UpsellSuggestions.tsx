"use client";

import { useState } from "react";
import { Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCartUpsell } from "@/hooks/use-cart-upsell";
import { useOrderStore } from "@/stores/order-store";
import type { ParsedOrderItem, UpsellSuggestion } from "@/types";

interface UpsellSuggestionsProps {
  slug: string;
}

export function UpsellSuggestions({ slug }: UpsellSuggestionsProps) {
  const parsedItems = useOrderStore((s) => s.parsedItems);
  const addItem = useOrderStore((s) => s.addItem);
  const { data, isLoading } = useCartUpsell(slug, parsedItems);
  const [addedIds, setAddedIds] = useState<Set<number>>(new Set());

  const cartItemIds = new Set(parsedItems.map((i) => i.menu_item_id));

  const suggestions = (data?.suggestions ?? []).filter(
    (s) => !cartItemIds.has(s.menu_item_id) && !addedIds.has(s.menu_item_id)
  );

  const handleAdd = (suggestion: UpsellSuggestion) => {
    if (!suggestion.variant_id || !suggestion.price) return;

    const newItem: ParsedOrderItem = {
      menu_item_id: suggestion.menu_item_id,
      name: suggestion.name,
      variant: {
        id: suggestion.variant_id,
        label: suggestion.variant_label ?? "Regular",
        price: suggestion.price,
      },
      quantity: 1,
      modifiers: [],
      special_requests: "",
      line_total: suggestion.price,
    };

    addItem(newItem);
    setAddedIds((prev) => new Set(prev).add(suggestion.menu_item_id));
  };

  if (isLoading) {
    return (
      <div className="mb-6 space-y-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Sparkles className="h-4 w-4 animate-pulse text-primary" />
          <span>Finding suggestions for you...</span>
        </div>
        {[1, 2].map((i) => (
          <div
            key={i}
            className="glass-card rounded-2xl p-4 animate-pulse"
          >
            <div className="flex gap-3">
              <div className="h-14 w-14 rounded-xl bg-muted shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-24 bg-muted rounded" />
                <div className="h-3 w-40 bg-muted rounded" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (suggestions.length === 0) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="h-4 w-4 text-primary" />
        <p className="text-sm font-medium text-muted-foreground">
          You might also enjoy
        </p>
      </div>
      <div className="space-y-3">
        {suggestions.map((suggestion) => (
          <div
            key={suggestion.menu_item_id}
            className="glass-card rounded-2xl p-4"
          >
            <div className="flex gap-3 items-start">
              {suggestion.image_url && (
                <img
                  src={suggestion.image_url}
                  alt={suggestion.name}
                  className="h-14 w-14 rounded-xl object-cover shrink-0"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-foreground font-semibold text-sm">
                      {suggestion.name}
                    </p>
                    {suggestion.price && (
                      <p className="text-primary text-sm font-medium">
                        ${suggestion.price}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0 bg-primary/10 text-primary border-primary/20 hover:bg-primary/20"
                    onClick={() => handleAdd(suggestion)}
                  >
                    <Plus className="h-3.5 w-3.5 mr-1" />
                    Add
                  </Button>
                </div>
                <p className="text-muted-foreground text-xs mt-1 italic">
                  {suggestion.reason}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
