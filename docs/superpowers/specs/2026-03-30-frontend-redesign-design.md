# Frontend Redesign — "Soft Dark & Elevated"

## Overview

Full visual redesign of the AI QR ordering frontend. The current amber/slate theme is replaced with a cohesive design system: a dark, atmospheric "Soft Dark & Elevated" theme for customer-facing pages, a clean light "Clean & Airy" theme for the admin dashboard, and an extra-dark variant for the kitchen display.

The approach is theme-first: rebuild design tokens and component overrides first, then sweep through each page updating layouts and adding visual effects.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Visual direction | Soft Dark & Elevated | Deep navy/slate, gradient text, soft glows — refined and atmospheric |
| Scope | All surfaces | Landing, ordering flow, admin dashboard, kitchen display |
| Theme strategy | Dark customers, light admin | Dark is premium for diners; light is ergonomic for owners working long sessions |
| AI interaction style | Futuristic/techy | Waveforms, glowing orb, particle effects — lean into the cutting-edge angle |
| Implementation approach | Theme-first | Build tokens + component overrides first, then page-by-page updates |

## Design System Foundation

### Customer Theme — "Soft Dark & Elevated"

**Color Palette (HSL for CSS variables):**

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0f172a` (222 47% 11%) | Page background |
| Surface | `#1e293b` (217 33% 17%) | Card/container backgrounds |
| Elevated | `#334155` (215 25% 27%) | Hover states, raised elements |
| Primary | gradient `#7c3aed → #6366f1` | Buttons, CTAs, interactive elements |
| Accent | gradient `#f0abfc → #818cf8` | Gradient text highlights, decorative |
| Text primary | `#f1f5f9` (210 40% 96%) | Headings, important text |
| Text secondary | `rgba(255,255,255,0.6)` | Body text |
| Text muted | `rgba(255,255,255,0.35)` | Labels, hints |
| Border | `rgba(255,255,255,0.06)` | Card borders, dividers |
| Success | `#22c55e` | Confirmation states |
| Destructive | `#ef4444` | Error/delete states |

**Visual Effects:**

- **Glass cards:** `rgba(255,255,255,0.04-0.06)` background + `backdrop-filter: blur(20px)` + `border: 1px solid rgba(255,255,255,0.06)`
- **Soft glows:** `box-shadow: 0 0 30-60px rgba(124,58,237,0.15-0.3)` on primary interactive elements
- **Gradient text:** `background: linear-gradient(135deg, #f0abfc, #818cf8); -webkit-background-clip: text` on key headings
- **Ambient orbs:** Large `radial-gradient` circles with purple/indigo at low opacity positioned absolutely behind content
- **Border radius:** 14-20px for cards, 10-12px for buttons/inputs (increase from current 8px/0.5rem)

**Typography (Geist Sans — keep existing fonts):**

| Element | Size | Weight | Style |
|---------|------|--------|-------|
| H1 (hero) | 36-48px | 700 | letter-spacing: -1 to -2px |
| H2 (section) | 24-28px | 600-700 | letter-spacing: -0.5 to -1px |
| H3 (card title) | 15-17px | 600 | — |
| Body | 14-15px | 400 | color: text-secondary |
| Label | 11px | 500-600 | uppercase, letter-spacing: 2-3px, color: text-muted |

### Admin Theme — "Clean & Airy"

**Color Palette:**

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#f8fafc` (210 40% 98%) | Page background |
| Surface | `#ffffff` | Cards, sidebar, header |
| Text primary | `#0f172a` (222 47% 11%) | Headings |
| Text secondary | `#64748b` (215 16% 47%) | Body text |
| Text muted | `#94a3b8` (215 16% 65%) | Labels |
| Primary | gradient `#7c3aed → #6366f1` | Active states, CTAs, brand accent |
| Primary subtle | `rgba(124,58,237,0.08)` | Active sidebar item, hover states |
| Border | `#e2e8f0` (214 32% 91%) | Card borders, dividers |
| Muted | `#f1f5f9` (210 40% 96%) | Secondary backgrounds |

**Visual Properties:**

