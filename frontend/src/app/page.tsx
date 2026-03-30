import Link from "next/link";
import {
  UtensilsCrossed,
  Store,
  QrCode,
  Mic,
  CheckCircle,
  BarChart3,
  MonitorCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* ───────────────────── HERO ───────────────────── */}
      <section className="relative isolate overflow-hidden min-h-screen flex flex-col items-center justify-center px-6 text-center">
        {/* ambient glow orbs */}
        <div
          aria-hidden
          className="animate-glow-pulse absolute top-1/4 left-1/4 -z-10 h-[350px] w-[350px] rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]"
        />
        <div
          aria-hidden
          className="animate-glow-pulse absolute bottom-1/4 right-1/4 -z-10 h-[250px] w-[250px] rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]"
          style={{ animationDelay: "2s" }}
        />

        {/* floating particles */}
        <div
          aria-hidden
          className="animate-float-particle absolute top-[20%] left-[15%] h-[4px] w-[4px] bg-violet-400/30 rounded-full"
          style={{ animationDelay: "0s" }}
        />
        <div
          aria-hidden
          className="animate-float-particle absolute top-[35%] right-[18%] h-[3px] w-[3px] bg-violet-400/30 rounded-full"
          style={{ animationDelay: "1s" }}
        />
        <div
          aria-hidden
          className="animate-float-particle absolute bottom-[30%] left-[25%] h-[5px] w-[5px] bg-violet-400/30 rounded-full"
          style={{ animationDelay: "2s" }}
        />
        <div
          aria-hidden
          className="animate-float-particle absolute bottom-[20%] right-[20%] h-[3px] w-[3px] bg-violet-400/30 rounded-full"
          style={{ animationDelay: "0.5s" }}
        />
        <div
          aria-hidden
          className="animate-float-particle absolute top-[60%] left-[10%] h-[4px] w-[4px] bg-violet-400/30 rounded-full"
          style={{ animationDelay: "1.5s" }}
        />

        {/* logo */}
        <div className="animate-fade-in-up flex items-center gap-3 mb-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
            <UtensilsCrossed className="h-7 w-7 text-primary" />
          </div>
          <span className="text-2xl font-bold tracking-tight text-foreground">
            QR Order
          </span>
        </div>

        {/* headline */}
        <h1 className="animate-fade-in-up-delay-1 max-w-2xl text-4xl md:text-5xl font-bold tracking-tight text-foreground leading-[1.15]">
          The smarter way to{" "}
          <br className="hidden sm:block" />
          <span className="gradient-text">dine & order</span>
        </h1>

        {/* subtitle */}
        <p className="animate-fade-in-up-delay-2 mt-6 text-muted-foreground max-w-md mx-auto text-lg leading-relaxed">
          AI-powered ordering that speaks every language. Scan a QR code and
          let your voice do the rest.
        </p>

        {/* CTA buttons */}
        <div className="animate-fade-in-up-delay-3 mt-10 flex flex-col sm:flex-row gap-4">
          <Button asChild variant="gradient" size="lg">
            <Link href="/demo">Try a Demo</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/account/register">
              <Store className="mr-2 h-4 w-4" />
              I&apos;m a Restaurant Owner
            </Link>
          </Button>
        </div>
      </section>

      {/* ──────────── HOW IT WORKS ──────────── */}
      <section className="relative px-6 py-24 md:py-32">
        <div className="mx-auto max-w-5xl">
          {/* section header */}
          <div className="mb-16 text-center">
            <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-3">
              Simple by design
            </p>
            <h2 className="text-2xl md:text-3xl font-bold text-foreground">
              How It Works
            </h2>
          </div>

          {/* step cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 items-start">
            {/* Step 1 */}
            <div className="glass-card rounded-2xl p-7 text-center">
              <div className="flex justify-center mb-5">
                <div className="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center">
                  <QrCode className="h-6 w-6 text-primary" />
                </div>
              </div>
              <p className="text-[11px] uppercase tracking-[3px] text-violet-400 mb-2">
                Step 1
              </p>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Scan QR Code
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Point your phone at the QR code at your table or counter to
                open the menu instantly.
              </p>
            </div>

            {/* arrow connector (desktop) */}
            <div className="hidden sm:flex absolute left-[calc(33%-20px)] top-[calc(50%+80px)] items-center pointer-events-none">
              {/* visual spacing handled by grid */}
            </div>

            {/* Step 2 */}
            <div className="glass-card rounded-2xl p-7 text-center">
              <div className="flex justify-center mb-5">
                <div className="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center">
                  <Mic className="h-6 w-6 text-primary" />
                </div>
              </div>
              <p className="text-[11px] uppercase tracking-[3px] text-violet-400 mb-2">
                Step 2
              </p>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Talk to AI
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Speak or type your order in any language. Our AI understands
                you perfectly.
              </p>
            </div>

            {/* Step 3 */}
            <div className="glass-card rounded-2xl p-7 text-center">
              <div className="flex justify-center mb-5">
                <div className="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center">
                  <CheckCircle className="h-6 w-6 text-primary" />
                </div>
              </div>
              <p className="text-[11px] uppercase tracking-[3px] text-violet-400 mb-2">
                Step 3
              </p>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Order Confirmed
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Pay instantly on your phone. Your order goes straight to the
                kitchen — no waiting.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ──────────── FOR RESTAURANT OWNERS ──────────── */}
      <section className="relative px-6 py-24 md:py-32">
        <div className="mx-auto max-w-5xl">
          {/* section header */}
          <div className="mb-16 text-center">
            <p className="text-[11px] uppercase tracking-[3px] text-muted-foreground mb-3">
              Built for operators
            </p>
            <h2 className="text-2xl md:text-3xl font-bold text-foreground">
              For Restaurant Owners
            </h2>
          </div>

          {/* feature cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {/* AI Menu Management */}
            <div className="glass-card rounded-2xl p-7">
              <div className="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center mb-5">
                <Sparkles className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                AI-Powered Menu Management
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Update your menu in seconds. AI handles translations, dietary
                tags, and item descriptions automatically.
              </p>
            </div>

            {/* Kitchen Display */}
            <div className="glass-card rounded-2xl p-7">
              <div className="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center mb-5">
                <MonitorCheck className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Real-Time Kitchen Display
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Orders appear instantly on your kitchen screen. No more
                lost tickets or miscommunication.
              </p>
            </div>

            {/* Analytics */}
            <div className="glass-card rounded-2xl p-7">
              <div className="w-14 h-14 bg-primary/10 border border-primary/20 rounded-2xl flex items-center justify-center mb-5">
                <BarChart3 className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                Analytics &amp; Insights
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                See your best-selling items, peak hours, and revenue trends at
                a glance. Data-driven decisions made easy.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ──────────── CLOSING CTA ──────────── */}
      <section className="relative isolate overflow-hidden px-6 py-24 md:py-32 text-center">
        {/* ambient glow orbs */}
        <div
          aria-hidden
          className="animate-glow-pulse absolute top-0 left-1/3 -z-10 h-[300px] w-[300px] rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]"
        />
        <div
          aria-hidden
          className="animate-glow-pulse absolute bottom-0 right-1/3 -z-10 h-[250px] w-[250px] rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]"
          style={{ animationDelay: "2s" }}
        />

        <div className="mx-auto max-w-2xl">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">
            Ready to Transform{" "}
            <span className="gradient-text">Your Restaurant?</span>
          </h2>
          <p className="mt-4 text-muted-foreground text-lg">
            Join restaurants already saving time, cutting costs, and delighting
            customers with QR Order.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
            <Button asChild variant="gradient" size="lg">
              <Link href="/demo">Try a Demo</Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/account/register">
                <Store className="mr-2 h-4 w-4" />
                I&apos;m a Restaurant Owner
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* ──────────── FOOTER ──────────── */}
      <footer className="border-t border-border px-6 py-8">
        <div className="mx-auto max-w-5xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
              <UtensilsCrossed className="h-4 w-4 text-primary" />
            </div>
            <span className="font-semibold gradient-text">QR Order</span>
          </div>
          <p className="text-sm text-muted-foreground">
            AI-powered ordering for modern restaurants
          </p>
        </div>
      </footer>
    </div>
  );
}
