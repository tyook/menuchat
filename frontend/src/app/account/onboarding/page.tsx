"use client";

import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useRequireAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import { useCompleteOnboarding } from "@/hooks/use-onboarding";
import { PreferencesStep } from "@/components/onboarding/preferences-step";
import { OwnerQuestionStep } from "@/components/onboarding/owner-question-step";
import { RestaurantDetailsStep } from "@/components/onboarding/restaurant-details-step";
import { MenuUploadStep } from "@/components/onboarding/menu-upload-step";
import { POSVendorStep } from "@/components/onboarding/pos-vendor-step";
import { PaymentSetupStep } from "@/components/onboarding/payment-setup-step";
import { cn } from "@/lib/utils";

type Step = "preferences" | "owner-question" | "restaurant-details" | "menu-upload" | "payment-setup" | "pos-vendor";

export default function OnboardingPage() {
  return (
    <Suspense fallback={null}>
      <OnboardingPageContent />
    </Suspense>
  );
}

function OnboardingPageContent() {
  const isAuthenticated = useRequireAuth();
  const router = useRouter();
  const { user } = useAuthStore();
  const completeMutation = useCompleteOnboarding();
  const [step, setStep] = useState<Step>("preferences");
  const [restaurantSlug, setRestaurantSlug] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const [stripeReturnError, setStripeReturnError] = useState(false);

  useEffect(() => {
    const isStripeReturn = searchParams.get("stripe_return") === "true" || searchParams.get("stripe_refresh") === "true";
    if (isStripeReturn && !restaurantSlug) {
      const savedSlug = sessionStorage.getItem("onboarding_restaurant_slug");
      if (savedSlug) {
        setRestaurantSlug(savedSlug);
        setStep("payment-setup");
      } else {
        setStripeReturnError(true);
      }
    }
  }, [searchParams]);

  if (!isAuthenticated || !user) return null;

  if (stripeReturnError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="max-w-md text-center space-y-4">
          <h1 className="text-2xl font-bold">Unable to Restore Session</h1>
          <p className="text-muted-foreground">
            Unable to restore your session. Please return to your profile and continue setup.
          </p>
          <a href="/account/profile" className="text-primary underline">
            Go to Profile
          </a>
        </div>
      </div>
    );
  }

  const totalSteps = step === "restaurant-details" || step === "menu-upload" || step === "payment-setup" || step === "pos-vendor" ? 6 : 2;
  const currentStep =
    step === "preferences" ? 1 :
    step === "owner-question" ? 2 :
    step === "restaurant-details" ? 3 :
    step === "menu-upload" ? 4 :
    step === "payment-setup" ? 5 : 6;

  const handleComplete = () => {
    completeMutation.mutate(undefined, {
      onSuccess: () => router.push(
        restaurantSlug ? `/account/restaurants/${restaurantSlug}/menu` : "/"
      ),
    });
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
          {step === "preferences" && (
            <PreferencesStep onNext={() => setStep("owner-question")} onSkip={() => setStep("owner-question")} />
          )}
          {step === "owner-question" && (
            <OwnerQuestionStep
              onYes={() => {
                if (user.owns_restaurant) {
                  handleComplete();
                } else {
                  setStep("restaurant-details");
                }
              }}
              onNo={handleComplete}
              onBack={() => setStep("preferences")}
            />
          )}
          {step === "restaurant-details" && (
            <RestaurantDetailsStep
              onCreated={(slug) => { setRestaurantSlug(slug); setStep("menu-upload"); }}
              onBack={() => setStep("owner-question")}
            />
          )}
          {step === "menu-upload" && restaurantSlug && (
            <MenuUploadStep slug={restaurantSlug} onComplete={() => setStep("payment-setup")} onSkip={() => setStep("payment-setup")} />
          )}
          {step === "payment-setup" && restaurantSlug && (
            <PaymentSetupStep slug={restaurantSlug} onComplete={() => setStep("pos-vendor")} />
          )}
          {step === "pos-vendor" && restaurantSlug && (
            <POSVendorStep slug={restaurantSlug} onComplete={handleComplete} onSkip={handleComplete} />
          )}
        </div>
      </div>
    </div>
  );
}
