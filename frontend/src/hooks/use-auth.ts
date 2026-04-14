"use client";

import { useEffect } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

export function useRequireAuth() {
  const { isAuthenticated, checkAuth } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    const redirectToLogin = () => {
      const currentUrl = searchParams.toString()
        ? `${pathname}?${searchParams.toString()}`
        : pathname;
      router.push(`/account/login?returnUrl=${encodeURIComponent(currentUrl)}`);
    };

    if (isAuthenticated === null) {
      checkAuth().then((ok) => {
        if (!ok) redirectToLogin();
      });
    } else if (isAuthenticated === false) {
      redirectToLogin();
    }
  }, [isAuthenticated, checkAuth, router, pathname, searchParams]);

  return isAuthenticated;
}

export function useRequireRestaurantAccess() {
  const auth = useRequireAuth();
  const { user } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (auth === true && user && !user.is_restaurant_owner) {
      router.push("/account/profile");
    }
  }, [auth, user, router]);

  return auth;
}
