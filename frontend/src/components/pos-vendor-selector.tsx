"use client";

import { cn } from "@/lib/utils";
import { Square, UtensilsCrossed, X } from "lucide-react";

interface VendorOption {
  id: string;
  name: string;
  tagline: string;
  icon: React.ReactNode;
  comingSoon: boolean;
}

const VENDORS: VendorOption[] = [
  {
    id: "square",
    name: "Square",
    tagline: "Popular with restaurants & retail",
    icon: <Square className="h-8 w-8" />,
    comingSoon: false,
  },
  {
    id: "toast",
    name: "Toast",
    tagline: "Built for restaurants",
    icon: <UtensilsCrossed className="h-8 w-8" />,
    comingSoon: true,
  },
  {
    id: "none",
    name: "None",
    tagline: "I don't use a POS",
    icon: <X className="h-8 w-8" />,
    comingSoon: false,
  },
];

interface POSVendorSelectorProps {
  selected: string | null;
  onSelect: (posType: string) => void;
}

export function POSVendorSelector({ selected, onSelect }: POSVendorSelectorProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {VENDORS.map((vendor) => {
        const isSelected = selected === vendor.id;
        const isDisabled = vendor.comingSoon;

        return (
          <button
            key={vendor.id}
            type="button"
            disabled={isDisabled}
            onClick={() => onSelect(vendor.id)}
            className={cn(
              "relative flex flex-col items-center gap-3 rounded-2xl border-2 p-6 text-center transition-all",
              isDisabled && "cursor-not-allowed opacity-50",
              !isDisabled && !isSelected && "border-border hover:border-primary/40 hover:bg-accent/50",
              !isDisabled && isSelected && "border-primary bg-primary/5 ring-1 ring-primary/20",
              vendor.id === "none" && !isSelected && "border-dashed"
            )}
          >
            {vendor.comingSoon && (
              <span className="absolute top-2 right-2 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                Coming Soon
              </span>
            )}
            <div
              className={cn(
                "flex h-14 w-14 items-center justify-center rounded-xl",
                isSelected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              )}
            >
              {vendor.icon}
            </div>
            <div>
              <div className="font-semibold">{vendor.name}</div>
              <div className="mt-1 text-xs text-muted-foreground">{vendor.tagline}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
