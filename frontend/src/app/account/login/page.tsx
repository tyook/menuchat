"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { SocialLoginButtons } from "@/components/SocialLoginButtons";
import { useAuthStore } from "@/stores/auth-store";

export default function CustomerLoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const getUser = () => useAuthStore.getState().user;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      const user = getUser();
      router.push(user?.onboarding_completed ? "/account/orders" : "/account/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 relative overflow-hidden">
      {/* Ambient glow orb */}
      <div className="absolute w-[300px] h-[300px] bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)] rounded-full animate-glow-pulse pointer-events-none" />

      <div className="glass-card rounded-2xl p-8 max-w-md w-full relative z-10">
        <h1 className="text-2xl font-bold mb-6 text-center gradient-text">Sign In</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <p className="text-destructive text-sm">{error}</p>}
          <Button type="submit" variant="gradient" size="lg" className="w-full" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </Button>
        </form>

        <div className="relative my-4">
          <div className="absolute inset-0 flex items-center">
            <Separator className="w-full" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-2 text-muted-foreground">or</span>
          </div>
        </div>

        <SocialLoginButtons
          onSuccess={() => {
            const user = getUser();
            router.push(user?.onboarding_completed ? "/account/orders" : "/account/onboarding");
          }}
          onError={(err) => setError(err)}
          buttonClassName="bg-card border border-border rounded-xl hover:bg-card/80"
        />

        <p className="text-sm text-center mt-4 text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/account/register" className="text-primary hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
