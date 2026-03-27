# Menu Upload with AI Parsing — Design Spec

## Overview

Restaurant owners can upload photos of their physical menu, and an AI agent parses the images into structured menu data. The owner reviews and edits the parsed result, then saves it as a new menu version with the option to overwrite or append to the existing menu. Menus are versioned, allowing rollback and named menu sets (e.g. Lunch, Dinner).

## Data Model

### New Model: `MenuVersion`

| Field | Type | Notes |
|-------|------|-------|
| `restaurant` | FK → Restaurant | |
| `name` | CharField(255) | e.g. "Lunch Menu", "Menu - Mar 27, 2026" |
| `is_active` | BooleanField | Default `False`. Only one per restaurant is `True`. |
| `source` | CharField choices | `"manual"` or `"ai_upload"` |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

**Active version constraint:** Enforced in application logic — when activating a version, deactivate all others in a single transaction.

### Changes to Existing Models

- `MenuCategory` gains a required FK → `MenuVersion`. The existing `restaurant` FK on `MenuCategory` is **removed** — restaurant is now derived via `category.version.restaurant`. All existing queries filtering `MenuCategory` by `restaurant` must be updated to filter by the active `MenuVersion` instead.
- `MenuItem` is unchanged (still FK → `MenuCategory`). Items are implicitly scoped to a version through their category. The existing `is_active` field on `MenuItem` and `MenuCategory` is preserved and still respected — an item must be `is_active=True` AND belong to the active version to appear in the customer-facing menu.
- `MenuItemVariant` and `MenuItemModifier` are unchanged.

### Integration: Existing Menu Queries

The following query paths must be updated to filter by active `MenuVersion` instead of directly by `Restaurant`:

- `build_menu_context()` in `backend/orders/llm/menu_context.py` — used by the order parsing agent
- Public menu API endpoint (`/api/order/<slug>/menu/`)
- Admin menu API endpoint (`/api/restaurants/<slug>/menu/`)
- Any other views/serializers that query `MenuCategory.objects.filter(restaurant=...)`

### Migration

A data migration creates a `MenuVersion(name="Default", is_active=True, source="manual")` for each existing restaurant and reassigns all existing `MenuCategory` records to it. The `restaurant` FK column is dropped from `MenuCategory` after reassignment.

### Default Version Naming

When the user does not provide a version name, auto-generate: `"Menu - Mar 27, 2026"`. If a version with that name already exists for the restaurant, append a counter: `"Menu - Mar 27, 2026 (2)"`, `"Menu - Mar 27, 2026 (3)"`, etc.

## AI Agent Architecture

Two agents, both following the existing `BaseAgent` pattern from `backend/ai/base_agent.py`.

### 1. MenuParsingAgent (Vision)

- **Model:** `gpt-4o` (hardcoded, ignores `LLM_MODEL` setting — a vision-capable model is required)
- **Input:** Single menu photo image
- **Output:** `ParsedMenuPage` (structured Pydantic model)
- **Behavior:** One instance per uploaded photo, all run in parallel via `concurrent.futures.ThreadPoolExecutor`
- **Prompt:** Instructed to extract categories, items with names/descriptions, and size/price variants

### 2. MenuMergeAgent (Text)

- **Model:** `gpt-4o-mini`
- **Input:** Array of `ParsedMenuPage` results from all photos
- **Output:** `ParsedMenu` — deduplicated, unified menu
- **Behavior:** Merges duplicate categories (e.g. "Drinks" appearing on two pages), resolves naming inconsistencies, produces a single clean menu structure

### Pydantic Schemas

```python
class ParsedMenuVariant(BaseModel):
    label: str        # e.g. "Regular", "Small", "Large"
    price: Decimal = Field(max_digits=8, decimal_places=2)

class ParsedMenuItem(BaseModel):
    name: str
    description: str | None
    variants: list[ParsedMenuVariant] = Field(min_length=1)

class ParsedMenuCategory(BaseModel):
    name: str
    items: list[ParsedMenuItem]

class ParsedMenuPage(BaseModel):
    categories: list[ParsedMenuCategory]

class ParsedMenu(BaseModel):
    categories: list[ParsedMenuCategory]
```

## API Design

All endpoints under `/api/restaurants/<slug>/`.

