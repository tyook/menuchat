"use client";

import { useOrderStore } from "@/stores/order-store";
import { Button } from "@/components/ui/button";

export function TabClosedStep() {
  const { tabTotal, tabAmountPaid, reset } = useOrderStore();

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 text-center overflow-hidden">
      {/* Warm ambient glow */}
      <div
        aria-hidden
        className="absolute w-[320px] h-[320px] bg-[radial-gradient(circle,rgba(217,119,6,0.15),transparent_70%)] rounded-full pointer-events-none animate-glow-pulse"
      />
      <div
        aria-hidden
        className="absolute w-[200px] h-[200px] translate-y-[-60px] bg-[radial-gradient(circle,rgba(251,191,36,0.1),transparent_70%)] rounded-full pointer-events-none animate-glow-pulse"
        style={{ animationDelay: "1s" }}
      />

      {/* Checkmark icon */}
      <div className="relative mb-8 animate-fade-in-up">
        <div className="w-24 h-24 rounded-full border-2 border-primary/30 flex items-center justify-center">
          <div className="w-16 h-16 rounded-full gradient-primary flex items-center justify-center glow-primary">
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
        </div>
        {/* Pulse rings */}
        <div
          aria-hidden
          className="absolute top-1/2 left-1/2 w-24 h-24 border border-primary/20 rounded-full animate-pulse-ring"
        />
        <div
          aria-hidden
          className="absolute top-1/2 left-1/2 w-24 h-24 border border-primary/10 rounded-full animate-pulse-ring-delayed"
        />
      </div>

      {/* Heading */}
      <h2 className="text-3xl font-bold text-foreground mb-2 animate-fade-in-up-delay-1">
        All Settled!
      </h2>
      <p className="text-muted-foreground text-base max-w-xs mb-8 animate-fade-in-up-delay-1">
        Your tab has been fully paid. Thanks for dining with us — enjoy the rest of your day.
      </p>

      {/* Receipt summary card */}
      <div className="glass-card rounded-2xl p-6 w-full max-w-sm animate-fade-in-up-delay-2">
        <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-4">
          Receipt
        </p>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground text-sm">Tab Total</span>
            <span className="text-foreground font-medium">${tabTotal}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground text-sm">Amount Paid</span>
            <span className="text-green-400 font-medium">${tabAmountPaid}</span>
          </div>
          <div className="border-t border-border/40 pt-3 flex justify-between items-center">
            <span className="text-foreground font-semibold text-sm">Balance</span>
            <span className="gradient-text font-bold text-lg">$0.00</span>
          </div>
        </div>
      </div>

      {/* CTA */}
      <Button
        variant="gradient"
        size="lg"
        className="mt-8 w-full max-w-sm glow-primary animate-fade-in-up-delay-3"
        onClick={reset}
      >
        Done
      </Button>
    </div>
  );
}
