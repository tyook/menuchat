"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useConnectOnboardingLink, useConnectOnboardingStatus } from "@/hooks/use-connect-onboarding";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2 } from "lucide-react";

interface PaymentSetupStepProps {
  slug: string;
  onComplete: () => void;
}

export function PaymentSetupStep({ slug, onComplete }: PaymentSetupStepProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { toast } = useToast();

  const isStripeReturn = searchParams.get("stripe_return") === "true";
  const isStripeRefresh = searchParams.get("stripe_refresh") === "true";
  const shouldCheckStatus = isStripeReturn || isStripeRefresh;

  const connectLink = useConnectOnboardingLink(slug);
  const { data: status, isLoading: statusLoading } = useConnectOnboardingStatus(slug, shouldCheckStatus);
  const [hasCheckedStatus, setHasCheckedStatus] = useState(false);

  useEffect(() => {
    if (status && shouldCheckStatus && !hasCheckedStatus) {
      setHasCheckedStatus(true);
      // Clean query params from URL
      router.replace(pathname);
    }
  }, [status, shouldCheckStatus, hasCheckedStatus, router, pathname]);

  const isComplete = status?.onboarding_complete ?? false;

  const handleSetup = () => {
    const baseUrl = window.location.origin;
    const returnUrl = `${baseUrl}${pathname}?stripe_return=true`;
    const refreshUrl = `${baseUrl}${pathname}?stripe_refresh=true`;

    sessionStorage.setItem("onboarding_restaurant_slug", slug);

    connectLink.mutate(
      { returnUrl, refreshUrl },
      {
        onSuccess: (data) => {
          window.location.href = data.url;
        },
        onError: (err) => {
          toast({
            title: "Failed to start payment setup",
            description: err instanceof Error ? err.message : "Unknown error",
            variant: "destructive",
          });
        },
      }
    );
  };

  // Loading state while checking status after return
  if (shouldCheckStatus && statusLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Verifying Payment Setup</h1>
          <p className="text-muted-foreground mt-1">Checking your Stripe account status...</p>
        </div>
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      </div>
    );
  }

  // Complete state
  if (isComplete) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Payments Ready</h1>
          <p className="text-muted-foreground mt-1">
            Your Stripe account is set up and ready to receive payouts.
          </p>
        </div>
        <div className="flex flex-col items-center gap-3 py-6">
          <CheckCircle2 className="h-12 w-12 text-green-600" />
          <p className="text-green-600 font-medium">Payment setup complete</p>
        </div>
        <div className="flex gap-3 pt-2">
          <Button onClick={onComplete} className="flex-1">
            Continue
          </Button>
        </div>
      </div>
    );
  }

  // Returned but incomplete
  if (isStripeReturn && hasCheckedStatus && !isComplete) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Payment Setup Incomplete</h1>
          <p className="text-muted-foreground mt-1">
            It looks like the payment setup was not completed. Please try again to finish connecting your bank account.
          </p>
        </div>
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleSetup}
            className="flex-1"
            disabled={connectLink.isPending}
          >
            {connectLink.isPending ? "Redirecting..." : "Try Again"}
          </Button>
        </div>
      </div>
    );
  }

  // Session expired / refresh
  if (isStripeRefresh && hasCheckedStatus && !isComplete) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Session Expired</h1>
          <p className="text-muted-foreground mt-1">
            Your payment setup session expired. Please try again.
          </p>
        </div>
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleSetup}
            className="flex-1"
            disabled={connectLink.isPending}
          >
            {connectLink.isPending ? "Redirecting..." : "Set Up Payments"}
          </Button>
        </div>
      </div>
    );
  }

  // Not started (default)
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Set Up Payments</h1>
        <p className="text-muted-foreground mt-1">
          Connect your bank account to receive payouts for QR orders.
          You will be redirected to Stripe to complete setup.
        </p>
      </div>
      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleSetup}
          className="flex-1"
          disabled={connectLink.isPending}
        >
          {connectLink.isPending ? "Redirecting to Stripe..." : "Set Up Payments"}
        </Button>
      </div>
    </div>
  );
}
