# POS Vendor Selection During Onboarding

## Problem

POS integration is currently a standalone settings page, disconnected from onboarding. The connect flow has hardcoded Square references (buttons, OAuth initiation). Adding a second vendor (Toast) would require duplicating UI patterns.

## Goal

- Add a POS vendor selection step to onboarding so owners choose their POS early
- Extract a shared `POSVendorSelector` component used by both onboarding and the integrations settings page
- Vendor selection is separate from OAuth connection — onboarding saves the choice, the settings page handles the actual connection

## Design

### Backend

**New endpoint:** `POST /api/restaurants/{slug}/pos/select-vendor/`

- Accepts `{ pos_type: "square" | "none" }`
- Backend validates `pos_type` against a whitelist of currently enabled vendors (`["square", "none"]`), not the full `POSType` enum. When Toast is enabled later, add it to the whitelist.
- Creates or updates a `POSConnection` record with `pos_type` set and **explicitly sets `is_active=false`** (overriding the model default of `True`). This represents "vendor selected but not connected."
- Uses the existing `RestaurantPOSMixin` for ownership validation (returns 404 if not owned by user). Returns 400 for invalid `pos_type` values.
- No model schema changes needed — existing `POSConnection` fields are sufficient.
- Calling the endpoint multiple times updates the existing record (via `update_or_create`).

**No new serializer fields.** The existing `POSConnectionSerializer` already returns `pos_type` and `is_connected` (computed from `is_active and pos_type != 'none'`). The frontend can derive all needed states from these two fields:
- No record / `pos_type == "none"`: no vendor selected
- `pos_type != "none"` and `is_connected == false`: vendor selected, not connected
- `is_connected == true`: fully connected

**Bare dict response update:** The `POSConnectionDetailView.get` fallback response (when no record exists) already returns `{"pos_type": "none", "is_connected": False, "payment_mode": "stripe"}` — this is consistent with the above logic and needs no changes.

**New URL:** Add `path("restaurants/<slug:slug>/pos/select-vendor/", POSVendorSelectView.as_view())` to `integrations/urls.py`.

### Frontend — Shared Component

**`src/components/pos-vendor-selector.tsx`**

Renders a grid of vendor tiles. Each tile shows: name, icon/logo placeholder, tagline, and optional "Coming Soon" badge.

Vendor configuration (static array inside component):

| Vendor | Tagline | Status |
|--------|---------|--------|
| Square | Popular with restaurants & retail | Selectable |
| Toast | Built for restaurants | Coming Soon (disabled) |
| None | I don't use a POS | Selectable |

Props:
- `selected: string | null` — currently selected vendor
- `onSelect: (posType: string) => void` — called when a tile is clicked

The "None" tile is visually distinct (muted/outlined). Coming Soon tiles are grayed out and not clickable.

### Frontend — Onboarding Step

**New component:** `src/components/onboarding/pos-vendor-step.tsx`

Props: `slug: string`, `onComplete: () => void`, `onSkip: () => void`

- Renders `POSVendorSelector` for tile selection
- "Continue" button: calls `POST /api/restaurants/{slug}/pos/select-vendor/` with the selected vendor, then `onComplete()`
- "Skip" button: calls `onSkip()` directly (no API call, no record created)
- Skip means "I'll decide later." Selecting None means "I don't use a POS." Both are functionally equivalent downstream (no POS sync) but the explicit choice captures user intent.

### Frontend — Onboarding Flow Changes

**`/account/onboarding/page.tsx`:**
- New step `"pos-vendor"` added after `"menu-upload"`
- Restaurant owner path becomes 5 steps: preferences -> owner-question -> restaurant-details -> menu-upload -> pos-vendor
- Non-owner path stays at 2 steps
- Update `totalSteps` logic: currently `step === "restaurant-details" || step === "menu-upload" ? 4 : 2`. Change to include `"pos-vendor"` in the owner-path condition and set `totalSteps = 5`. Update `currentStep` mapping: preferences=1, owner-question=2, restaurant-details=3, menu-upload=4, pos-vendor=5.

**`/account/register-restaurant/page.tsx`:**
- New step `"pos-vendor"` added after `"menu"`
- Becomes 3 steps: details -> menu -> pos-vendor
- `handleComplete` still redirects to `/account/restaurants` — the pos-vendor step's `onComplete` and `onSkip` both call this same handler

### Frontend — Integrations Settings Page

**`/account/restaurants/[slug]/settings/integrations/page.tsx`:**

Replace the current "Connect Square" / "Connect Toast (Coming Soon)" buttons with `POSVendorSelector` when no vendor is connected yet.

Three states:
1. **No vendor selected** (`pos_type == "none"` or no record): Show `POSVendorSelector` with a "Save" button. On save, calls `POST /pos/select-vendor/`.
2. **Vendor selected, not connected** (`pos_type != "none"` and `is_connected == false`): Show the selected tile highlighted, plus a "Connect" button to kick off OAuth and a "Change" button. "Change" re-shows the selector and PATCHes via the same `select-vendor` endpoint (no record deletion).
3. **Connected** (`is_connected == true`): Show existing connection status card, location selector, and payment mode as-is.

### API Hook

**New hook:** `src/hooks/use-pos-vendor-select.ts`

Wraps the `POST /api/restaurants/{slug}/pos/select-vendor/` call as a mutation. Invalidates `["pos-connection", slug]` query key on success.

### New API function

Add `selectPOSVendor(slug: string, posType: string)` to `src/lib/api.ts`.

### Type Update

Add no new fields to `POSConnectionResponse` in `src/types/index.ts` — existing `pos_type` and `is_connected` fields are sufficient to derive all UI states.

## Known Pre-existing Issue

The `SquareOAuthCallbackView` redirects to `/account/restaurants/{slug}/integrations?connected=square` but the actual route is `/account/restaurants/[slug]/settings/integrations/`. This is out of scope for this spec but should be fixed when touching the integrations page.

## Out of Scope

- Refactoring `POSConnectInitiateView` into a vendor-registry/strategy pattern (deferred until Toast is actually added)
- Refactoring `SquareOAuthCallbackView` into a generic callback
- Fetching vendor logos from external sources (using icon placeholders for now)
- Fixing the OAuth redirect URL mismatch (pre-existing, separate fix)
