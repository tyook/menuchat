"use client";

export function LoadingStep() {
  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center bg-background">
      {/* Ambient glow */}
      <div
        aria-hidden
        className="absolute w-[200px] h-[200px] bg-[radial-gradient(circle,rgba(217,119,6,0.15),transparent_70%)] rounded-full animate-glow-pulse pointer-events-none"
      />

      {/* Loading orb */}
      <div className="w-20 h-20 gradient-primary rounded-full animate-glow-pulse flex items-center justify-center glow-primary-lg">
        <div className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full bg-white/70 animate-pulse"
            style={{ animationDelay: "0s" }}
          />
          <span
            className="w-2 h-2 rounded-full bg-white/70 animate-pulse"
            style={{ animationDelay: "0.2s" }}
          />
          <span
            className="w-2 h-2 rounded-full bg-white/70 animate-pulse"
            style={{ animationDelay: "0.4s" }}
          />
        </div>
      </div>

      <p className="text-muted-foreground text-sm mt-6">Processing your order</p>
      <p className="text-foreground/70 text-lg font-medium mt-3">Understanding your order...</p>

      {/* Pulsing dots below text */}
      <div className="flex items-center gap-2 mt-4">
        <span
          className="w-2 h-2 rounded-full bg-primary/50 animate-pulse"
          style={{ animationDelay: "0s" }}
        />
        <span
          className="w-2 h-2 rounded-full bg-primary/50 animate-pulse"
          style={{ animationDelay: "0.2s" }}
        />
        <span
          className="w-2 h-2 rounded-full bg-primary/50 animate-pulse"
          style={{ animationDelay: "0.4s" }}
        />
      </div>
    </div>
  );
}
