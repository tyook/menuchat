# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the entire frontend from warm amber/cool slate to a "Soft Dark & Elevated" customer theme, "Clean & Airy" admin theme, and extra-dark kitchen theme.

**Architecture:** Theme-first approach — update CSS variables and design tokens first, then override shadcn/ui components, then sweep through each page. The existing `data-theme` attribute system and CSS variable architecture stays intact; we're changing the values and adding a third "kitchen" theme.

**Tech Stack:** Next.js 14, Tailwind CSS 3.4, shadcn/ui (New York), CSS custom properties (HSL), class-variance-authority, tailwindcss-animate

---

## File Structure

**Modified files:**
- `frontend/src/app/globals.css` — New color tokens, animations, utility classes for all 3 themes
- `frontend/tailwind.config.ts` — Updated border radius, new animation keyframes, gradient color tokens
- `frontend/src/components/ThemeProvider.tsx` — Add "kitchen" theme type and routing
- `frontend/src/components/ui/button.tsx` — New gradient variant, updated border radius
- `frontend/src/components/ui/card.tsx` — Updated border radius, glass-card support
- `frontend/src/components/ui/input.tsx` — Updated border radius and focus ring
- `frontend/src/components/ui/badge.tsx` — Updated border radius, new status variants
- `frontend/src/components/ui/dialog.tsx` — Glass styling for customer theme
- `frontend/src/components/ui/tabs.tsx` — Updated active indicator styling
- `frontend/src/components/Header.tsx` — Restyle for dark/light themes
- `frontend/src/app/page.tsx` — Full landing page redesign
- `frontend/src/app/order/[slug]/components/WelcomeStep.tsx` — Dark welcome screen
- `frontend/src/app/order/[slug]/components/InputStep.tsx` — Futuristic AI voice input
- `frontend/src/app/order/[slug]/components/LoadingStep.tsx` — Dark loading state
- `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx` — Dark order review
- `frontend/src/app/order/[slug]/components/PaymentStep.tsx` — Dark payment flow
- `frontend/src/app/order/[slug]/components/SubmittedStep.tsx` — Dark submitted state
- `frontend/src/app/account/login/page.tsx` — Dark auth styling
- `frontend/src/app/account/register/page.tsx` — Dark auth styling
- `frontend/src/app/account/onboarding/page.tsx` — Dark auth styling
- `frontend/src/app/account/restaurants/[slug]/menu/page.tsx` — Light admin styling
- `frontend/src/app/account/restaurants/[slug]/orders/page.tsx` — Light admin styling
- `frontend/src/app/account/restaurants/[slug]/settings/page.tsx` — Light admin styling
- `frontend/src/app/account/restaurants/[slug]/billing/page.tsx` — Light admin styling
- `frontend/src/app/account/restaurants/[slug]/sync-logs/page.tsx` — Light admin styling
- `frontend/src/app/account/restaurants/[slug]/settings/integrations/page.tsx` — Light admin styling
- `frontend/src/app/account/restaurants/page.tsx` — Light admin restaurant list
- `frontend/src/components/onboarding/preferences-step.tsx` — Dark onboarding styling
- `frontend/src/components/onboarding/owner-question-step.tsx` — Dark onboarding styling
- `frontend/src/components/onboarding/restaurant-details-step.tsx` — Dark onboarding styling
- `frontend/src/components/onboarding/menu-upload-step.tsx` — Dark onboarding styling
- `frontend/src/components/onboarding/onboarding-banner.tsx` — Dark onboarding styling
- `frontend/src/components/PreferencesDialog.tsx` — Glass dialog styling
- `frontend/src/components/SocialLoginButtons.tsx` — Glass-style buttons
- `frontend/src/components/menu-upload-modal.tsx` — Glass dialog styling
- `frontend/src/components/parsed-menu-editor.tsx` — Admin theme styling
- `frontend/src/app/kitchen/[slug]/page.tsx` — Extra-dark kitchen styling

---

## Chunk 1: Design Tokens & Component Foundation

### Task 1: Update CSS custom properties in globals.css

**Files:**
- Modify: `frontend/src/app/globals.css`

**Note:** Line numbers below refer to the original file before any edits. Use the content-based descriptions (e.g., "the `[data-theme="customer"]` block") to locate sections, not line numbers, since earlier steps shift later lines.

- [ ] **Step 1: Replace customer theme light mode (the `[data-theme="customer"], :root` block) with dark "Soft Dark & Elevated" values**

Replace the `[data-theme="customer"], :root` block with:

```css
[data-theme="customer"],
:root {
  --background: 222 47% 11%;
  --foreground: 210 40% 96%;
  --card: 217 33% 17%;
  --card-foreground: 210 40% 96%;
  --popover: 217 33% 17%;
  --popover-foreground: 210 40% 96%;
  --primary: 263 70% 50%;
  --primary-foreground: 0 0% 100%;
  --secondary: 215 25% 27%;
  --secondary-foreground: 210 40% 96%;
  --muted: 217 33% 17%;
  --muted-foreground: 215 20% 65%;
  --accent: 217 33% 17%;
  --accent-foreground: 210 40% 96%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 98%;
  --border: 215 20% 18%;
  --input: 215 20% 20%;
  --ring: 263 70% 50%;
  --chart-1: 263 70% 55%;
  --chart-2: 232 70% 65%;
  --chart-3: 280 65% 60%;
  --chart-4: 160 60% 45%;
  --chart-5: 340 75% 55%;

  /* Gradient tokens (not usable in hsl() but referenced in utility classes) */
  --primary-from: #7c3aed;
  --primary-to: #6366f1;
  --accent-from: #f0abfc;
  --accent-to: #818cf8;
  --success: #22c55e;
}
```

