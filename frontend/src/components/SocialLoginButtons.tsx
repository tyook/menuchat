"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { isNativePlatform, getPlatform } from "@/lib/native";

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
  buttonClassName?: string;
}

export function SocialLoginButtons({
  linkOrderId,
  onSuccess,
  onError,
  disabled,
  buttonClassName,
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
              prompt: (callback?: (notification: { isSkippedMoment: () => boolean }) => void) => void;
            };
          };
        }
      | undefined;

    if (!google) return;

    google.accounts.id.initialize({
      client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      callback: (response: { credential?: string }) => {
        googleCallbackRef.current?.(response);
      },
      ux_mode: "popup",
    });

    // Also render a hidden button as fallback
    if (googleBtnRef.current) {
      google.accounts.id.renderButton(googleBtnRef.current, {
        type: "icon",
        size: "large",
      });
    }

    setGoogleReady(true);
  }, []);

  useEffect(() => {
    setMounted(true);
    if (isNativePlatform()) return; // Skip web Google SDK initialization on native
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

  const handleGoogleClick = async () => {
    if (isNativePlatform()) {
      setLoading("google");
      try {
        const { GoogleAuth } = await import("@codetrix-studio/capacitor-google-auth");
        const result = await GoogleAuth.signIn();
        await googleLogin(result.authentication.idToken, linkOrderId);
        onSuccess?.();
      } catch (err) {
        onError?.(err instanceof Error ? err.message : "Google login failed");
      } finally {
        setLoading(null);
      }
      return;
    }

    if (!googleReady) {
      onError?.("Google Sign-In is still loading. Please try again.");
      return;
    }

    const google = (window as unknown as Record<string, unknown>).google as
      | {
          accounts: {
            id: {
              prompt: (callback?: (notification: { isSkippedMoment: () => boolean }) => void) => void;
            };
          };
        }
      | undefined;

    if (google) {
      // Use prompt() to trigger the Google Sign-In popup
      google.accounts.id.prompt((notification) => {
        if (notification.isSkippedMoment()) {
          // Fallback: try the hidden rendered button
          const btn = googleBtnRef.current?.querySelector("div[role='button']") as HTMLElement | null;
          if (btn) {
            btn.click();
          } else {
            onError?.("Google Sign-In was dismissed. Please try again or use email login.");
          }
        }
      });
    } else {
      onError?.("Google Sign-In is not available");
    }
  };

  const handleAppleLogin = async () => {
    if (isNativePlatform()) {
      setLoading("apple");
      try {
        const { SignInWithApple } = await import("@capacitor-community/apple-sign-in");
        const result = await SignInWithApple.authorize({
          clientId: process.env.NEXT_PUBLIC_APPLE_CLIENT_ID || "com.menuchat.qrordering",
          redirectURI: "",
          scopes: "email name",
        });
        const name = result.response.givenName
          ? `${result.response.givenName} ${result.response.familyName || ""}`.trim()
          : undefined;
        await appleLogin(result.response.identityToken, name, linkOrderId);
        onSuccess?.();
      } catch (err) {
        const errorObj = err as { error?: string };
        if (errorObj?.error !== "popup_closed_by_user") {
          onError?.(err instanceof Error ? err.message : "Apple login failed");
        }
      } finally {
        setLoading(null);
      }
      return;
    }

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
      <button
        className={`bg-card border border-border rounded-xl py-3 px-4 hover:bg-card/80 flex items-center justify-center gap-3 text-foreground transition-colors w-full disabled:opacity-50 disabled:cursor-not-allowed${buttonClassName ? ` ${buttonClassName}` : ""}`}
        onClick={handleGoogleClick}
        disabled={disabled || loading !== null || !mounted}
      >
        <svg className="h-5 w-5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
        </svg>
        {loading === "google" ? "Signing in..." : "Continue with Google"}
      </button>
      {(!isNativePlatform() || getPlatform() === "ios") && (
        <button
          className={`bg-card border border-border rounded-xl py-3 px-4 hover:bg-card/80 flex items-center justify-center gap-3 text-foreground transition-colors w-full disabled:opacity-50 disabled:cursor-not-allowed${buttonClassName ? ` ${buttonClassName}` : ""}`}
          onClick={handleAppleLogin}
          disabled={disabled || loading !== null || !mounted}
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
            <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.7 9.05 7.36c1.37.07 2.33.74 3.13.8 1.21-.23 2.37-.94 3.67-.84 1.58.13 2.76.79 3.52 2.01-3.31 1.98-2.6 5.98.48 7.26-.61 1.4-1.42 2.78-2.8 3.69zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
          </svg>
          {loading === "apple" ? "Signing in..." : "Continue with Apple"}
        </button>
      )}
    </div>
  );
}
