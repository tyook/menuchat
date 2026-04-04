# POS Vendor Selection Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a POS vendor selection step to onboarding and extract a shared vendor selector component for the integrations settings page.

**Architecture:** New backend endpoint saves vendor choice to `POSConnection` with `is_active=false`. Shared `POSVendorSelector` React component renders vendor tiles, used by both a new onboarding step and the refactored integrations settings page.

**Tech Stack:** Django REST Framework, Next.js 14, TanStack Query, Tailwind CSS + shadcn/ui, pytest, Lucide icons

**Spec:** `docs/superpowers/specs/2026-04-04-pos-vendor-selection-design.md`

---

## Chunk 1: Backend — Select Vendor Endpoint

### Task 1: Backend view and URL for vendor selection

**Files:**
- Modify: `backend/integrations/views.py` (add `POSVendorSelectView` after `POSConnectionDetailView`, around line 56)
- Modify: `backend/integrations/urls.py` (add URL pattern)
- Test: `backend/integrations/tests/test_views.py`

- [ ] **Step 1: Write failing tests for the new endpoint**

Add to `backend/integrations/tests/test_views.py`:

```python
@pytest.fixture
def owner_setup(api_client):
    """Shared fixture — extract to module level (replaces the duplicate in TestPOSConnectionAPI)."""
    user = UserFactory()
    restaurant = RestaurantFactory(owner=user, slug="test-resto")
    api_client.force_authenticate(user=user)
    return {"user": user, "restaurant": restaurant, "client": api_client}


@pytest.mark.django_db
class TestPOSVendorSelectAPI:

    def test_select_square_creates_connection(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert response.data["is_connected"] is False
        conn = POSConnection.objects.get(restaurant=owner_setup["restaurant"])
        assert conn.pos_type == "square"
        assert conn.is_active is False

    def test_select_none_creates_connection(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "none"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "none"

    def test_select_vendor_updates_existing(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="none",
            is_active=False,
        )
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert POSConnection.objects.filter(
            restaurant=owner_setup["restaurant"]
        ).count() == 1

    def test_select_invalid_vendor_rejected(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "toast"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_select_vendor_unauthenticated(self, api_client):
        RestaurantFactory(slug="test-resto")
        response = api_client.post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_select_vendor_wrong_owner(self, api_client):
        other_user = UserFactory()
        RestaurantFactory(owner=other_user, slug="not-mine")
        user = UserFactory()
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/restaurants/not-mine/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_select_vendor_missing_pos_type(self, owner_setup):
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_select_vendor_on_already_connected_disconnects(self, owner_setup):
        """Selecting a new vendor on an active connection sets is_active=False."""
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
            is_active=True,
        )
        response = owner_setup["client"].post(
            "/api/restaurants/test-resto/pos/select-vendor/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        conn = POSConnection.objects.get(restaurant=owner_setup["restaurant"])
        assert conn.is_active is False
        assert response.data["is_connected"] is False
```

Also remove the duplicate `owner_setup` fixture from the existing `TestPOSConnectionAPI` class and use the new module-level one instead. The `api_client` fixture comes from `backend/conftest.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest integrations/tests/test_views.py::TestPOSVendorSelectAPI -v`
Expected: FAIL — `POSVendorSelectView` does not exist / URL not found.

- [ ] **Step 3: Implement the view**

Add to `backend/integrations/views.py` after `POSConnectionDetailView` (after line 55):

```python
ENABLED_POS_VENDORS = {"square", "none"}


class POSVendorSelectView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        restaurant = self.get_restaurant(slug)
        pos_type = request.data.get("pos_type")

        if pos_type not in ENABLED_POS_VENDORS:
            return Response(
                {"error": f"Unsupported POS type: {pos_type}. Allowed: {', '.join(sorted(ENABLED_POS_VENDORS))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        connection, _ = POSConnection.objects.update_or_create(
            restaurant=restaurant,
            defaults={"pos_type": pos_type, "is_active": False},
        )
        return Response(POSConnectionSerializer(connection).data)
```

- [ ] **Step 4: Add URL pattern**

Add to `backend/integrations/urls.py` — import `POSVendorSelectView` and add path:

```python
path(
    "restaurants/<slug:slug>/pos/select-vendor/",
    POSVendorSelectView.as_view(),
    name="pos-vendor-select",
),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest integrations/tests/test_views.py::TestPOSVendorSelectAPI -v`
Expected: All 8 tests PASS.