- [ ] **Step 2: Remove customer dark mode block**

Delete the entire `.dark [data-theme="customer"], .dark:root { ... }` block — the customer theme is now always dark.

- [ ] **Step 3: Replace admin theme light mode (the `[data-theme="admin"]` block) with "Clean & Airy" values**

Replace the `[data-theme="admin"]` block with:

```css
[data-theme="admin"] {
  --background: 210 40% 98%;
  --foreground: 222 47% 11%;
  --card: 0 0% 100%;
  --card-foreground: 222 47% 11%;
  --popover: 0 0% 100%;
  --popover-foreground: 222 47% 11%;
  --primary: 263 70% 50%;
  --primary-foreground: 0 0% 100%;
  --secondary: 210 40% 96%;
  --secondary-foreground: 222 47% 11%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --accent: 214 100% 97%;
  --accent-foreground: 222 47% 11%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 98%;
  --border: 214 32% 91%;
  --input: 214 32% 91%;
  --ring: 263 70% 50%;
  --chart-1: 263 70% 55%;
  --chart-2: 173 58% 39%;
  --chart-3: 197 37% 24%;
  --chart-4: 43 74% 66%;
  --chart-5: 27 87% 67%;

  --primary-from: #7c3aed;
  --primary-to: #6366f1;
  --accent-from: #f0abfc;
  --accent-to: #818cf8;
  --success: #22c55e;
}
```

- [ ] **Step 4: Remove admin dark mode block**

Delete the entire `.dark [data-theme="admin"] { ... }` block — admin is always light.

- [ ] **Step 5: Add kitchen theme block**

Add after the admin theme:

```css
/* ══════════════════════════════════════════════
   KITCHEN THEME — extra dark for low-light
   ══════════════════════════════════════════════ */
[data-theme="kitchen"] {
  --background: 222 55% 5%;
  --foreground: 210 40% 96%;
  --card: 222 47% 8%;
  --card-foreground: 210 40% 96%;
  --popover: 222 47% 8%;
  --popover-foreground: 210 40% 96%;
  --primary: 263 70% 50%;
  --primary-foreground: 0 0% 100%;
  --secondary: 222 40% 12%;
  --secondary-foreground: 210 40% 96%;
  --muted: 222 40% 12%;
  --muted-foreground: 215 20% 55%;
  --accent: 222 40% 12%;
  --accent-foreground: 210 40% 96%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 98%;
  --border: 222 30% 14%;
  --input: 222 30% 16%;
  --ring: 263 70% 50%;
  --chart-1: 263 70% 55%;
  --chart-2: 48 96% 53%;
  --chart-3: 142 71% 45%;
  --chart-4: 0 84% 60%;
  --chart-5: 217 91% 60%;

  --primary-from: #7c3aed;
  --primary-to: #6366f1;
  --accent-from: #f0abfc;
  --accent-to: #818cf8;
  --success: #22c55e;
}
```

- [ ] **Step 6: Update the --radius default**

Change `:root { --radius: 0.5rem; }` to `:root { --radius: 0.75rem; }`.

