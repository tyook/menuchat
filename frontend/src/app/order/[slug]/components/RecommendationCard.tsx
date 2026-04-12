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
