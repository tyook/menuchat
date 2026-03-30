"use client";

import { Button } from "@/components/ui/button";
import { useOrderStore } from "@/stores/order-store";

interface WelcomeStepProps {
  restaurantName: string;
}

export function WelcomeStep({ restaurantName }: WelcomeStepProps) {
  const setStep = useOrderStore((s) => s.setStep);

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 text-center">
      {/* Ambient glow orbs */}
      <div
        aria-hidden
        className="absolute top-1/4 left-1/4 -z-10 h-[350px] w-[350px] rounded-full animate-glow-pulse pointer-events-none bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]"
      />
      <div
        aria-hidden
        className="absolute bottom-1/4 right-1/4 -z-10 h-[250px] w-[250px] rounded-full animate-glow-pulse pointer-events-none bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]"
        style={{ animationDelay: "2s" }}
      />

      <div className="flex flex-col items-center gap-4 w-full max-w-sm">
        <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground">
          Welcome to
        </p>
        <h1 className="gradient-text text-3xl font-bold tracking-tight">
          {restaurantName}
        </h1>
        <p className="text-muted-foreground text-sm">
          Type or speak your order in any language
        </p>
        <Button
          variant="gradient"
          size="lg"
          className="w-full max-w-sm glow-primary-lg"
          onClick={() => setStep("input")}
        >
          Start Ordering
        </Button>
      </div>
    </div>
  );
}
