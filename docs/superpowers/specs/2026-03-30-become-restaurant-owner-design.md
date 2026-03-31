# Become a Restaurant Owner — Design Spec

## Problem

Customers who completed onboarding as diners have no way to register a restaurant. The "Do you own a restaurant?" question only appears during initial onboarding, and the "My Restaurants" link in the header is hidden until `is_restaurant_owner` is `true`. There is no discoverable path for existing customers to become restaurant owners.

## Solution

Add a CTA card on the profile page that links to a new restaurant registration wizard, reusing the existing onboarding step components.

## User Flow

1. Customer visits `/account/profile`
2. Sees a green CTA card at the top: "Own a restaurant? Register your restaurant and start accepting QR orders" with a "Get Started" button
3. Clicks "Get Started" → confirmation dialog appears showing the two steps (restaurant details + optional menu upload) and a note that everything is editable later
4. Clicks "Continue" → navigates to `/account/register-restaurant`
5. **Step 1 — Restaurant Details:** Name, URL slug, phone (optional), address with Google Places autocomplete (optional). Submits via `POST /api/restaurants/`
6. **Step 2 — Menu Upload (optional):** Upload menu photos or skip. Uses existing `MenuUploadModal`
7. On completion → redirects to `/account/restaurants` (My Restaurants list)

After restaurant creation, `is_restaurant_owner` returns `true` automatically, and the "My Restaurants" header link appears.

## Backend Changes

None. The existing `POST /api/restaurants/` endpoint already:
- Sets the authenticated user as `owner`
- Creates a `RestaurantStaff` entry with role `owner`
- Creates a trial `Subscription` (14-day trial)
- The `is_restaurant_owner` property on the User model is computed from these relationships

## Frontend Changes

### 1. New page: `frontend/src/app/account/register-restaurant/page.tsx`

A two-step wizard page:
- Requires authentication (`useRequireAuth`)
- If user already owns a restaurant, redirect to `/account/restaurants`
- **Step 1:** Renders `RestaurantDetailsStep` component
  - `onCreated(slug)` → advances to step 2, stores slug in state
  - `onBack` → navigates back to `/account/profile`
- **Step 2:** Renders `MenuUploadStep` component
  - `onComplete` → redirects to `/account/restaurants`
  - `onSkip` → redirects to `/account/restaurants`
- Includes step indicator (reuse the same numbered-circle pattern from onboarding)

### 2. Modified page: `frontend/src/app/account/profile/page.tsx`

Add a CTA card at the top of the page (before "Basic Information" card):
- **Condition:** Only shown when `profile.owns_restaurant === false` (uses `owns_restaurant` rather than `is_restaurant_owner` so that staff members who don't own a restaurant can still see the CTA)
- **Design:** Green gradient background (`bg-gradient-to-r from-green-50 to-emerald-50`), border (`border-green-300`), Store icon from lucide-react, heading "Own a restaurant?", description text, "Get Started" button
- **Interaction:** Clicking "Get Started" opens a shadcn `AlertDialog`

Confirmation dialog content:
- **Title:** "Register Your Restaurant"
- **Body:** Numbered step list — (1) Restaurant details: name, address, contact info. (2) Menu upload (optional): upload a photo or PDF of your menu. Footer note: "You can edit everything later from your dashboard."
- **Actions:** Cancel (closes dialog) / Continue (navigates to `/account/register-restaurant`)

### 3. Modified hook: `frontend/src/hooks/use-create-restaurant.ts`

Add `["profile"]` to the query invalidation in `onSuccess` so that the header's "My Restaurants" link appears immediately after restaurant creation (without requiring a page refresh):

```ts
onSuccess: () => {
  queryClient.invalidateQueries({ queryKey: ["my-restaurants"] });
  queryClient.invalidateQueries({ queryKey: ["profile"] });
},
```

### Components Reused (no modifications)

- `RestaurantDetailsStep` (`frontend/src/components/onboarding/restaurant-details-step.tsx`) — props: `onCreated(slug)`, `onBack()`
- `MenuUploadStep` (`frontend/src/components/onboarding/menu-upload-step.tsx`) — props: `slug`, `onComplete()`, `onSkip()`
- `useProfile` hook (`frontend/src/hooks/use-profile.ts`)
- `useRequireAuth` hook (`frontend/src/hooks/use-auth.ts`)

### Components Used from shadcn/ui

- `AlertDialog`, `AlertDialogTrigger`, `AlertDialogContent`, `AlertDialogHeader`, `AlertDialogTitle`, `AlertDialogDescription`, `AlertDialogFooter`, `AlertDialogCancel`, `AlertDialogAction`
- `Card`, `Button`

## Edge Cases

- **User already owns a restaurant:** CTA card is hidden on profile (checked via `owns_restaurant`). Direct navigation to `/account/register-restaurant` redirects to `/account/restaurants`.
- **Staff member who doesn't own a restaurant:** CTA card is visible since `owns_restaurant` is `false` (even though `is_restaurant_owner` is `true`). They can register their own restaurant.
- **User creates a second restaurant:** Not blocked — the backend supports multiple restaurants per owner. The CTA hides after the first restaurant is created since `is_restaurant_owner` becomes `true`. Users can create additional restaurants from the `/account/restaurants` page which already has a "+ New Restaurant" button.
- **Restaurant creation fails:** Error toast is shown by the existing `RestaurantDetailsStep` component. User stays on step 1.
- **Browser back during wizard:** Standard Next.js routing handles this. User returns to previous step or profile page.

## Testing

- Verify CTA card appears for non-owner users on profile page
- Verify CTA card is hidden for existing restaurant owners
- Verify confirmation dialog opens and Cancel/Continue work correctly
- Verify restaurant details step creates restaurant successfully
- Verify menu upload step works (upload and skip paths)
- Verify redirect to `/account/restaurants` after completion
- Verify "My Restaurants" header link appears after registration
- Verify direct navigation to `/account/register-restaurant` by an owner redirects
- Verify unauthenticated users are redirected to login
- Verify staff members (non-owners) can see the CTA and register their own restaurant
