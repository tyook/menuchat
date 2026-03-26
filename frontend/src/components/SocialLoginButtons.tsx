"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth-store";

interface AppleAuthResponse {
  authorization: { id_token: string };
  user?: { name: { firstName: string; lastName: string } };
}

interface AppleIDAuth {
  auth: {
    init: (config: Record<string, unknown>) => void;
    signIn: () => Promise<AppleAuthResponse>;
  };
}

interface SocialLoginButtonsProps {
  linkOrderId?: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
  disabled?: boolean;
}

export function SocialLoginButtons({
  linkOrderId,
  onSuccess,
  onError,
  disabled,
}: SocialLoginButtonsProps) {
  const { googleLogin, appleLogin } = useAuthStore();
  const [loading, setLoading] = useState<"google" | "apple" | null>(null);
  const [mounted, setMounted] = useState(false);
  const [googleReady, setGoogleReady] = useState(false);
  const googleBtnRef = useRef<HTMLDivElement>(null);

  // Stable callback ref so Google's initialize doesn't go stale
  const googleCallbackRef = useRef<(response: { credential?: string }) => void>();
  googleCallbackRef.current = async (response: { credential?: string }) => {
    if (!response.credential) {
      onError?.("Google login was cancelled or failed");
      setLoading(null);
      return;
    }
    try {
      setLoading("google");
      await googleLogin(response.credential, linkOrderId);
      onSuccess?.();
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Google login failed");
    } finally {
      setLoading(null);
    }
  };

  const initGoogle = useCallback(() => {
    const google = (window as unknown as Record<string, unknown>).google as
      | {
          accounts: {
            id: {
              initialize: (config: Record<string, unknown>) => void;
              renderButton: (element: HTMLElement, config: Record<string, unknown>) => void;
            };
          };
        }
      | undefined;

    if (!google || !googleBtnRef.current) return;

    google.accounts.id.initialize({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      callback: (response: { credential?: string }) => {
        googleCallbackRef.current?.(response);
      },
    });

    // Render a hidden Google button that we'll click programmatically
    google.accounts.id.renderButton(googleBtnRef.current, {
      type: "icon",
      size: "large",
    });

    setGoogleReady(true);
  }, []);

  useEffect(() => {
    setMounted(true);
    // GIS script may already be loaded (lazyOnload), or may still be loading
    if ((window as unknown as Record<string, unknown>).google) {
      initGoogle();
    } else {
      const interval = setInterval(() => {
        if ((window as unknown as Record<string, unknown>).google) {
          initGoogle();
          clearInterval(interval);
        }
      }, 200);
      return () => clearInterval(interval);
    }
  }, [initGoogle]);

  const handleGoogleClick = () => {
    if (!googleReady) {
      onError?.("Google Sign-In is still loading. Please try again.");
      return;
    }
    // Click the hidden Google rendered button to open the consent popup
    const iframe = googleBtnRef.current?.querySelector("div[role='button']") as HTMLElement | null;
    if (iframe) {
      iframe.click();
    } else {
      onError?.("Google Sign-In is not available");
    }
  };

  const handleAppleLogin = async () => {
    setLoading("apple");
    try {
      const AppleID = (window as unknown as Record<string, unknown>)
        .AppleID as AppleIDAuth | undefined;
      if (!AppleID) {
        onError?.("Apple Sign-In is not available");
        setLoading(null);
        return;
      }
      const response = await AppleID.auth.signIn();
      const token = response.authorization.id_token;
      const name = response.user
        ? `${response.user.name.firstName} ${response.user.name.lastName}`
        : undefined;
      await appleLogin(token, name, linkOrderId);
      onSuccess?.();
    } catch (err) {
      const errorObj = err as { error?: string };
      if (errorObj?.error !== "popup_closed_by_user") {
        onError?.(err instanceof Error ? err.message : "Apple login failed");
      }
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="space-y-2">
      {/* Hidden Google rendered button — clicked programmatically */}
      <div ref={googleBtnRef} className="h-0 w-0 overflow-hidden" />
      <Button
        variant="outline"
        className="w-full"
        onClick={handleGoogleClick}
        disabled={disabled || loading !== null || !mounted}
      >
        {loading === "google" ? "Signing in..." : "Continue with Google"}
      </Button>
      <Button
        variant="outline"
        className="w-full"
        onClick={handleAppleLogin}
        disabled={disabled || loading !== null || !mounted}
      >
        {loading === "apple" ? "Signing in..." : "Continue with Apple"}
      </Button>
    </div>
  );
}
