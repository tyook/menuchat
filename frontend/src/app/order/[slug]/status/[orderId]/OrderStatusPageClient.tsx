"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { SocialLoginButtons } from "@/components/SocialLoginButtons";
import { useAuthStore } from "@/stores/auth-store";
import { useOrderStatus } from "@/hooks/use-order-status";
import { OrderTracker } from "../../components/OrderTracker";

export default function OrderStatusPageClient() {
  const params = useParams<{ slug: string; orderId: string }>();
  const slug = params.slug;
  const orderId = params.orderId;

  const { data: order, isLoading, error } = useOrderStatus(slug, orderId);
  const { isAuthenticated, register, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const [showRegister, setShowRegister] = useState(false);
  const [registerForm, setRegisterForm] = useState({ email: "", password: "" });
  const [registerError, setRegisterError] = useState("");
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerSuccess, setRegisterSuccess] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegisterLoading(true);
    setRegisterError("");
    try {
      await register({
        email: registerForm.email,
        password: registerForm.password,
        link_order_id: orderId,
      });
      setRegisterSuccess(true);
      setShowRegister(false);
    } catch (err) {
      setRegisterError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegisterLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="flex items-center justify-center min-h-screen px-4 text-center">
        <p className="text-muted-foreground">Order not found.</p>
      </div>
    );
  }

  const isPosCollected = order.payment_status === "pos_collected";

  return (
    <main className="min-h-screen bg-background">
      <div className="relative min-h-screen flex flex-col items-center justify-center px-6 py-12 text-center">
        {/* Ambient success glow */}
        <div
          aria-hidden
          className="absolute w-[250px] h-[250px] bg-[radial-gradient(circle,rgba(34,197,94,0.12),transparent_70%)] rounded-full pointer-events-none"
        />

        {/* Success icon */}
        <div className="w-20 h-20 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mb-6">
          <CheckCircle className="text-green-400 w-10 h-10" />
        </div>

        <h2 className="text-2xl font-bold text-foreground mb-2">Order Submitted</h2>

        <p className="gradient-text text-lg font-semibold">
          #{orderId.slice(0, 8)}
        </p>

        {order.table_identifier && (
          <p className="text-muted-foreground text-sm mt-1">Table {order.table_identifier}</p>
        )}

        <p className="text-muted-foreground text-sm mt-2 max-w-xs">
          Your order has been sent to the kitchen.
          {isPosCollected && (
            <span className="block mt-1 font-medium text-foreground">
              Please pay at the counter.
            </span>
          )}
        </p>

        {/* Order details card */}
        {order.items && order.items.length > 0 && (
          <div className="glass-card rounded-2xl p-5 mt-8 w-full max-w-sm text-left">
            <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-3">
              Your Items
            </p>
            <div className="space-y-2">
              {order.items.map((item) => (
                <div key={item.id} className="flex justify-between items-center">
                  <span className="text-foreground/80 text-sm">
                    {item.quantity > 1 && (
                      <span className="text-muted-foreground text-xs mr-1">{item.quantity}x</span>
                    )}
                    {item.name}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    ${(Number(item.variant_price) * item.quantity).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
            <Separator className="my-3" />
            <div className="flex justify-between items-center font-semibold text-sm">
              <span className="text-foreground">Total</span>
              <span className="text-foreground">${Number(order.total_price).toFixed(2)}</span>
            </div>
          </div>
        )}

        {/* Live order tracker */}
        <div className="w-full max-w-sm mt-6">
          <OrderTracker slug={slug} orderId={orderId} />
        </div>

        {/* Account creation prompt */}
        {!isAuthenticated && !registerSuccess && (
          <div className="glass-card rounded-2xl p-6 mt-6 w-full max-w-sm text-left">
            <h3 className="text-lg font-semibold text-foreground mb-2">Save your order to an account?</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Create an account to track this order and save your preferences for next time.
            </p>

            {!showRegister ? (
              <div className="space-y-3">
                <SocialLoginButtons
                  linkOrderId={orderId}
                  onSuccess={() => setRegisterSuccess(true)}
                  onError={(err) => setRegisterError(err)}
                />
                {registerError && (
                  <p className="text-destructive text-sm">{registerError}</p>
                )}
                <div className="relative my-2">
                  <div className="absolute inset-0 flex items-center">
                    <Separator className="w-full" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-card px-2 text-muted-foreground">or</span>
                  </div>
                </div>
                <Button variant="outline" className="w-full" onClick={() => setShowRegister(true)}>
                  Sign up with email
                </Button>
              </div>
            ) : (
              <form onSubmit={handleRegister} className="space-y-3">
                <div>
                  <Label htmlFor="register-email">Email</Label>
                  <Input
                    id="register-email"
                    type="email"
                    value={registerForm.email}
                    onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="register-password">Password (min. 8 characters)</Label>
                  <Input
                    id="register-password"
                    type="password"
                    value={registerForm.password}
                    onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                    required
                    minLength={8}
                  />
                </div>
                {registerError && (
                  <p className="text-destructive text-sm">{registerError}</p>
                )}
                <div className="flex gap-2">
                  <Button type="submit" variant="gradient" className="flex-1" disabled={registerLoading}>
                    {registerLoading ? "Creating account..." : "Create Account"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setShowRegister(false);
                      setRegisterError("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* Success message after registration */}
        {registerSuccess && (
          <div className="glass-card rounded-2xl p-6 mt-6 w-full max-w-sm text-center">
            <div className="w-12 h-12 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mx-auto mb-3">
              <CheckCircle className="text-green-400 w-6 h-6" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-1">Account created!</h3>
            <p className="text-sm text-muted-foreground">
              Your order has been linked to your new account. You can now track all your orders.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