- No glass effects — clean solid borders (`1px solid #e2e8f0`) and subtle shadows
- Same border radius system (14-20px cards, 10-12px controls)
- Same typography scale
- Violet accent used sparingly for active states and brand identity

### Kitchen Theme — Extra Dark

- Background: `#0a0f1a` (even darker than customer)
- Same glass card approach as customer theme
- Color-coded columns: violet (new), amber (preparing), green (ready)
- Larger text sizes for readability at distance
- Live status indicator with green pulse dot + glow

## Page Designs

### Landing Page

**Hero section:**
- Full-viewport dark background with ambient purple/indigo glow orbs (positioned absolutely)
- Floating particle dots (small circles at low opacity) for depth
- Gradient brand logo ("QRder") in nav
- Large headline: "Order with your voice, not a menu" — second line uses gradient text
- Subtitle in muted text, max-width ~420px
- Dual CTA: primary gradient "Try a Demo" + secondary glass "I'm a Restaurant Owner"
- Nav items in muted text, sign-in as glass pill button

**How It Works section:**
- Three glass cards in a row with arrow connectors
- Each card: icon in gradient-tinted container, violet step label (uppercase), heading, description
- Section header with label + large heading

**Additional sections (CTA, footer):**
- Follow same glass card + gradient accent patterns
- Keep content and structure similar to current, restyle to new tokens

### Customer Ordering Flow

**Welcome screen (after QR scan):**
- Centered, mobile-first layout (max-width ~512px)
- Ambient glow orbs in background
- Restaurant logo in glass-bordered rounded container
- "Welcome to" label (uppercase, muted) + restaurant name in gradient text
- Table number below
- User dietary preferences shown as glass pill badges with subtle violet/indigo tint
- Note about AI respecting preferences
- Full-width gradient CTA button with glow shadow

**AI Voice Input — the hero screen:**
- Large ambient radial glow centered behind microphone
- "Listening..." label (uppercase, muted)
- Microphone orb: 120px circle with gradient violet background, inset glow, mic icon
- Two concentric pulse rings expanding outward (animated in implementation)
- Waveform visualization: ~16 vertical bars, varying heights, gradient fills (violet/indigo), animated
- Live transcript: glass card with typed text in secondary color, blinking cursor (violet)
- Text input fallback: glass-bordered input at bottom with send button
- Particle effects: small dots floating around the orb area (animated in implementation)

**Order Confirmation:**
- Section header: label + "Review & Confirm" heading
- Order items as glass cards: item name (primary text), customizations (muted), quantity controls (−/+), price in accent color
- Quantity minus: muted glass button; plus: violet-tinted button
- Total with gradient text
- Two buttons: "Add More" (glass secondary) + "Proceed to Pay" (gradient primary with glow)

**Payment, Submitted screens:**
- Follow same glass card patterns
- Stripe elements styled to match dark theme where possible
- Success state with green accent, checkmark animation

### Admin Dashboard

**Layout:**
- Top nav bar: white background, bottom border, gradient logo, restaurant name, notification + avatar
- Left sidebar: white background, right border, navigation items with icons
- Active item: violet-tinted background + violet text
- Main content: slate background with white card containers

**Overview page:**
- Stats row: three white cards with clean borders — metric label (uppercase, muted), large number, trend indicator (green up / red down)
- Recent orders table: white card, header row with "View All" link in violet, row items with colored status badges

**Menu, Orders, Settings, Billing pages:**
- Follow same layout patterns: white cards on slate background
- Forms use clean inputs with slate borders
- Buttons: primary gradient for main actions, ghost/outline for secondary
- Tabs: clean underline style with violet active indicator

### Auth Pages (Login, Register, Onboarding)

Auth pages use the customer dark theme. No layout changes — same form structures, same onboarding steps. Restyle to new tokens:

- Dark background with ambient glow orbs
- Glass card wrapping the form content
- Inputs with glass styling (rgba background, subtle border)
- Primary gradient CTA buttons with glow
- Social login buttons in glass style
- Onboarding step indicators using violet accent for active/completed states

### Kitchen Display