- [ ] **Step 7: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors. Pages will look different but functional.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat(design): replace color tokens with Soft Dark, Clean Airy, and Kitchen themes"
```

### Task 2: Add new animations and utility classes to globals.css

**Files:**
- Modify: `frontend/src/app/globals.css` (animation section, lines 11-69)

- [ ] **Step 1: Replace the existing keyframes and animation classes (lines 11-69) with the expanded set**

Replace everything between the `text-balance` utility and the `@layer base` block:

```css
/* ── Animations ── */
@keyframes glow-pulse {
  0%, 100% {
    opacity: 0.4;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

@keyframes fade-in-up {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

@keyframes pulse-ring {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.4;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.4);
    opacity: 0;
  }
}

@keyframes waveform {
  0%, 100% {
    height: 12px;
  }
  50% {
    height: var(--wave-height, 32px);
  }
}

@keyframes blink-cursor {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

@keyframes slide-in-top {
  from {
    opacity: 0;
    transform: translateY(-16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes float-particle {
  0%, 100% {
    transform: translateY(0) translateX(0);
    opacity: 0.3;
  }
  25% {
    opacity: 0.6;
  }
  50% {
    transform: translateY(-12px) translateX(4px);
    opacity: 0.3;
  }
  75% {
    opacity: 0.5;
  }
}

/* Animation utility classes */
.animate-glow-pulse {
  animation: glow-pulse 4s ease-in-out infinite;
}

.animate-fade-in-up {
  animation: fade-in-up 0.7s ease-out forwards;
  opacity: 0;
}

.animate-fade-in-up-delay-1 {
  animation: fade-in-up 0.7s ease-out 0.15s forwards;
  opacity: 0;
}

.animate-fade-in-up-delay-2 {
  animation: fade-in-up 0.7s ease-out 0.3s forwards;
  opacity: 0;
}

.animate-fade-in-up-delay-3 {
  animation: fade-in-up 0.7s ease-out 0.45s forwards;
  opacity: 0;
}

.animate-float {
  animation: float 3s ease-in-out infinite;
}

.animate-pulse-ring {
  animation: pulse-ring 2s ease-out infinite;
}

.animate-pulse-ring-delayed {
  animation: pulse-ring 2s ease-out 0.5s infinite;
}

.animate-waveform {
  animation: waveform 1.2s ease-in-out infinite;
}

.animate-blink-cursor {
  animation: blink-cursor 1s step-end infinite;
}

.animate-slide-in-top {
  animation: slide-in-top 0.4s ease-out forwards;
  opacity: 0;
}

.animate-float-particle {
  animation: float-particle 4s ease-in-out infinite;
}

/* ── Utility classes ── */
.gradient-text {
  background: linear-gradient(135deg, var(--accent-from), var(--accent-to));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.gradient-primary {
  background: linear-gradient(135deg, var(--primary-from), var(--primary-to));
}

.glass-card {
  background: hsl(var(--card) / 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
}

.glow-primary {
  box-shadow: 0 0 30px rgba(124, 58, 237, 0.2);
}

.glow-primary-lg {
  box-shadow: 0 0 60px rgba(124, 58, 237, 0.25);
}

.ambient-orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
```

- [ ] **Step 2: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat(design): add new animations and utility classes for redesign"
```

### Task 3: Update Tailwind config

**Files:**
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Add gradient color tokens and update border radius**

Replace the `theme.extend` object:

```typescript
extend: {
  colors: {
    background: 'hsl(var(--background))',
    foreground: 'hsl(var(--foreground))',
    card: {
      DEFAULT: 'hsl(var(--card))',
      foreground: 'hsl(var(--card-foreground))'
    },
    popover: {
      DEFAULT: 'hsl(var(--popover))',
      foreground: 'hsl(var(--popover-foreground))'
    },
    primary: {
      DEFAULT: 'hsl(var(--primary))',
      foreground: 'hsl(var(--primary-foreground))'
    },
    secondary: {
      DEFAULT: 'hsl(var(--secondary))',
      foreground: 'hsl(var(--secondary-foreground))'
    },
    muted: {
      DEFAULT: 'hsl(var(--muted))',
      foreground: 'hsl(var(--muted-foreground))'
    },
    accent: {
      DEFAULT: 'hsl(var(--accent))',
      foreground: 'hsl(var(--accent-foreground))'
    },
    destructive: {
      DEFAULT: 'hsl(var(--destructive))',
      foreground: 'hsl(var(--destructive-foreground))'
    },
    border: 'hsl(var(--border))',
    input: 'hsl(var(--input))',
    ring: 'hsl(var(--ring))',
    chart: {
      '1': 'hsl(var(--chart-1))',
      '2': 'hsl(var(--chart-2))',
      '3': 'hsl(var(--chart-3))',
      '4': 'hsl(var(--chart-4))',
      '5': 'hsl(var(--chart-5))'
    },
    violet: {
      glow: 'rgba(124, 58, 237, 0.2)',
    },
    success: 'var(--success)',
  },
  borderRadius: {
    xl: 'calc(var(--radius) + 8px)',
    lg: 'var(--radius)',
    md: 'calc(var(--radius) - 2px)',
    sm: 'calc(var(--radius) - 4px)'
  },
  animation: {
    'pulse-ring': 'pulse-ring 2s ease-out infinite',
    'waveform': 'waveform 1.2s ease-in-out infinite',
    'blink-cursor': 'blink-cursor 1s step-end infinite',
    'slide-in-top': 'slide-in-top 0.4s ease-out forwards',
    'float-particle': 'float-particle 4s ease-in-out infinite',
  },
  keyframes: {
    'pulse-ring': {
      '0%': { transform: 'translate(-50%, -50%) scale(1)', opacity: '0.4' },
      '100%': { transform: 'translate(-50%, -50%) scale(1.4)', opacity: '0' },
    },
    'waveform': {
      '0%, 100%': { height: '12px' },
      '50%': { height: 'var(--wave-height, 32px)' },
    },
    'blink-cursor': {
      '0%, 100%': { opacity: '1' },
      '50%': { opacity: '0' },
    },
    'slide-in-top': {
      from: { opacity: '0', transform: 'translateY(-16px)' },
      to: { opacity: '1', transform: 'translateY(0)' },
    },
    'float-particle': {
      '0%, 100%': { transform: 'translateY(0) translateX(0)', opacity: '0.3' },
      '25%': { opacity: '0.6' },
      '50%': { transform: 'translateY(-12px) translateX(4px)', opacity: '0.3' },
      '75%': { opacity: '0.5' },
    },
  },
}
```

- [ ] **Step 2: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat(design): update Tailwind config with new tokens, radii, and animations"
```

### Task 4: Update ThemeProvider with kitchen theme

**Files:**
- Modify: `frontend/src/components/ThemeProvider.tsx`

- [ ] **Step 1: Add "kitchen" to the ThemeName type and update resolveTheme**

Replace the full file content:

```tsx
"use client";

import { createContext, useContext, useMemo } from "react";
import { usePathname } from "next/navigation";

type ThemeName = "customer" | "admin" | "kitchen";

interface ThemeContextValue {
  theme: ThemeName;
}

const ThemeContext = createContext<ThemeContextValue>({ theme: "customer" });

function resolveTheme(pathname: string): ThemeName {
  if (pathname.startsWith("/kitchen")) {
    return "kitchen";
  }
  if (pathname.startsWith("/account/restaurants")) {
    return "admin";
  }
  return "customer";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const theme = resolveTheme(pathname);

  const value = useMemo(() => ({ theme }), [theme]);

  return (
    <ThemeContext.Provider value={value}>
      <div data-theme={theme} className="contents">
        {children}
      </div>
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
```

Note: `/kitchen` must be checked before `/account/restaurants` since the order matters for prefix matching.

- [ ] **Step 2: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ThemeProvider.tsx
git commit -m "feat(design): add kitchen theme to ThemeProvider"
```

### Task 5: Update shadcn/ui Button component

**Files:**
- Modify: `frontend/src/components/ui/button.tsx`

- [ ] **Step 1: Update buttonVariants with new border radius and add gradient variant**

Replace the `buttonVariants` definition:

```tsx
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        gradient:
          "gradient-primary text-white shadow-md glow-primary hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-12 rounded-xl px-8 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)
```

- [ ] **Step 2: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/button.tsx
git commit -m "feat(design): update Button with gradient variant and new sizing"
```

### Task 6: Update shadcn/ui Card, Input, and Badge components

**Files:**
- Modify: `frontend/src/components/ui/card.tsx`
- Modify: `frontend/src/components/ui/input.tsx`
- Modify: `frontend/src/components/ui/badge.tsx`

- [ ] **Step 1: Update Card base class**

In `card.tsx`, change the Card className from:
```
"rounded-xl border bg-card text-card-foreground shadow"
```
to:
```
"rounded-2xl border bg-card text-card-foreground shadow-sm"
```

- [ ] **Step 2: Update Input base class**

In `input.tsx`, change the Input className from:
```
"flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
```
to:
```
"flex h-10 w-full rounded-xl border border-input bg-card px-4 py-2 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm"
```

- [ ] **Step 3: Update Badge border radius**

In `badge.tsx`, change the base class from:
```
"inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
```
to:
```
"inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
```

- [ ] **Step 4: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/card.tsx frontend/src/components/ui/input.tsx frontend/src/components/ui/badge.tsx
git commit -m "feat(design): update Card, Input, Badge with new radii and styling"
```

### Task 7: Update Header component

**Files:**
- Modify: `frontend/src/components/Header.tsx`

- [ ] **Step 1: Read the current Header.tsx**

Read: `frontend/src/components/Header.tsx`

- [ ] **Step 2: Update the header styling**

The header already uses theme tokens for most colors. Make these specific changes:

1. Update the header container class on line 41 from:
```
"sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
```
to:
```
"sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-xl"
```

2. Update the logo on line 44 — add `gradient-text` to the span:
```tsx
<Link href="/" className="mr-6 flex items-center gap-2 font-bold">
  <UtensilsCrossed className="h-5 w-5 text-primary" />
  <span className="gradient-text">QR Order</span>
</Link>
```

3. Update the login button on line 143 to use gradient variant:
```tsx
<Button size="sm" variant="gradient">Log in</Button>
```

- [ ] **Step 3: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Header.tsx
git commit -m "feat(design): restyle Header for dark/light theme support"
```

---

## Chunk 2: Landing Page Redesign

### Task 8: Redesign the landing page hero section

**Files:**
- Modify: `frontend/src/app/page.tsx` (lines ~82-141)

- [ ] **Step 1: Read the current landing page**

Read: `frontend/src/app/page.tsx`

- [ ] **Step 2: Rewrite the hero section**

Replace the current hero section with a dark atmospheric design:

- Dark background (`bg-background`) — inherited from customer theme tokens
- Ambient purple glow orbs: two `div` elements positioned absolutely with `bg-[radial-gradient(circle,rgba(124,58,237,0.12),transparent_70%)]` and large dimensions (250-350px), `rounded-full`, `animate-glow-pulse`
- Navigation bar: logo with `gradient-text` class, nav links in `text-muted-foreground`, sign-in button with `bg-card border border-border rounded-xl`
- Floating particle dots: 3-5 small `div` elements (3-5px) with `bg-violet-400/30 rounded-full animate-float-particle` and different animation delays
- Headline: large text (text-4xl md:text-5xl), `font-bold tracking-tight text-foreground`, second line uses `gradient-text`
- Subtitle: `text-muted-foreground max-w-md mx-auto`
- Dual CTAs: primary `Button variant="gradient" size="lg"` + secondary `Button variant="outline" size="lg"`

- [ ] **Step 3: Verify the page renders**

Run: `cd frontend && npm run dev`
Check: Open http://localhost:3000 and verify the hero section is dark with purple glows and gradient text.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat(design): redesign landing page hero with dark atmospheric style"
```

### Task 9: Redesign the landing page content sections

**Files:**
- Modify: `frontend/src/app/page.tsx` (lines ~144-420)

- [ ] **Step 1: Rewrite the persona split panels (lines ~144-297)**

Replace the two-column persona cards with a unified "How It Works" section and a "For Restaurant Owners" section, both using glass cards:

- Section header: uppercase label (`text-[11px] uppercase tracking-[3px] text-muted-foreground`) + large heading (`text-2xl md:text-3xl font-bold text-foreground`)
- Three step cards in a row with arrow connectors: `glass-card rounded-2xl p-7 text-center`
- Each card: icon in a `w-14 h-14 gradient-primary/10 border border-primary/20 rounded-2xl` container, violet step label, heading, description in muted text

- [ ] **Step 2: Rewrite the closing CTA section (lines ~358-405)**

Dark section with ambient glow, gradient heading, and CTA buttons matching the hero pattern.

- [ ] **Step 3: Rewrite the footer (lines ~408-420)**

Simple dark footer with `text-muted-foreground`, gradient logo.

- [ ] **Step 4: Verify the full page renders**

Run: `cd frontend && npm run dev`
Check: Full landing page at http://localhost:3000 — all sections dark with consistent glass cards and violet accents.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat(design): redesign landing page content sections"
```

---

## Chunk 3: Customer Ordering Flow

### Task 10: Redesign WelcomeStep

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`

- [ ] **Step 1: Read the current component**

Read: `frontend/src/app/order/[slug]/components/WelcomeStep.tsx`

- [ ] **Step 2: Restyle the welcome screen**

Update the component styling to match the dark design:

- Full-height centered layout with `relative min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 text-center`
- Two ambient glow orbs positioned absolutely
- Restaurant logo in a `glass-card w-18 h-18 rounded-2xl` container
- "Welcome to" in uppercase label style
- Restaurant name with `gradient-text text-3xl font-bold tracking-tight`
- Table number in `text-muted-foreground`
- Dietary preference badges: `bg-primary/10 border border-primary/20 text-primary-foreground/70 rounded-full px-3 py-1 text-xs`
- Note text in `text-muted-foreground text-sm`
- Full-width `Button variant="gradient" size="lg"` with `glow-primary-lg`

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run dev`
Check: Navigate to an order page and verify the welcome screen.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/order/[slug]/components/WelcomeStep.tsx
git commit -m "feat(design): redesign WelcomeStep with dark atmospheric style"
```

### Task 11: Redesign InputStep with futuristic AI interaction

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/InputStep.tsx`

- [ ] **Step 1: Read the current component**

Read: `frontend/src/app/order/[slug]/components/InputStep.tsx`

- [ ] **Step 2: Restyle with futuristic AI elements**

This is the hero screen. Update styling:

- Large ambient radial glow behind the microphone: `absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-[55%] w-[300px] h-[300px] bg-[radial-gradient(circle,rgba(124,58,237,0.2),rgba(99,102,241,0.08)_50%,transparent_70%)] rounded-full`
- "Listening..." label in uppercase muted style
- Microphone orb: `w-[120px] h-[120px] gradient-primary/30 border border-primary/30 rounded-full flex items-center justify-center glow-primary-lg` with inset glow
- Two concentric pulse rings: `absolute top-1/2 left-1/2 border border-primary/15 rounded-full animate-pulse-ring` at 160px and 200px diameters
- Waveform visualization: flex container with ~16 `div` bars, each `w-[3px] rounded-full bg-primary/50` with varying `--wave-height` CSS variable and `animate-waveform` with staggered `animation-delay`
- Live transcript: `glass-card rounded-2xl p-4` with text in `text-foreground/70` and a blinking cursor `w-0.5 h-4 bg-primary/70 animate-blink-cursor`
- Text input fallback: `glass-card rounded-xl p-3.5 flex items-center gap-3` with a send button in `bg-primary/20 rounded-lg`

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run dev`
Check: The voice input screen shows the orb, pulse rings, waveform, and transcript.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/order/[slug]/components/InputStep.tsx
git commit -m "feat(design): redesign InputStep with futuristic AI interaction"
```

### Task 12: Redesign ConfirmationStep

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`

- [ ] **Step 1: Read the current component**

Read: `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`

- [ ] **Step 2: Restyle the order confirmation**

Update styling:

- Section header: uppercase label + "Review & Confirm" in `text-2xl font-semibold text-foreground`
- Order items: `glass-card rounded-2xl p-5` with flex layout — item name in `text-foreground font-semibold`, customizations in `text-muted-foreground text-xs`, quantity controls (minus in `bg-card border border-border rounded-lg`, plus in `bg-primary/20 text-primary rounded-lg`), price in `text-primary font-semibold`
- Total: `border-t border-border pt-4` with total amount using `gradient-text text-xl font-bold`
- Buttons: "Add More" as `Button variant="outline"` + "Proceed to Pay" as `Button variant="gradient" size="lg"` with `glow-primary`

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run dev`
Check: Order confirmation shows glass cards with violet accents.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/order/[slug]/components/ConfirmationStep.tsx
git commit -m "feat(design): redesign ConfirmationStep with glass cards"
```

### Task 13: Redesign remaining ordering steps

**Files:**
- Modify: `frontend/src/app/order/[slug]/components/LoadingStep.tsx`
- Modify: `frontend/src/app/order/[slug]/components/PaymentStep.tsx`
- Modify: `frontend/src/app/order/[slug]/components/SubmittedStep.tsx`

- [ ] **Step 1: Read all three files**

Read: `LoadingStep.tsx`, `PaymentStep.tsx`, `SubmittedStep.tsx`

- [ ] **Step 2: Restyle LoadingStep**

Update the loading screen to dark atmospheric style:

- Container: `min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center bg-background`
- Ambient glow: `absolute w-[200px] h-[200px] bg-[radial-gradient(circle,rgba(124,58,237,0.15),transparent_70%)] rounded-full animate-glow-pulse`
- Loading orb: `w-20 h-20 gradient-primary rounded-full animate-glow-pulse flex items-center justify-content glow-primary-lg`
- Loading text: `text-muted-foreground text-sm mt-6`
- Status text (e.g., "Processing your order..."): `text-foreground/70 text-lg font-medium mt-3`
- Three pulsing dots below text: `w-2 h-2 rounded-full bg-primary/50 animate-pulse` with staggered delays

- [ ] **Step 3: Restyle PaymentStep**

Update the payment screen with glass cards on dark:

- Container: `max-w-lg mx-auto px-6 py-8`
- Section header: `text-[11px] uppercase tracking-[3px] text-muted-foreground mb-2` label + `text-2xl font-semibold text-foreground` heading
- Order summary card: `glass-card rounded-2xl p-5 mb-6` listing items with `text-foreground text-sm` names and `text-muted-foreground text-xs` for details, total in `gradient-text font-bold`
- Stripe Elements container: `glass-card rounded-2xl p-6` wrapping the Stripe form
- Configure Stripe appearance object:
```typescript
const appearance: Appearance = {
  theme: 'night',
  variables: {
    colorPrimary: '#7c3aed',
    colorBackground: '#1e293b',
    colorText: '#f1f5f9',
    colorTextSecondary: '#94a3b8',
    colorDanger: '#ef4444',
    fontFamily: 'var(--font-geist-sans)',
    borderRadius: '12px',
    spacingUnit: '4px',
  },
  rules: {
    '.Input': {
      backgroundColor: '#334155',
      border: '1px solid rgba(255,255,255,0.06)',
    },
  },
};
```
- Pay button: `Button variant="gradient" size="lg"` with `className="w-full glow-primary mt-4"`

- [ ] **Step 4: Restyle SubmittedStep**

Update the success screen with dark styling:

- Container: `min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-6 text-center`
- Ambient glow: `absolute w-[250px] h-[250px] bg-[radial-gradient(circle,rgba(34,197,94,0.12),transparent_70%)] rounded-full` (green-tinted for success)
- Success icon: `w-20 h-20 bg-green-500/10 border border-green-500/20 rounded-full flex items-center justify-center mb-6` containing a `CheckCircle` icon from lucide-react in `text-green-400 w-10 h-10`
- "Order Submitted" heading: `text-2xl font-bold text-foreground mb-2`
- Order number: `gradient-text text-lg font-semibold`
- Status message: `text-muted-foreground text-sm mt-2 max-w-xs`
- Order details card: `glass-card rounded-2xl p-5 mt-8 w-full max-w-sm` with item list in `text-foreground/80 text-sm`
- "Track Order" or "Done" button: `Button variant="gradient" size="lg"` with `className="mt-6 w-full max-w-sm"`

- [ ] **Step 5: Verify all steps**

Run: `cd frontend && npm run dev`
Check: Navigate through the full ordering flow.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/order/[slug]/components/LoadingStep.tsx frontend/src/app/order/[slug]/components/PaymentStep.tsx frontend/src/app/order/[slug]/components/SubmittedStep.tsx
git commit -m "feat(design): redesign Loading, Payment, and Submitted steps"
```

---

## Chunk 4: Auth Pages & Admin Dashboard

### Task 14: Redesign auth pages

**Files:**
- Modify: `frontend/src/app/account/login/page.tsx`
- Modify: `frontend/src/app/account/register/page.tsx`
- Modify: `frontend/src/app/account/onboarding/page.tsx`

- [ ] **Step 1: Read all three auth page files**

Read: `login/page.tsx`, `register/page.tsx`, `onboarding/page.tsx`

- [ ] **Step 2: Restyle login page**

- Dark background (customer theme)
- Centered `glass-card rounded-2xl p-8 max-w-md w-full` wrapping the form
- Ambient glow orb behind the card
- Gradient logo at top
- Inputs using updated Input component (already styled via tokens)
- Social login buttons: `glass-card` style with `hover:bg-card/80`
- Submit button: `Button variant="gradient" size="lg" w-full`

- [ ] **Step 3: Restyle register page**

- Dark background with ambient glow orb (same as login)
- Centered `glass-card rounded-2xl p-8 max-w-md w-full` wrapping the form
- Gradient logo at top
- Name, email, password, confirm password inputs — all use updated Input component
- Social login buttons: `bg-card border border-border rounded-xl hover:bg-card/80` with provider icons
- Submit button: `Button variant="gradient" size="lg"` with `className="w-full"`
- "Already have an account?" link in `text-muted-foreground text-sm` with `text-primary hover:underline` for the link

- [ ] **Step 4: Restyle onboarding page**

- Dark background with glass-card step container
- Step indicators: circles with `bg-primary` for completed, `border border-primary` for current, `border border-border` for upcoming
- Step content inside glass card
- Navigation buttons: back as `Button variant="ghost"`, next as `Button variant="gradient"`

- [ ] **Step 5: Verify all auth pages**

Run: `cd frontend && npm run dev`
Check: Visit /account/login, /account/register, /account/onboarding.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/account/login/page.tsx frontend/src/app/account/register/page.tsx frontend/src/app/account/onboarding/page.tsx
git commit -m "feat(design): redesign auth pages with dark glass-card style"
```

### Task 15: Redesign admin dashboard pages

**Files:**
- Modify: `frontend/src/app/account/restaurants/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/menu/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/orders/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/settings/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/settings/integrations/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/billing/page.tsx`
- Modify: `frontend/src/app/account/restaurants/[slug]/sync-logs/page.tsx`

- [ ] **Step 1: Read all admin page files**

Read all seven files to understand their current layout and content.

- [ ] **Step 2: Restyle restaurant list page**

`frontend/src/app/account/restaurants/page.tsx`:
- Light background via admin theme tokens
- Restaurant cards: `bg-card border border-border rounded-2xl p-5` with restaurant name in `text-foreground font-semibold`, details in `text-muted-foreground`
- "Add Restaurant" button: `Button variant="gradient"`
- Card hover: `hover:border-primary/30 transition-colors`

- [ ] **Step 3: Restyle menu management page**

- Light admin theme (applied via ThemeProvider)
- Replace any amber/warm color references with violet/indigo accents
- Cards: `bg-card border border-border rounded-2xl` (white cards on slate background)
- Active states and buttons use `gradient-primary` or `text-primary` (now violet)
- Table rows: `hover:bg-muted/50`

- [ ] **Step 4: Restyle orders page**

- Same light card pattern
- Status badges: use updated Badge component
  - New: `bg-primary/10 text-primary` (violet)
  - Preparing: `bg-amber-100 text-amber-700`
  - Completed: `bg-green-100 text-green-700`
- Order list in white cards with clean borders

- [ ] **Step 5: Restyle settings page**

- Form sections in white cards
- Labels in `text-muted-foreground text-sm`
- Toggle switches and inputs use theme tokens
- Save button as `Button variant="gradient"`

- [ ] **Step 6: Restyle integrations page**

`frontend/src/app/account/restaurants/[slug]/settings/integrations/page.tsx`:
- Same white card layout as settings
- Integration cards: `bg-card border border-border rounded-2xl p-5`
- Connected status: `Badge` with `bg-green-100 text-green-700`
- Disconnected status: `Badge` with `bg-muted text-muted-foreground`
- Connect button: `Button variant="gradient"`

- [ ] **Step 7: Restyle billing page**

- Stats cards with `bg-card border border-border rounded-2xl`
- Numbers in `text-foreground text-2xl font-bold`
- Trend indicators: green for up, red for down

- [ ] **Step 8: Restyle sync-logs page**

- Log entries in white card table: `bg-card border border-border rounded-2xl overflow-hidden`
- Table rows: `border-b border-border hover:bg-muted/50`
- Status indicators: success in `text-green-600`, error in `text-destructive`, pending in `text-muted-foreground`

- [ ] **Step 9: Verify all admin pages**

Run: `cd frontend && npm run dev`
Check: Visit /account/restaurants, /account/restaurants/[any-slug]/menu, /orders, /settings, /settings/integrations, /billing, /sync-logs.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/app/account/restaurants/
git commit -m "feat(design): redesign admin dashboard with Clean & Airy theme"
```

---

## Chunk 5: Kitchen Display & Polish

### Task 16: Redesign kitchen display

**Files:**
- Modify: `frontend/src/app/kitchen/[slug]/page.tsx`

- [ ] **Step 1: Read the current kitchen page**

Read: `frontend/src/app/kitchen/[slug]/page.tsx`

- [ ] **Step 2: Restyle the kitchen display**

The kitchen now uses the "kitchen" theme (extra-dark #0a0f1a via tokens):

- Header: `bg-card/50 border-b border-border` with kitchen icon, restaurant name, and live status dot (`w-2 h-2 bg-success rounded-full` with `box-shadow: 0 0 8px rgba(34,197,94,0.4)`)
- Three-column Kanban layout: `grid grid-cols-3 gap-3 p-4`
- Column headers: uppercase label with count badge
  - New: `bg-primary/20 text-primary` count badge
  - Preparing: `bg-amber-500/20 text-amber-400` count badge
  - Ready: `bg-green-500/20 text-green-400` count badge
- Order cards per column:
  - New: `bg-primary/[0.08] border border-primary/15 rounded-xl p-4`
  - Preparing: `bg-amber-500/[0.06] border border-amber-500/12 rounded-xl p-4`
  - Ready: `bg-green-500/[0.06] border border-green-500/12 rounded-xl p-4`
- Order number colored per column (violet, amber, green)
- Table + time in `text-muted-foreground text-xs`
- Item list with customizations indented (`text-muted-foreground text-xs` preceded by `↳`)
- Action buttons per column:
  - "Start Preparing": `Button variant="gradient"`
  - "Mark Ready": `bg-amber-500/15 border border-amber-500/25 text-amber-400 rounded-lg`
  - "Complete": `bg-green-500/15 border border-green-500/25 text-green-400 rounded-lg`
- New order cards use `animate-slide-in-top`

- [ ] **Step 3: Verify the kitchen display**

Run: `cd frontend && npm run dev`
Check: Visit /kitchen/[slug] — extra-dark background, color-coded columns.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/kitchen/[slug]/page.tsx
git commit -m "feat(design): redesign kitchen display with extra-dark theme"
```

### Task 17: Update Dialog, Tabs, and remaining UI components

**Files:**
- Modify: `frontend/src/components/ui/dialog.tsx`
- Modify: `frontend/src/components/ui/tabs.tsx`

- [ ] **Step 1: Read dialog.tsx and tabs.tsx**

Read: `frontend/src/components/ui/dialog.tsx`, `frontend/src/components/ui/tabs.tsx`

- [ ] **Step 2: Update Dialog styling**

- Overlay: `bg-black/60 backdrop-blur-sm`
- Content: `bg-card border border-border rounded-2xl`
- Ensure it works in both dark (customer) and light (admin) contexts

- [ ] **Step 3: Update Tabs styling**

- Tab list: `bg-card border border-border rounded-xl p-1`
- Active tab: `bg-primary text-primary-foreground rounded-lg shadow-sm`
- Inactive tab: `text-muted-foreground hover:text-foreground`

- [ ] **Step 4: Verify the app builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/dialog.tsx frontend/src/components/ui/tabs.tsx
git commit -m "feat(design): update Dialog and Tabs styling"
```

### Task 18: Restyle onboarding components

**Files:**
- Modify: `frontend/src/components/onboarding/preferences-step.tsx`
- Modify: `frontend/src/components/onboarding/owner-question-step.tsx`
- Modify: `frontend/src/components/onboarding/restaurant-details-step.tsx`
- Modify: `frontend/src/components/onboarding/menu-upload-step.tsx`
- Modify: `frontend/src/components/onboarding/onboarding-banner.tsx`

- [ ] **Step 1: Read all five onboarding component files**

Read each file to understand current markup.

- [ ] **Step 2: Restyle preferences-step.tsx**

- Option cards: `glass-card rounded-2xl p-4 cursor-pointer hover:border-primary/30`
- Selected option: `border-primary bg-primary/10`
- Labels: `text-foreground font-medium`, descriptions: `text-muted-foreground text-sm`

- [ ] **Step 3: Restyle owner-question-step.tsx**

- Choice buttons: `glass-card rounded-2xl p-5 hover:border-primary/30 cursor-pointer`
- Selected: `border-primary bg-primary/10`
- Text: `text-foreground`

- [ ] **Step 4: Restyle restaurant-details-step.tsx**

- Form inputs inside `glass-card rounded-2xl p-6`
- Labels: `text-foreground text-sm font-medium`
- Google Places autocomplete input: same Input component styling

- [ ] **Step 5: Restyle menu-upload-step.tsx**

- Upload dropzone: `glass-card rounded-2xl p-8 border-dashed border-2 border-border hover:border-primary/30 text-center`
- Upload icon: `text-muted-foreground`
- Instructions: `text-muted-foreground text-sm`

- [ ] **Step 6: Restyle onboarding-banner.tsx**

- Banner: `bg-card border border-border rounded-xl p-4` with gradient accent on left border or `border-l-4 border-l-primary`
- Text: `text-foreground text-sm`, link in `text-primary hover:underline`

- [ ] **Step 7: Verify onboarding flow**

Run: `cd frontend && npm run dev`
Check: Visit /account/onboarding and step through the flow.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/onboarding/
git commit -m "feat(design): restyle onboarding components for dark theme"
```

### Task 19: Restyle shared components and final polish

**Files:**
- Modify: `frontend/src/components/PreferencesDialog.tsx`
- Modify: `frontend/src/components/SocialLoginButtons.tsx`
- Modify: `frontend/src/components/menu-upload-modal.tsx`
- Modify: `frontend/src/components/parsed-menu-editor.tsx`

- [ ] **Step 1: Read all four shared component files**

Read each file to understand current markup.

- [ ] **Step 2: Restyle PreferencesDialog.tsx**

- Dialog content uses updated Dialog component (already glass-styled via Task 17)
- Preference options: `glass-card rounded-xl p-3 cursor-pointer hover:border-primary/30`
- Selected state: `border-primary bg-primary/10`
- Save button: `Button variant="gradient"`

- [ ] **Step 3: Restyle SocialLoginButtons.tsx**

- Social buttons: `bg-card border border-border rounded-xl py-3 px-4 hover:bg-card/80 flex items-center justify-center gap-3 text-foreground`
- Provider icons retain their brand colors

- [ ] **Step 4: Restyle menu-upload-modal.tsx**

- Dialog content uses updated Dialog (glass-styled)
- Upload area: `glass-card rounded-2xl p-6 border-dashed border-2 border-border hover:border-primary/30`
- Progress indicators: `bg-primary` fill bar

- [ ] **Step 5: Restyle parsed-menu-editor.tsx**

This component is used in admin context (light theme):
- Editor container: `bg-card border border-border rounded-2xl`
- Category headers: `text-foreground font-semibold`
- Item rows: `border-b border-border p-3 hover:bg-muted/50`
- Edit inputs: standard Input component
- Save/cancel buttons: `Button variant="gradient"` / `Button variant="ghost"`

- [ ] **Step 6: Check for remaining hardcoded color references**

Search for hardcoded amber/orange colors that should be replaced with theme tokens:

Run: `grep -rn "amber\|orange\|bg-\[#" frontend/src/ --include="*.tsx" --include="*.ts" | grep -v node_modules`

**Important:** Amber used for semantic status indicators (e.g., "Preparing" order status in kitchen/admin) is intentional and should be preserved. Only replace amber/orange used as brand/accent colors.

- [ ] **Step 7: Fix any hardcoded colors found**

Replace brand-color amber/orange references with `primary`, `gradient-primary`, or `gradient-text` classes as appropriate.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PreferencesDialog.tsx frontend/src/components/SocialLoginButtons.tsx frontend/src/components/menu-upload-modal.tsx frontend/src/components/parsed-menu-editor.tsx
git commit -m "feat(design): restyle shared components for new theme"
```

### Task 20: Full visual walkthrough and final verification

- [ ] **Step 1: Start the dev server**

Run: `cd frontend && npm run dev`

- [ ] **Step 2: Walk through every page and verify**

- [ ] Landing page: dark, gradient text, glass cards, ambient glows
- [ ] Login/Register: dark glass-card forms
- [ ] Onboarding: dark glass-card steps with styled preference cards
- [ ] Ordering flow: dark, futuristic AI interaction, glass order cards
- [ ] Admin restaurant list: light, clean white cards on slate
- [ ] Admin menu/orders/settings/billing: light with violet accents
- [ ] Kitchen display: extra-dark, color-coded Kanban columns

- [ ] **Step 3: Fix any visual inconsistencies found**

Address any remaining issues from the walkthrough.

- [ ] **Step 4: Final build verification**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 5: Commit any remaining fixes**

```bash
git add frontend/src/
git commit -m "feat(design): final polish and consistency fixes"
```
