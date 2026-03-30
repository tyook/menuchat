"use client";

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { useDismissOnboarding } from "@/hooks/use-onboarding";
import { X } from "lucide-react";

export function OnboardingBanner() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();
  const dismissMutation = useDismissOnboarding();

  if (
    !isAuthenticated ||
    !user ||
    user.onboarding_completed ||
    user.onboarding_dismissed
  ) {
    return null;
  }

  const handleDismiss = () => {
    dismissMutation.mutate();
  };

  return (
    <div className="bg-card border border-border rounded-xl p-4 border-l-4 border-l-primary flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-foreground text-sm">
          Complete your profile for a personalized experience
        </span>
        <button
          onClick={() => router.push("/account/onboarding")}
          className="text-primary hover:underline text-sm font-medium"
        >
          Set up now
        </button>
      </div>
      <button
        onClick={handleDismiss}
        className="text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