**Layout:**
- Full-screen dark background (#0a0f1a)
- Minimal header: kitchen icon + label, restaurant name, live status dot
- Three-column Kanban grid

**Columns:**
- Column headers: uppercase label + count badge color-coded to status
- New Orders: violet-tinted cards, violet "Start Preparing" gradient button
- Preparing: amber-tinted cards, amber outline "Mark Ready" button
- Ready: green-tinted cards, green outline "Complete" button
- Each card: order number in column color, table + time in muted text, item list with customization indented, action button

## Animations & Micro-interactions

All animations will be defined in globals.css using CSS keyframes and tailwindcss-animate:

| Animation | Where | Behavior |
|-----------|-------|----------|
| `pulse-ring` | Voice input mic rings | Scale 1→1.3 with fade, infinite loop, staggered delays |
| `waveform` | Voice input bars | Random height oscillation, infinite, staggered |
| `float-particle` | Landing hero, voice input | Gentle vertical float + fade, randomized timing |
| `glow-pulse` | Primary buttons, mic orb | Box-shadow intensity oscillation |
| `blink-cursor` | Live transcript cursor | Opacity 0↔1 at 1s interval |
| `fade-in-up` | Page transitions, cards | Translate Y + opacity, 300-500ms ease-out |
| `slide-in` | Kitchen order cards | New orders slide in from top |

## Component Overrides (shadcn/ui)

Components to update via CSS variable overrides and Tailwind config:

| Component | Customer Theme Changes | Admin Theme Changes |
|-----------|----------------------|---------------------|
| Button (primary) | Gradient background, glow shadow, 14px radius | Gradient background, no glow, 10px radius |
| Button (secondary) | Glass background + border, 14px radius | White background + slate border, 10px radius |
| Button (ghost) | Transparent, white text hover | Transparent, slate text hover |
| Card | Glass background, subtle border, 16-20px radius | White, slate border, 14px radius |
| Input | Glass background, subtle border, 14px radius | White, slate border, 10px radius |
| Badge | Glass tinted per status color | Light tinted per status color |
| Dialog | Glass background with backdrop blur, dark overlay | White, subtle shadow |
| Dropdown | Glass background, dark | White, subtle shadow |
| Tabs | Glass tab list, violet active glow | Clean underline, violet indicator |
| Separator | rgba(255,255,255,0.06) | #e2e8f0 |

## CSS Architecture

**globals.css structure:**

1. Tailwind directives (@tailwind base/components/utilities)
2. CSS custom properties in `:root` — shared tokens
3. `[data-theme="customer"]` — customer dark token overrides
4. `[data-theme="admin"]` — admin light token overrides
5. `[data-theme="kitchen"]` — kitchen extra-dark overrides (new)
6. Keyframe animations
7. Utility classes (gradient-text, glass-card, glow, etc.)

**ThemeProvider updates:**
- Add "kitchen" as a third theme
- Routes starting with `/kitchen` → "kitchen" theme
- Routes starting with `/account/restaurants` → "admin" theme
- All other routes → "customer" theme

**Tailwind config updates:**
- Update border-radius tokens (increase defaults)
- Add custom animation utilities
- Update color palette references to new HSL values

## Implementation Order

1. **Design tokens** — Update globals.css with new color palette, add kitchen theme, define animations
2. **Tailwind config** — Update border radius, colors, animation config
3. **ThemeProvider** — Add kitchen theme detection
4. **shadcn/ui component overrides** — Update button, card, input, badge, dialog, tabs, etc.
5. **Landing page** — Hero, How It Works, CTA sections
6. **Ordering flow** — Welcome, AI Voice Input (with animations), Confirmation, Payment, Submitted
7. **Auth pages** — Login, Register, Onboarding (customer dark theme)
8. **Admin dashboard** — Layout with sidebar, overview, menu, orders, settings, billing pages
9. **Kitchen display** — Kanban board with color-coded columns
10. **Polish pass** — Animation timing, responsive breakpoints, edge cases

## Out of Scope

- No structural/routing changes — same pages, same URLs
- No new features — purely visual redesign
- No backend changes
- No font changes — keep Geist Sans / Geist Mono
- No new dependencies (use existing tailwindcss-animate, CVA, etc.)
