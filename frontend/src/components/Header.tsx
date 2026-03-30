"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CreditCard,
  ClipboardList,
  LogOut,
  ShoppingBag,
  Store,
  UtensilsCrossed,
  User as UserIcon,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function Header() {
  const router = useRouter();
  const { isAuthenticated, user, logout } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="container mx-auto flex h-14 items-center px-4">
        {/* Logo */}
        <Link href="/" className="mr-6 flex items-center gap-2 font-bold">
          <UtensilsCrossed className="h-5 w-5 text-primary" />
          <span className="gradient-text">QR Order</span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/account/orders">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <ShoppingBag className="h-4 w-4" />
              Orders
            </Button>
          </Link>
          <Link href="/account/profile">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <UserIcon className="h-4 w-4" />
              Profile
            </Button>
          </Link>
          {mounted && user?.is_restaurant_owner && (
            <Link href="/account/restaurants">
              <Button variant="ghost" size="sm" className="gap-1.5">
                <Store className="h-4 w-4" />
                My Restaurants
              </Button>
            </Link>
          )}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Auth section — render after mount to avoid hydration mismatch from localStorage */}
        {!mounted ? (
          <div className="h-9 w-9" />
        ) : isAuthenticated ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full">
                <UserIcon className="h-5 w-5" />
                <span className="sr-only">User menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {user && (
                <>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col gap-1">
                      <p className="text-sm font-medium">{user.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {user.email}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                </>
              )}
              {user?.onboarding_completed === false && (
                <>
                  <DropdownMenuItem
                    onClick={() => router.push("/account/onboarding")}
                  >
                    <ClipboardList className="mr-2 h-4 w-4" />
                    Complete your profile
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}
              <DropdownMenuItem onClick={() => router.push("/account/orders")}>
                <ShoppingBag className="mr-2 h-4 w-4" />
                Orders
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/account/profile")}>
                <UserIcon className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => router.push("/account/payment-methods")}
              >
                <CreditCard className="mr-2 h-4 w-4" />
                Payment Methods
              </DropdownMenuItem>
              {user?.is_restaurant_owner && (
                <DropdownMenuItem
                  onClick={() => router.push("/account/restaurants")}
                >
                  <Store className="mr-2 h-4 w-4" />
                  My Restaurants
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : (
          <Link href="/account/login">
            <Button size="sm" variant="gradient">Log in</Button>
          </Link>
        )}
      </div>
    </header>
  );
}
