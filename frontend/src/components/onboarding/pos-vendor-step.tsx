"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { POSVendorSelector } from "@/components/pos-vendor-selector";
import { usePOSVendorSelect } from "@/hooks/use-pos-vendor-select";
import { useToast } from "@/hooks/use-toast";

interface POSVendorStepProps {
  slug: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function POSVendorStep({ slug, onComplete, onSkip }: POSVendorStepProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const vendorSelect = usePOSVendorSelect(slug);
  const { toast } = useToast();

  const handleContinue = () => {
    if (!selected) return;
    vendorSelect.mutate(selected, {
      onSuccess: () => onComplete(),
      onError: (err) => {
        toast({
          title: "Failed to save POS selection",
          description: err instanceof Error ? err.message : "Unknown error",
          variant: "destructive",
        });
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Connect Your POS</h1>
        <p className="text-muted-foreground mt-1">
          Select your point-of-sale system to sync orders automatically.
          You can connect it later from settings.
        </p>
      </div>

      <POSVendorSelector selected={selected} onSelect={setSelected} />

      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleContinue}
          className="flex-1"
          disabled={!selected || vendorSelect.isPending}
        >
          {vendorSelect.isPending ? "Saving..." : "Continue"}
        </Button>
        <Button variant="ghost" onClick={onSkip}>
          Skip for now
        </Button>
      </div>
    </div>
  );
}