Note: `conn.is_connected` in the test is not a model property — it's computed by the serializer. Use `conn.is_active and conn.pos_type != "none"` for direct model assertions, or assert on `response.data["is_connected"]`.

- [ ] **Step 6: Run full integrations test suite for regressions**

Run: `cd backend && python -m pytest integrations/tests/ -v`
Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/integrations/views.py backend/integrations/urls.py backend/integrations/tests/test_views.py
git commit -m "feat: add POST /pos/select-vendor/ endpoint for POS vendor selection"
```

---

## Chunk 2: Frontend — API Function, Hook, and Shared Component

### Task 2: Add API function and hook for vendor selection

**Files:**
- Modify: `frontend/src/lib/api.ts` (add `selectPOSVendor` after `updatePOSConnection`, around line 396)
- Create: `frontend/src/hooks/use-pos-vendor-select.ts`

- [ ] **Step 1: Add API function**

Add to `frontend/src/lib/api.ts` after the `disconnectPOS` function (around line 386):

```typescript
export async function selectPOSVendor(
  slug: string,
  posType: string
): Promise<POSConnectionResponse> {
  return apiFetch<POSConnectionResponse>(
    `/api/restaurants/${slug}/pos/select-vendor/`,
    { method: "POST", body: JSON.stringify({ pos_type: posType }) }
  );
}
```

- [ ] **Step 2: Create the hook**

Create `frontend/src/hooks/use-pos-vendor-select.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { selectPOSVendor } from "@/lib/api";