### `POST /menu/upload/parse/`

- **Auth:** Restaurant owner/manager
- **Content-Type:** `multipart/form-data`
- **Body:** Multiple image files (field name: `images`)
- **Flow:**
  1. Validate images (type, size, count ≤ 10)
  2. Run `MenuParsingAgent` in parallel — one per photo
  3. Run `MenuMergeAgent` on combined results
  4. Return merged `ParsedMenu` JSON
- **Timeout:** This is a synchronous request. With up to 10 photos, expect 10-30 seconds. The view sets a 120-second timeout. If any individual photo parse fails, it is excluded and the merge proceeds with successful results. If all fail, return `422`.
- **Image validation:** Max 10MB per file. Accepted types: JPEG, PNG, HEIC/HEIF.
- **Response:** `200 OK` with `ParsedMenu` body

### `POST /menu/upload/save/`

- **Auth:** Restaurant owner/manager
- **Content-Type:** `application/json`
- **Body:**
  ```json
  {
    "menu": { "categories": [...] },
    "mode": "overwrite" | "append",
    "version_name": "Lunch Menu"  // optional
  }
  ```
- **Flow:**
  - **Overwrite:** Create new `MenuVersion`, populate with parsed items, set as active. Previous version is deactivated but preserved.
  - **Append:** Create new `MenuVersion`, bulk-copy all categories/items/variants/modifiers from current active version (using `bulk_create`), then add parsed items, set as active.
- **Response:** `201 Created` with new `MenuVersion` and full menu data

### `GET /menu/versions/`

- **Auth:** Restaurant owner/manager
- **Response:** List of versions with `id`, `name`, `is_active`, `source`, `created_at`, `item_count`

### `PATCH /menu/versions/<id>/`

- **Auth:** Restaurant owner/manager
- **Body:** `{ "name": "New Name" }`
- **Response:** Updated version

### `POST /menu/versions/<id>/activate/`

- **Auth:** Restaurant owner/manager
- **Flow:** Deactivate all versions for restaurant, activate this one
- **Response:** `200 OK` with activated version

### `DELETE /menu/versions/<id>/`

- **Auth:** Restaurant owner/manager
- **Constraint:** Cannot delete the active version
- **Response:** `204 No Content`

## Frontend Flow

The upload flow lives on the existing menu management page (`/account/restaurants/[slug]/menu/`).

### Menu Page Additions

- **"Upload Menu Photos" button** — purple accent, next to existing "Add Category" button
- **Version indicator** — shows active version name, link to version management
- **Version selector** — dropdown to view/switch between versions

### Upload Modal (4 steps)

**Step 1 — Upload:**
- Drag & drop zone for multiple photos
- File list with remove buttons
- Supports JPG, PNG, HEIC, up to 10 photos
- "Parse Menu with AI" button

**Step 2 — Parsing (loading):**
- Progress indicator
- "Analyzing your menu photos..." message
- Estimated time: 10-15 seconds

**Step 3 — Review & Edit:**
- Parsed categories shown as collapsible sections
- Each item has inline-editable fields: name, description, price/variants
- Remove buttons on items and categories
- Overwrite / Append toggle (two cards, user clicks to select)
- Version name input with auto-generated placeholder
- "Save Menu" button

**Step 4 — Success:**
- Confirmation message, menu page refreshes to show new version

### Version Management

On the menu page itself (no separate page):
- **Version picker** — dropdown showing all versions with active indicator
- **Per-version actions:** Activate, Rename, Delete (cannot delete active)
- **Version metadata:** name, created date, source (manual/AI), item count

## Error Handling

- **Image validation:** Reject non-image files, files over 10MB, more than 10 files
- **Parse failure:** Show error toast, allow retry. Individual photo failures don't block others — merge whatever succeeded.
- **Empty parse:** If AI extracts nothing from a photo, warn user and exclude it from merge
- **Save conflicts:** If active version changed between parse and save, warn user

## Scope Exclusions

- **Modifiers:** AI does not extract modifiers (add-ons). Owners add these manually.
- **Item images:** AI does not extract item photos from menu images.
- **Scheduled version switching:** Manual only for now. Data model supports future scheduling.
- **Bulk edit after save:** Standard menu management handles post-save edits.
