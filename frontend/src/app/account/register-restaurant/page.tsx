"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/hooks/use-auth";
import { useProfile } from "@/hooks/use-profile";
import { RestaurantDetailsStep } from "@/components/onboarding/restaurant-details-step";
import { MenuUploadStep } from "@/components/onboarding/menu-upload-step";
import { cn } from "@/lib/utils";

type Step = "details" | "menu";

export default function RegisterRestaurantPage() {
  const isAuthenticated = useRequireAuth();
  const router = useRouter();
  const { data: profile, isLoading } = useProfile();
  const [step, setStep] = useState<Step>("details");
  const [restaurantSlug, setRestaurantSlug] = useState<string | null>(null);

  if (isAuthenticated === null || isLoading) {
    return (
      <div className="max-w-xl mx-auto px-4 py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
      </div>
    );
  }

  if (isAuthenticated === false) return null;

  // Redirect owners to their restaurants list
  if (profile?.owns_restaurant) {
    router.replace("/account/restaurants");
    return null;
  }

  const totalSteps = 2;
  const currentStep = step === "details" ? 1 : 2;

  const handleComplete = () => {
    router.push("/account/restaurants");
  };

  return (
    <div className="min-h-screen bg-background flex items-start justify-center px-4 py-8 relative overflow-hidden">
      {/* Ambient glow orb */}
      <div className="absolute w-[400px] h-[400px] bg-[radial-gradient(circle,rgba(124,58,237,0.10),transparent_70%)] rounded-full animate-glow-pulse pointer-events-none top-1/4 left-1/2 -translate-x-1/2" />

      <div className="w-full max-w-xl relative z-10">
        {/* Step indicators */}
        <div className="mb-8 flex items-center justify-center gap-3">
          {Array.from({ length: totalSteps }, (_, i) => {
            const stepIndex = i + 1;
            const isCompleted = stepIndex < currentStep;
            const isCurrent = stepIndex === currentStep;
            return (
              <div key={stepIndex} className="flex items-center gap-3">
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all",
                    isCompleted && "bg-primary text-primary-foreground",
                    isCurrent && "border-2 border-primary text-primary",
                    !isCompleted && !isCurrent && "border border-border text-muted-foreground"
                  )}
                >
                  {isCompleted ? (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <path d="M2 7l3.5 3.5L12 3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : (
                    stepIndex
                  )}
                </div>
                {stepIndex < totalSteps && (
                  <div className={cn("h-px w-8", isCompleted ? "bg-primary" : "bg-border")} />
                )}
              </div>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground text-center mb-6">
          Step {currentStep} of {totalSteps}
        </p>

        {/* Step content inside glass card */}
        <div className="glass-card rounded-2xl p-8">
          {step === "details" && (
            <RestaurantDetailsStep
              onCreated={(slug) => {
                setRestaurantSlug(slug);
                setStep("menu");
              }}
              onBack={() => router.push("/account/profile")}
            />
          )}
          {step === "menu" && restaurantSlug && (
            <MenuUploadStep
              slug={restaurantSlug}
              onComplete={handleComplete}
              onSkip={handleComplete}
            />
          )}
        </div>
      </div>
    </div>
  );
}