export function usePOSVendorSelect(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (posType: string) => selectPOSVendor(slug, posType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-connection", slug] });
    },
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/hooks/use-pos-vendor-select.ts
git commit -m "feat: add selectPOSVendor API function and usePOSVendorSelect hook"
```

### Task 3: Create shared `POSVendorSelector` component

**Files:**
- Create: `frontend/src/components/pos-vendor-selector.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/pos-vendor-selector.tsx`:

```tsx
"use client";

import { cn } from "@/lib/utils";
import { Square, UtensilsCrossed, X } from "lucide-react";

interface VendorOption {
  id: string;
  name: string;
  tagline: string;
  icon: React.ReactNode;
  comingSoon: boolean;
}

const VENDORS: VendorOption[] = [
  {
    id: "square",
    name: "Square",
    tagline: "Popular with restaurants & retail",
    icon: <Square className="h-8 w-8" />,
    comingSoon: false,
  },
  {
    id: "toast",
    name: "Toast",
    tagline: "Built for restaurants",
    icon: <UtensilsCrossed className="h-8 w-8" />,
    comingSoon: true,
  },
  {
    id: "none",
    name: "None",
    tagline: "I don't use a POS",
    icon: <X className="h-8 w-8" />,
    comingSoon: false,
  },
];

interface POSVendorSelectorProps {
  selected: string | null;
  onSelect: (posType: string) => void;
}

export function POSVendorSelector({ selected, onSelect }: POSVendorSelectorProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {VENDORS.map((vendor) => {
        const isSelected = selected === vendor.id;
        const isDisabled = vendor.comingSoon;

        return (
          <button
            key={vendor.id}
            type="button"
            disabled={isDisabled}
            onClick={() => onSelect(vendor.id)}
            className={cn(
              "relative flex flex-col items-center gap-3 rounded-2xl border-2 p-6 text-center transition-all",
              isDisabled && "cursor-not-allowed opacity-50",
              !isDisabled && !isSelected && "border-border hover:border-primary/40 hover:bg-accent/50",
              !isDisabled && isSelected && "border-primary bg-primary/5 ring-1 ring-primary/20",
              vendor.id === "none" && !isSelected && "border-dashed"
            )}
          >
            {vendor.comingSoon && (
              <span className="absolute top-2 right-2 rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                Coming Soon
              </span>
            )}
            <div
              className={cn(
                "flex h-14 w-14 items-center justify-center rounded-xl",
                isSelected ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              )}
            >
              {vendor.icon}
            </div>
            <div>
              <div className="font-semibold">{vendor.name}</div>
              <div className="mt-1 text-xs text-muted-foreground">{vendor.tagline}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/pos-vendor-selector.tsx
git commit -m "feat: add shared POSVendorSelector tile component"
```

---

## Chunk 3: Frontend — Onboarding Step and Flow Changes

### Task 4: Create POS vendor onboarding step component

**Files:**
- Create: `frontend/src/components/onboarding/pos-vendor-step.tsx`

- [ ] **Step 1: Create the step component**

Create `frontend/src/components/onboarding/pos-vendor-step.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { POSVendorSelector } from "@/components/pos-vendor-selector";
import { usePOSVendorSelect } from "@/hooks/use-pos-vendor-select";
import { useToast } from "@/hooks/use-toast";

interface POSVendorStepProps {
  slug: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function POSVendorStep({ slug, onComplete, onSkip }: POSVendorStepProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const vendorSelect = usePOSVendorSelect(slug);
  const { toast } = useToast();

  const handleContinue = () => {
    if (!selected) return;
    vendorSelect.mutate(selected, {
      onSuccess: () => onComplete(),
      onError: (err) => {
        toast({
          title: "Failed to save POS selection",
          description: err instanceof Error ? err.message : "Unknown error",
          variant: "destructive",
        });
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Connect Your POS</h1>
        <p className="text-muted-foreground mt-1">
          Select your point-of-sale system to sync orders automatically.
          You can connect it later from settings.
        </p>
      </div>

      <POSVendorSelector selected={selected} onSelect={setSelected} />

      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleContinue}
          className="flex-1"
          disabled={!selected || vendorSelect.isPending}
        >
          {vendorSelect.isPending ? "Saving..." : "Continue"}
        </Button>
        <Button variant="ghost" onClick={onSkip}>
          Skip for now
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/onboarding/pos-vendor-step.tsx
git commit -m "feat: add POS vendor selection onboarding step component"
```

### Task 5: Wire POS vendor step into onboarding flow

**Files:**
- Modify: `frontend/src/app/account/onboarding/page.tsx`

- [ ] **Step 1: Update the onboarding page**

Make the following changes to `frontend/src/app/account/onboarding/page.tsx`:

1. Add import for the new step:
```typescript
import { POSVendorStep } from "@/components/onboarding/pos-vendor-step";
```

2. Update the `Step` type to include `"pos-vendor"`:
```typescript
type Step = "preferences" | "owner-question" | "restaurant-details" | "menu-upload" | "pos-vendor";
```

3. Update `totalSteps` calculation (line 26):
```typescript
const totalSteps = step === "restaurant-details" || step === "menu-upload" || step === "pos-vendor" ? 5 : 2;
```

4. Update `currentStep` calculation (lines 27-30):
```typescript
const currentStep =
  step === "preferences" ? 1 :
  step === "owner-question" ? 2 :
  step === "restaurant-details" ? 3 :
  step === "menu-upload" ? 4 : 5;
```

5. In the `menu-upload` step rendering, change `onComplete={handleComplete}` and `onSkip={handleComplete}` to advance to pos-vendor instead:
```tsx
{step === "menu-upload" && restaurantSlug && (
  <MenuUploadStep slug={restaurantSlug} onComplete={() => setStep("pos-vendor")} onSkip={() => setStep("pos-vendor")} />
)}
```

6. Add the new step rendering after the menu-upload block:
```tsx
{step === "pos-vendor" && restaurantSlug && (
  <POSVendorStep slug={restaurantSlug} onComplete={handleComplete} onSkip={handleComplete} />
)}
```

- [ ] **Step 2: Verify the app compiles**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -5` (or `npx tsc --noEmit`)
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/onboarding/page.tsx
git commit -m "feat: add POS vendor step to onboarding flow (step 5 of 5)"
```

### Task 6: Wire POS vendor step into register-restaurant flow

**Files:**
- Modify: `frontend/src/app/account/register-restaurant/page.tsx`

- [ ] **Step 1: Update the register-restaurant page**

Make the following changes to `frontend/src/app/account/register-restaurant/page.tsx`:

1. Add import:
```typescript
import { POSVendorStep } from "@/components/onboarding/pos-vendor-step";
```

2. Update `Step` type:
```typescript
type Step = "details" | "menu" | "pos-vendor";
```

3. Update `totalSteps`:
```typescript
const totalSteps = 3;
```

4. Update `currentStep`:
```typescript
const currentStep = step === "details" ? 1 : step === "menu" ? 2 : 3;
```

5. Change the menu step's `onComplete` and `onSkip` to advance to pos-vendor:
```tsx
{step === "menu" && restaurantSlug && (
  <MenuUploadStep
    slug={restaurantSlug}
    onComplete={() => setStep("pos-vendor")}
    onSkip={() => setStep("pos-vendor")}
  />
)}
```

6. Add the new step after the menu block:
```tsx
{step === "pos-vendor" && restaurantSlug && (
  <POSVendorStep
    slug={restaurantSlug}
    onComplete={handleComplete}
    onSkip={handleComplete}
  />
)}
```

- [ ] **Step 2: Verify the app compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/register-restaurant/page.tsx
git commit -m "feat: add POS vendor step to register-restaurant flow (step 3 of 3)"
```

---

## Chunk 4: Frontend — Refactor Integrations Settings Page

### Task 7: Refactor integrations page to use `POSVendorSelector`

**Files:**
- Modify: `frontend/src/app/account/restaurants/[slug]/settings/integrations/page.tsx`

- [ ] **Step 1: Refactor the integrations page**

Replace the "Connect Square" / "Connect Toast (Coming Soon)" buttons section with `POSVendorSelector`. The page should handle three states:

1. **No vendor selected** (`pos_type === "none"` and `!isConnected`): Show `POSVendorSelector` with a "Save" button. On save, call `usePOSVendorSelect`.
2. **Vendor selected, not connected** (`pos_type !== "none"` and `!isConnected`): Show the selected vendor name, a "Connect" button to kick off OAuth, and a "Change" button to re-show the selector.
3. **Connected** (`isConnected`): Keep existing UI — status card, location selector, payment mode, disconnect.

Full replacement for the page:

```tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  usePOSConnect,
  usePOSConnection,
  usePOSConnectionUpdate,
  usePOSDisconnect,
} from "@/hooks/use-pos-connection";
import { usePOSVendorSelect } from "@/hooks/use-pos-vendor-select";
import { POSVendorSelector } from "@/components/pos-vendor-selector";

export default function POSIntegrationsPage() {
  const params = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const slug = params.slug;

  const { data: connection, isLoading, error } = usePOSConnection(slug);
  const connect = usePOSConnect();
  const disconnect = usePOSDisconnect(slug);
  const updateConnection = usePOSConnectionUpdate(slug);
  const vendorSelect = usePOSVendorSelect(slug);

  const [locationId, setLocationId] = useState("");
  const [selectedVendor, setSelectedVendor] = useState<string | null>(null);
  const [isChanging, setIsChanging] = useState(false);

  useEffect(() => {
    if (connection?.external_location_id != null) {
      setLocationId(connection.external_location_id);
    }
  }, [connection?.external_location_id]);

  const justConnected = searchParams.get("connected");
  const oauthError = searchParams.get("error");

  if (isLoading) {
    return <div className="p-6">Loading...</div>;
  }

  if (error) {
    return (
      <div className="p-6 text-destructive">
        Failed to load POS connection. Please try again later.
      </div>
    );
  }

  const isConnected = connection?.is_connected ?? false;
  const posType = connection?.pos_type ?? "none";
  const isVendorSelected = posType !== "none" && !isConnected;
  const showSelector = (!isVendorSelected && !isConnected) || isChanging;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">POS Integration</h1>

      {justConnected && (
        <div className="rounded-md bg-success/10 p-4 text-success">
          Successfully connected to {justConnected}!
        </div>
      )}

      {oauthError && (
        <div className="rounded-md bg-destructive/10 p-4 text-destructive">
          Failed to connect. Please try again.
        </div>
      )}

      {/* Vendor Selection */}
      {showSelector && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">Select Your POS</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose your point-of-sale system to sync orders automatically.
          </p>
          <div className="mt-4">
            <POSVendorSelector
              selected={selectedVendor}
              onSelect={setSelectedVendor}
            />
          </div>
          <div className="mt-4 flex gap-3">
            <Button
              variant="gradient"
              onClick={() => {
                if (!selectedVendor) return;
                vendorSelect.mutate(selectedVendor, {
                  onSuccess: () => setIsChanging(false),
                });
              }}
              disabled={!selectedVendor || vendorSelect.isPending}
            >
              {vendorSelect.isPending ? "Saving..." : "Save"}
            </Button>
            {isChanging && (
              <Button variant="ghost" onClick={() => setIsChanging(false)}>
                Cancel
              </Button>
            )}
          </div>
        </Card>
      )}

      {/* Vendor Selected, Not Connected */}
      {isVendorSelected && !isChanging && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">Connection Status</h2>
          <div className="mt-4 flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-amber-400" />
            <span className="capitalize">{posType}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-600 font-medium">
              Not Connected
            </span>
          </div>
          <div className="mt-4 flex gap-3">
            <Button
              variant="gradient"
              onClick={() => connect.mutate({ slug, posType })}
              disabled={connect.isPending}
            >
              {connect.isPending ? "Connecting..." : `Connect ${posType.charAt(0).toUpperCase() + posType.slice(1)}`}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setSelectedVendor(posType);
                setIsChanging(true);
              }}
            >
              Change
            </Button>
          </div>
        </Card>
      )}

      {/* Connected */}
      {isConnected && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">Connection Status</h2>
          <div className="mt-4 flex items-center gap-3">
            <span className="h-3 w-3 rounded-full bg-success" />
            <span>Connected to {posType}</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">Active</span>
          </div>
          <Button
            variant="outline"
            className="mt-4 border-destructive text-destructive hover:bg-destructive/10"
            onClick={() => {
              if (window.confirm("Disconnect POS? Orders will no longer sync.")) {
                disconnect.mutate();
              }
            }}
            disabled={disconnect.isPending}
          >
            Disconnect
          </Button>
        </Card>
      )}

      {/* Location Selector */}
      {isConnected && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">POS Location</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter the location ID from your POS dashboard for the location that should receive QR orders.
          </p>
          <div className="mt-4 flex gap-3">
            <Input
              type="text"
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              placeholder="e.g., L1234ABC (Square) or GUID (Toast)"
              className="flex-1"
            />
            <Button
              variant="gradient"
              onClick={() =>
                updateConnection.mutate({ external_location_id: locationId })
              }
              disabled={updateConnection.isPending || locationId === (connection?.external_location_id ?? "")}
            >
              {updateConnection.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </Card>
      )}

      {/* Payment Mode */}
      {isConnected && (
        <Card className="bg-card border border-border rounded-2xl p-6">
          <h2 className="text-lg font-semibold">Payment Mode</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose how payments are collected for QR orders.
          </p>
          <div className="mt-4 space-y-3">
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="payment_mode"
                value="stripe"
                checked={connection?.payment_mode === "stripe"}
                onChange={() =>
                  updateConnection.mutate({ payment_mode: "stripe" })
                }
                className="mt-1"
              />
              <div>
                <div className="font-medium">Pay online (Stripe)</div>
                <div className="text-sm text-muted-foreground">
                  Customers pay through the app. Orders appear as paid in your POS.
                </div>
              </div>
            </label>
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="payment_mode"
                value="pos_collected"
                checked={connection?.payment_mode === "pos_collected"}
                onChange={() =>
                  updateConnection.mutate({ payment_mode: "pos_collected" })
                }
                className="mt-1"
              />
              <div>
                <div className="font-medium">Pay at counter (POS)</div>
                <div className="text-sm text-muted-foreground">
                  Orders are sent to your POS. Customers pay at the counter or table.
                </div>
              </div>
            </label>
          </div>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the app compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/restaurants/\[slug\]/settings/integrations/page.tsx
git commit -m "refactor: replace hardcoded POS buttons with shared POSVendorSelector on integrations page"
```

---

## Chunk 5: Final Verification

### Task 8: Full test suite and manual smoke test

- [ ] **Step 1: Run backend test suite**

Run: `cd backend && python -m pytest integrations/tests/ -v`
Expected: All tests pass, no regressions.

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npx next build --no-lint 2>&1 | tail -10`
Expected: Build succeeds.

- [ ] **Step 4: Manual smoke test checklist**

Verify these flows work:
1. Go to `/account/onboarding` as a new user — complete all 5 steps, selecting Square on step 5
2. Go to `/account/register-restaurant` — complete all 3 steps, skip POS vendor step
3. Go to `/account/restaurants/{slug}/settings/integrations` — see vendor selector, select Square, see "Connect" button
4. On integrations page — click "Change", select a different vendor, save
