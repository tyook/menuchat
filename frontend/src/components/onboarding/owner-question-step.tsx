"use client";

import { Button } from "@/components/ui/button";
import { Store, User } from "lucide-react";

interface OwnerQuestionStepProps {
  onYes: () => void;
  onNo: () => void;
  onBack: () => void;
}

export function OwnerQuestionStep({ onYes, onNo, onBack }: OwnerQuestionStepProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Do you own a restaurant?</h1>
        <p className="text-muted-foreground mt-1">
          If you own or manage a restaurant, we can help you set up QR code ordering.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={onYes}
          className="glass-card rounded-2xl p-5 flex flex-col items-center gap-3 text-center hover:border-primary/30 cursor-pointer transition-colors"
        >
          <Store className="h-8 w-8 text-primary" />
          <span className="text-lg font-semibold text-foreground">Yes, I do</span>
          <span className="text-xs text-muted-foreground">
            Set up your restaurant
          </span>
        </button>

        <button
          onClick={onNo}
          className="glass-card rounded-2xl p-5 flex flex-col items-center gap-3 text-center hover:border-primary/30 cursor-pointer transition-colors"
        >
          <User className="h-8 w-8 text-primary" />
          <span className="text-lg font-semibold text-foreground">No, just dining</span>
          <span className="text-xs text-muted-foreground">
            Start ordering right away
          </span>
        </button>
      </div>

      <div className="flex items-center justify-between pt-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          Back
        </Button>
        <Button variant="link" size="sm" onClick={onNo}>
          Skip for now
        </Button>
      </div>
    </div>
  );
}
