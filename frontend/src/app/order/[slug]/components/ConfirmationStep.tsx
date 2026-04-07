"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useOrderStore } from "@/stores/order-store";
import { usePreferencesStore } from "@/stores/preferences-store";
import { useAuthStore } from "@/stores/auth-store";
import { useProfile } from "@/hooks/use-profile";
import { useCreatePayment } from "@/hooks/use-create-payment";
import { BusynessBanner } from "./BusynessBanner";
import { useConfirmOrder } from "@/hooks/use-confirm-order";
import { UpsellSuggestions } from "./UpsellSuggestions";
import type { ConfirmOrderItem } from "@/types";

interface ConfirmationStepProps {
  slug: string;
  taxRate: string;
  paymentMode: "stripe" | "pos_collected";
}

export function ConfirmationStep({ slug, taxRate, paymentMode }: ConfirmationStepProps) {
  const {
    parsedItems,
    parsedAllergies,
    totalPrice,
    rawInput,
    language,
    tableIdentifier,
    customerName,
    customerPhone,
    setStep,
    setOrderId,
    setError,
    setClientSecret,
    setCustomerName,
    setCustomerPhone,
    setPaymentMode,
    removeItem,
    updateItemQuantity,
  } = useOrderStore();
  const { allergyNote } = usePreferencesStore();
  const { isAuthenticated } = useAuthStore();
  const { data: profile } = useProfile();
  const createPaymentMutation = useCreatePayment(slug);
  const confirmOrderMutation = useConfirmOrder(slug);

  // Auto-fill name and phone if customer is logged in
  useEffect(() => {
    if (isAuthenticated && profile && !customerName) {
      setCustomerName(profile.name);
    }
  }, [isAuthenticated, profile, customerName, setCustomerName]);

  const handleConfirm = () => {
    const items: ConfirmOrderItem[] = parsedItems.map((item) => ({
      menu_item_id: item.menu_item_id,
      variant_id: item.variant.id,
      quantity: item.quantity,
      modifier_ids: item.modifiers.map((m) => m.id),
      special_requests: item.special_requests,
    }));

    // Merge LLM-detected allergies with user-set allergy preferences
    const prefAllergies = allergyNote
      ? allergyNote.split(",").map((a) => a.trim()).filter(Boolean)
      : [];
    const allAllergies = Array.from(new Set([...parsedAllergies, ...prefAllergies]));

    if (paymentMode === "pos_collected") {
      confirmOrderMutation.mutate(
        { items, rawInput, tableIdentifier, language, customerName, customerPhone },
        {
          onSuccess: (result) => {
            setOrderId(result.id);
            setPaymentMode("pos_collected");
            setStep("submitted");
          },
          onError: (err) => {
            setError(err instanceof Error ? err.message : "Failed to place order");
          },
        }
      );
    } else {
      createPaymentMutation.mutate(
        { items, rawInput, tableIdentifier, language, customerName, customerPhone, allergies: allAllergies },
        {
          onSuccess: (result) => {
            setOrderId(result.id);
            setClientSecret(result.client_secret);
            setStep("payment");
          },
          onError: (err) => {
            setError(err instanceof Error ? err.message : "Failed to create payment");
          },
        }
      );
    }
  };

  const isSubmitting = paymentMode === "pos_collected"
    ? confirmOrderMutation.isPending
    : createPaymentMutation.isPending;

  if (parsedItems.length === 0) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8 text-center">
        <p className="text-muted-foreground mb-4">
          We couldn&apos;t match anything from the menu. Try again?
        </p>
        <Button onClick={() => setStep("ordering")}>Go Back</Button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <BusynessBanner slug={slug} />

      <div className="mb-6">
        <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-1">Your Order</p>
        <h2 className="text-2xl font-semibold text-foreground">Review &amp; Confirm</h2>
      </div>

      <div className="space-y-3 mb-6">
        {parsedItems.map((item, index) => (
          <div key={index} className="glass-card rounded-2xl p-5">
            <div className="flex justify-between items-start">
              <div className="flex-1 min-w-0 mr-4">
                <p className="text-foreground font-semibold">{item.name}</p>
                <p className="text-muted-foreground text-xs mt-0.5">
                  {item.variant.label} — ${item.variant.price}
                </p>
                {item.modifiers.length > 0 && (
                  <p className="text-muted-foreground text-xs">
                    + {item.modifiers.map((m) => m.name).join(", ")}
                  </p>
                )}
                {item.special_requests && (
                  <p className="text-muted-foreground text-xs italic mt-0.5">Note: {item.special_requests}</p>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  className="bg-card border border-border rounded-lg"
                  onClick={() =>
                    item.quantity > 1
                      ? updateItemQuantity(index, item.quantity - 1)
                      : removeItem(index)
                  }
                >
                  -
                </Button>
                <span className="w-6 text-center font-semibold text-foreground">{item.quantity}</span>
                <Button
                  variant="outline"
                  size="sm"
                  className="bg-primary/20 text-primary border-transparent rounded-lg hover:bg-primary/30"
                  onClick={() => updateItemQuantity(index, item.quantity + 1)}
                >
                  +
                </Button>
              </div>
            </div>
            <p className="text-right text-primary font-semibold mt-3">
              ${item.line_total}
            </p>
          </div>
        ))}
      </div>

      {(parsedAllergies.length > 0 || allergyNote) && (
        <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm">
          <p className="font-medium text-amber-300">
            Allergies noted:
          </p>
          <p className="text-amber-400/80">
            {Array.from(new Set([
              ...parsedAllergies,
              ...(allergyNote ? allergyNote.split(",").map((a) => a.trim()).filter(Boolean) : []),
            ])).join(", ")}
          </p>
        </div>
      )}

      <UpsellSuggestions slug={slug} />

      <Separator className="my-4" />

      {/* Customer info */}
      <div className="space-y-3 mb-6">
        <div>
          <Label htmlFor="customer-name">Your name *</Label>
          <Input
            id="customer-name"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            placeholder="Name for the order"
            required
          />
        </div>
        <div>
          <Label htmlFor="customer-phone">Phone (optional)</Label>
          <Input
            id="customer-phone"
            type="tel"
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
            placeholder="For order updates"
          />
        </div>
      </div>

      <div className="border-t border-border pt-4 mb-6">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-muted-foreground">Subtotal</span>
          <span className="text-foreground">${totalPrice}</span>
        </div>
        {parseFloat(taxRate) > 0 && (
          <div className="flex justify-between text-sm text-muted-foreground mb-1">
            <span>Tax ({taxRate}%)</span>
            <span>${(parseFloat(totalPrice) * parseFloat(taxRate) / 100).toFixed(2)}</span>
          </div>
        )}
        <div className="flex justify-between items-center pt-2">
          <span className="text-foreground font-semibold">Total</span>
          <span className="gradient-text text-xl font-bold">
            ${(parseFloat(totalPrice) + parseFloat(totalPrice) * parseFloat(taxRate) / 100).toFixed(2)}
          </span>
        </div>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" onClick={() => setStep("ordering")}>
          Add More
        </Button>
        <Button
          variant="gradient"
          size="lg"
          className="flex-1 glow-primary"
          onClick={handleConfirm}
          disabled={isSubmitting || !customerName.trim()}
        >
          {isSubmitting
            ? (paymentMode === "pos_collected" ? "Placing order..." : "Setting up payment...")
            : "Proceed to Pay"}
        </Button>
      </div>
    </div>
  );
}
