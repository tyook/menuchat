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
