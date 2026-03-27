"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRequireAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import { useCompleteOnboarding } from "@/hooks/use-onboarding";
import { PreferencesStep } from "@/components/onboarding/preferences-step";
import { OwnerQuestionStep } from "@/components/onboarding/owner-question-step";
import { RestaurantDetailsStep } from "@/components/onboarding/restaurant-details-step";
import { MenuUploadStep } from "@/components/onboarding/menu-upload-step";

type Step = "preferences" | "owner-question" | "restaurant-details" | "menu-upload";

export default function OnboardingPage() {
  const isAuthenticated = useRequireAuth();
  const router = useRouter();
  const { user } = useAuthStore();
  const completeMutation = useCompleteOnboarding();
  const [step, setStep] = useState<Step>("preferences");
  const [restaurantSlug, setRestaurantSlug] = useState<string | null>(null);

  if (!isAuthenticated || !user) return null;

  const totalSteps = step === "restaurant-details" || step === "menu-upload" ? 4 : 2;
  const currentStep =
    step === "preferences" ? 1 :
    step === "owner-question" ? 2 :
    step === "restaurant-details" ? 3 : 4;

  const handleComplete = () => {
    completeMutation.mutate(undefined, {
      onSuccess: () => router.push(
        restaurantSlug ? `/account/restaurants/${restaurantSlug}/menu` : "/"
      ),
    });
  };

  const progressPercent = (currentStep / totalSteps) * 100;

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <div className="mb-6">
        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Step {currentStep} of {totalSteps}
        </p>
      </div>

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
        <MenuUploadStep slug={restaurantSlug} onComplete={handleComplete} onSkip={handleComplete} />
      )}
    </div>
  );
}
