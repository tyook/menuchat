# Menu Upload with AI Parsing — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable restaurant owners to upload menu photos, parse them with AI into structured menu data, review/edit, and save as versioned menus.

**Architecture:** New `MenuVersion` model scopes categories to versions. Two LLM agents (vision parser + text merger) extract menu data from photos in parallel. Frontend upload modal on the existing menu page with editable preview. Version management (activate, rename, delete) on the same page.

**Tech Stack:** Django + DRF (backend), Next.js + React + shadcn/ui (frontend), OpenAI GPT-4o (vision), GPT-4o-mini (merge), agno framework (agent orchestration), concurrent.futures (parallelism), @tanstack/react-query (data fetching)

---

## File Structure

### Backend — New Files
- `backend/restaurants/models.py` — Add `MenuVersion` model (modify existing)
- `backend/restaurants/migrations/XXXX_add_menu_version.py` — Schema + data migration
- `backend/restaurants/llm/__init__.py` — New package for menu LLM agents
- `backend/restaurants/llm/schemas.py` — Pydantic schemas for parsed menu data
- `backend/restaurants/llm/parse_agent.py` — `MenuParsingAgent` (vision, GPT-4o)
- `backend/restaurants/llm/merge_agent.py` — `MenuMergeAgent` (text, GPT-4o-mini)
- `backend/restaurants/services/menu_upload_service.py` — Orchestration: parallel parse, merge, save
- `backend/restaurants/services/menu_version_service.py` — Version CRUD: activate, rename, delete, default naming
- `backend/restaurants/serializers/menu_upload_serializers.py` — Serializers for upload/save/version endpoints
- `backend/restaurants/views_menu_upload.py` — Views for parse, save, version CRUD

### Backend — Modified Files
- `backend/restaurants/models.py` — Add `MenuVersion`, modify `MenuCategory` FK
- `backend/restaurants/urls.py` — Add new URL patterns
- `backend/restaurants/services/restaurant_service.py` — Update `get_full_menu` to use active version
- `backend/restaurants/serializers/restaurant_serializers.py` — Update `MenuCategorySerializer` (remove restaurant field)
- `backend/restaurants/views.py` — Update `MenuCategoryListCreateView`, `MenuCategoryDetailView`, `MenuItemListCreateView` to scope by version
- `backend/restaurants/tests/factories.py` — Update `MenuCategoryFactory` to use `MenuVersionFactory`
- `backend/orders/llm/menu_context.py` — Update `build_menu_context` to use active version
- `backend/orders/services.py` — Update `OrderService.get_public_menu` to use active version

### Frontend — New Files
- `frontend/src/types/index.ts` — Add `MenuVersion`, `ParsedMenu` types (modify existing)
- `frontend/src/lib/api.ts` — Add menu upload/version API functions (modify existing)
- `frontend/src/hooks/use-menu-versions.ts` — React Query hooks for version CRUD
- `frontend/src/hooks/use-menu-upload.ts` — React Query hooks for parse/save
- `frontend/src/components/menu-upload-modal.tsx` — Upload modal (drag & drop → parse → review → save)
- `frontend/src/components/parsed-menu-editor.tsx` — Editable preview of parsed menu
- `frontend/src/components/version-picker.tsx` — Version dropdown with activate/rename/delete

### Frontend — Modified Files
- `frontend/src/app/account/restaurants/[slug]/menu/page.tsx` — Add upload button, version picker

### Test Files
- `backend/restaurants/tests/test_menu_version_model.py`
- `backend/restaurants/tests/test_menu_version_service.py`
- `backend/restaurants/tests/test_menu_upload_service.py`
- `backend/restaurants/tests/test_menu_upload_views.py`
- `backend/restaurants/tests/test_menu_upload_serializers.py`
- `backend/restaurants/tests/test_llm_agents.py`
- `backend/restaurants/tests/test_migration.py`

---

## Chunk 1: Data Model & Migration

### Task 1: Add MenuVersion Model

**Files:**
- Modify: `backend/restaurants/models.py`
- Test: `backend/restaurants/tests/test_menu_version_model.py`

- [ ] **Step 1: Write test for MenuVersion model**

Create `backend/restaurants/tests/test_menu_version_model.py`:

```python
import pytest
from django.db import IntegrityError
from restaurants.models import MenuVersion, Restaurant, MenuCategory


@pytest.mark.django_db
class TestMenuVersionModel:
    def test_create_menu_version(self, restaurant):
        version = MenuVersion.objects.create(
            restaurant=restaurant,
            name="Lunch Menu",
            source="manual",
        )
        assert version.name == "Lunch Menu"
        assert version.source == "manual"
        assert version.is_active is False
        assert version.restaurant == restaurant

    def test_str_representation(self, restaurant):
        version = MenuVersion.objects.create(
            restaurant=restaurant, name="Dinner", source="manual"
        )
        assert str(version) == "Dinner"

    def test_source_choices(self, restaurant):
        version = MenuVersion.objects.create(
            restaurant=restaurant, name="AI Menu", source="ai_upload"
        )
        assert version.source == "ai_upload"

    def test_ordering_by_created_at(self, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="V1", source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="V2", source="manual"
        )
        versions = list(MenuVersion.objects.filter(restaurant=restaurant))
        assert versions == [v2, v1]  # newest first
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_version_model.py -v`
Expected: FAIL — `MenuVersion` not defined

- [ ] **Step 3: Add MenuVersion model**

Add to `backend/restaurants/models.py` after the `RestaurantStaff` model (around line 97):

```python
class MenuVersion(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        AI_UPLOAD = "ai_upload", "AI Upload"

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="menu_versions"
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
```

- [ ] **Step 4: Add version FK to MenuCategory**

In `backend/restaurants/models.py`, modify the `MenuCategory` model:

Replace the `restaurant` FK with a `version` FK:
```python
class MenuCategory(models.Model):
    version = models.ForeignKey(
        MenuVersion, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.name
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_version_model.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/tests/test_menu_version_model.py
git commit -m "feat: add MenuVersion model, update MenuCategory FK to version"
```

### Task 2: Create Schema & Data Migration

**Files:**
- Create: `backend/restaurants/migrations/` (auto-generated + data migration)

- [ ] **Step 1: Generate schema migration**

Run: `cd backend && python manage.py makemigrations restaurants`

This will generate a migration that:
- Creates the `MenuVersion` table
- Removes `restaurant` FK from `MenuCategory`
- Adds `version` FK to `MenuCategory`

Django may not handle this cleanly in one step since it's removing a required FK and adding a new one. If needed, split into multiple operations.

- [ ] **Step 2: Create data migration**

Run: `cd backend && python manage.py makemigrations restaurants --empty -n populate_menu_versions`

Edit the generated file:

```python
from django.db import migrations


def create_default_versions(apps, schema_editor):
    Restaurant = apps.get_model("restaurants", "Restaurant")
    MenuVersion = apps.get_model("restaurants", "MenuVersion")
    MenuCategory = apps.get_model("restaurants", "MenuCategory")

    for restaurant in Restaurant.objects.all():
        version = MenuVersion.objects.create(
            restaurant=restaurant,
            name="Default",
            is_active=True,
            source="manual",
        )
        MenuCategory.objects.filter(restaurant=restaurant).update(version=version)


def reverse_migration(apps, schema_editor):
    MenuCategory = apps.get_model("restaurants", "MenuCategory")
    MenuVersion = apps.get_model("restaurants", "MenuVersion")

    for version in MenuVersion.objects.select_related("restaurant").all():
        MenuCategory.objects.filter(version=version).update(
            restaurant=version.restaurant
        )
    MenuVersion.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("restaurants", "XXXX_auto_YYYYMMDD"),  # Replace with the migration filename generated in Step 1
    ]

    operations = [
        migrations.RunPython(create_default_versions, reverse_migration),
    ]
```

Note: The exact migration order may need adjustment. The approach is:
1. First migration: Add `MenuVersion` model, add nullable `version` FK to `MenuCategory` (keep `restaurant` FK)
2. Data migration: Create default versions, assign categories
3. Third migration: Remove `restaurant` FK from `MenuCategory`, make `version` FK non-nullable

- [ ] **Step 3: Run migrations**

Run: `cd backend && python manage.py migrate`
Expected: All migrations apply successfully

- [ ] **Step 4: Verify migration in shell**

Run: `cd backend && python manage.py shell -c "from restaurants.models import MenuVersion, MenuCategory; print(MenuVersion.objects.count(), MenuCategory.objects.filter(version__isnull=True).count())"`
Expected: Shows version count > 0 and 0 orphaned categories

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/migrations/
git commit -m "feat: add migrations for MenuVersion and MenuCategory FK update"
```

### Task 3: Update Existing Queries to Use Active Version

**Files:**
- Modify: `backend/orders/llm/menu_context.py`
- Modify: `backend/restaurants/services/restaurant_service.py`
- Modify: `backend/restaurants/views.py`
- Modify: `backend/orders/views.py`
- Modify: `backend/restaurants/serializers/restaurant_serializers.py`

- [ ] **Step 1: Update build_menu_context**

In `backend/orders/llm/menu_context.py`, update the query to filter by active version:

```python
def build_menu_context(restaurant):
    active_version = restaurant.menu_versions.filter(is_active=True).first()
    if not active_version:
        return f"Restaurant: {restaurant.name}\n\nNo menu available."

    categories = (
        MenuCategory.objects.filter(version=active_version, is_active=True)
        .prefetch_related(
            Prefetch("items", queryset=MenuItem.objects.filter(is_active=True)),
            "items__variants",
            "items__modifiers",
        )
    )
    # ... rest of the function stays the same, iterating over categories
```

- [ ] **Step 2: Update RestaurantService.get_full_menu**

In `backend/restaurants/services/restaurant_service.py`, update `get_full_menu`:

```python
@staticmethod
def get_full_menu(restaurant):
    active_version = restaurant.menu_versions.filter(is_active=True).first()
    if not active_version:
        return {"restaurant_name": restaurant.name, "categories": []}

    categories = (
        MenuCategory.objects.filter(version=active_version)
        .prefetch_related("items__variants", "items__modifiers")
    )
    # ... rest uses same serialization pattern
```

- [ ] **Step 3: Update MenuCategoryListCreateView**

In `backend/restaurants/views.py`, update the category view to scope by active version:

```python
class MenuCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = MenuCategorySerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = restaurant.menu_versions.filter(is_active=True).first()
        if not active_version:
            return MenuCategory.objects.none()
        return MenuCategory.objects.filter(version=active_version)

    def perform_create(self, serializer):
        restaurant = self.get_restaurant()
        active_version = restaurant.menu_versions.filter(is_active=True).first()
        if not active_version:
            active_version = MenuVersion.objects.create(
                restaurant=restaurant, name="Default", is_active=True, source="manual"
            )
        serializer.save(version=active_version)
```

- [ ] **Step 4: Update MenuItemListCreateView**

In `backend/restaurants/views.py`, update item view similarly — the serializer context should include the active version so category validation works:

```python
class MenuItemListCreateView(generics.ListCreateAPIView):
    serializer_class = MenuItemSerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = restaurant.menu_versions.filter(is_active=True).first()
        if not active_version:
            return MenuItem.objects.none()
        return MenuItem.objects.filter(
            category__version=active_version
        ).prefetch_related("variants", "modifiers")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        restaurant = self.get_restaurant()
        ctx["restaurant"] = restaurant
        active_version = restaurant.menu_versions.filter(is_active=True).first()
        ctx["active_version"] = active_version
        return ctx
```

- [ ] **Step 4b: Update MenuCategoryDetailView**

In `backend/restaurants/views.py`, update `MenuCategoryDetailView` to scope its queryset by active version instead of restaurant:

```python
class MenuCategoryDetailView(RestaurantMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MenuCategorySerializer

    def get_queryset(self):
        restaurant = self.get_restaurant()
        active_version = restaurant.menu_versions.filter(is_active=True).first()
        if not active_version:
            return MenuCategory.objects.none()
        return MenuCategory.objects.filter(version=active_version)
```

- [ ] **Step 5: Update MenuCategorySerializer**

In `backend/restaurants/serializers/restaurant_serializers.py`, update `MenuCategorySerializer` to no longer reference `restaurant`:

```python
class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ["id", "name", "sort_order", "is_active"]
```

- [ ] **Step 6: Update MenuItemSerializer category validation**

In `backend/restaurants/serializers/restaurant_serializers.py`, update the `create` method of `MenuItemSerializer` to validate category belongs to the active version (not restaurant):

```python
def create(self, validated_data):
    active_version = self.context.get("active_version")
    category = validated_data.get("category")
    if active_version and category.version_id != active_version.id:
        raise serializers.ValidationError("Category does not belong to the active menu version.")
    # ... rest of create logic
```

- [ ] **Step 7: Update OrderService.get_public_menu in orders app**

In `backend/orders/services.py`, update `OrderService.get_public_menu` to filter categories by the active `MenuVersion` instead of by restaurant directly:

```python
@staticmethod
def get_public_menu(slug):
    restaurant = Restaurant.objects.get(slug=slug)
    active_version = restaurant.menu_versions.filter(is_active=True).first()
    if not active_version:
        return {"restaurant_name": restaurant.name, "categories": [], ...}

    categories = (
        MenuCategory.objects.filter(version=active_version, is_active=True)
        .prefetch_related(
            Prefetch("items", queryset=MenuItem.objects.filter(is_active=True)),
            "items__variants",
            "items__modifiers",
        )
    )
    # ... rest uses PublicMenuCategorySerializer on the filtered categories
```

- [ ] **Step 8: Run full test suite**

Run: `cd backend && python -m pytest --tb=short`
Expected: All existing tests pass (some may need fixture updates to create a MenuVersion)

- [ ] **Step 9: Update test factories and conftest**

Update `backend/restaurants/tests/factories.py` — add `MenuVersionFactory` and update `MenuCategoryFactory`:

```python
class MenuVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuVersion

    restaurant = factory.SubFactory(RestaurantFactory)
    name = "Default"
    is_active = True
    source = "manual"


class MenuCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuCategory

    version = factory.SubFactory(MenuVersionFactory)  # was: restaurant = factory.SubFactory(RestaurantFactory)
    name = factory.Sequence(lambda n: f"Category {n}")
```

Add shared pytest fixtures to `backend/conftest.py` (or `backend/restaurants/tests/conftest.py`):

```python
@pytest.fixture
def menu_version(restaurant):
    return MenuVersion.objects.create(
        restaurant=restaurant, name="Default", is_active=True, source="manual"
    )

@pytest.fixture
def category(menu_version):
    return MenuCategory.objects.create(version=menu_version, name="Appetizers")
```

- [ ] **Step 10: Fix any remaining broken tests**

Run: `cd backend && python -m pytest --tb=short`

Fix any remaining test failures caused by `MenuCategory` now requiring a `version` FK. Tests across `orders/tests/` and `integrations/tests/` that use `MenuCategoryFactory` should auto-resolve from the factory update in Step 9.

- [ ] **Step 11: Commit**

```bash
git add backend/restaurants/tests/factories.py backend/conftest.py backend/restaurants/ backend/orders/ backend/integrations/
git commit -m "refactor: update all menu queries to use active MenuVersion"
```

---

## Chunk 2: AI Agents (Backend)

### Task 4: Create Pydantic Schemas for Menu Parsing

**Files:**
- Create: `backend/restaurants/llm/__init__.py`
- Create: `backend/restaurants/llm/schemas.py`
- Test: `backend/restaurants/tests/test_llm_agents.py`

- [ ] **Step 1: Write test for schemas**

Create `backend/restaurants/tests/test_llm_agents.py`:

```python
import pytest
from decimal import Decimal
from pydantic import ValidationError
from restaurants.llm.schemas import (
    ParsedMenuVariant,
    ParsedMenuItem,
    ParsedMenuCategory,
    ParsedMenuPage,
    ParsedMenu,
)


class TestParsedMenuSchemas:
    def test_valid_variant(self):
        v = ParsedMenuVariant(label="Regular", price=Decimal("9.99"))
        assert v.label == "Regular"
        assert v.price == Decimal("9.99")

    def test_variant_price_precision(self):
        v = ParsedMenuVariant(label="Large", price=Decimal("12.50"))
        assert v.price == Decimal("12.50")

    def test_item_requires_at_least_one_variant(self):
        with pytest.raises(ValidationError):
            ParsedMenuItem(name="Burger", description=None, variants=[])

    def test_valid_item(self):
        item = ParsedMenuItem(
            name="Burger",
            description="Juicy beef burger",
            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
        )
        assert item.name == "Burger"
        assert len(item.variants) == 1

    def test_item_description_optional(self):
        item = ParsedMenuItem(
            name="Fries",
            description=None,
            variants=[ParsedMenuVariant(label="Regular", price=Decimal("5.00"))],
        )
        assert item.description is None

    def test_valid_category(self):
        cat = ParsedMenuCategory(
            name="Mains",
            items=[
                ParsedMenuItem(
                    name="Burger",
                    description=None,
                    variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                )
            ],
        )
        assert cat.name == "Mains"
        assert len(cat.items) == 1

    def test_parsed_menu_page(self):
        page = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Drinks",
                    items=[
                        ParsedMenuItem(
                            name="Cola",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("3.00"))],
                        )
                    ],
                )
            ]
        )
        assert len(page.categories) == 1

    def test_parsed_menu(self):
        menu = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Appetizers",
                    items=[
                        ParsedMenuItem(
                            name="Spring Rolls",
                            description="Crispy veggie rolls",
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("8.50"))],
                        )
                    ],
                )
            ]
        )
        assert len(menu.categories) == 1
        assert menu.categories[0].items[0].name == "Spring Rolls"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_llm_agents.py::TestParsedMenuSchemas -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create schemas**

Create `backend/restaurants/llm/__init__.py` (empty file).

Create `backend/restaurants/llm/schemas.py`:

```python
from decimal import Decimal
from pydantic import BaseModel, Field


class ParsedMenuVariant(BaseModel):
    label: str
    price: Decimal = Field(max_digits=8, decimal_places=2)


class ParsedMenuItem(BaseModel):
    name: str
    description: str | None = None
    variants: list[ParsedMenuVariant] = Field(min_length=1)


class ParsedMenuCategory(BaseModel):
    name: str
    items: list[ParsedMenuItem]


class ParsedMenuPage(BaseModel):
    categories: list[ParsedMenuCategory]


class ParsedMenu(BaseModel):
    categories: list[ParsedMenuCategory]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_llm_agents.py::TestParsedMenuSchemas -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/llm/ backend/restaurants/tests/test_llm_agents.py
git commit -m "feat: add Pydantic schemas for menu parsing"
```

### Task 5: Create MenuParsingAgent (Vision)

**Files:**
- Create: `backend/restaurants/llm/parse_agent.py`
- Test: `backend/restaurants/tests/test_llm_agents.py` (append)

- [ ] **Step 1: Write test for MenuParsingAgent**

Append to `backend/restaurants/tests/test_llm_agents.py`:

```python
from unittest.mock import patch, MagicMock
from restaurants.llm.parse_agent import MenuParsingAgent


class TestMenuParsingAgent:
    def test_agent_name(self):
        agent = MenuParsingAgent()
        assert agent.get_name() == "MenuParsingAgent"

    def test_output_schema(self):
        agent = MenuParsingAgent()
        assert agent.get_output_schema() is ParsedMenuPage

    def test_default_model_is_gpt4o(self):
        agent = MenuParsingAgent()
        assert agent.default_model == "gpt-4o"

    @patch("restaurants.llm.parse_agent.MenuParsingAgent._build_agent")
    def test_run_returns_parsed_page(self, mock_build):
        mock_result = MagicMock()
        mock_result.content = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description="Beef burger",
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result
        mock_build.return_value = mock_agent

        result = MenuParsingAgent.run(image_data=b"fake-image-bytes")
        assert isinstance(result, ParsedMenuPage)
        assert result.categories[0].name == "Mains"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_llm_agents.py::TestMenuParsingAgent -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create MenuParsingAgent**

Create `backend/restaurants/llm/parse_agent.py`:

```python
import base64

from ai.base_agent import BaseAgent
from restaurants.llm.schemas import ParsedMenuPage

INSTRUCTIONS = """You are a menu parser. Given a photo of a restaurant menu, extract all items into structured data.

Rules:
- Extract every category heading you see (e.g. "Appetizers", "Mains", "Drinks")
- For each item, extract the name, description (if visible), and all price variants
- If an item has a single price, create one variant with label "Regular"
- If an item has size/price options (e.g. Small $8, Large $12), create a variant for each
- Prices must be numeric (no currency symbols)
- If a description is not visible, set it to null
- Do not invent items or prices — only extract what is clearly visible
- If text is unclear or cut off, make your best reasonable interpretation
"""


class MenuParsingAgent(BaseAgent):
    default_model = "gpt-4o"

    def get_name(self):
        return "MenuParsingAgent"

    def get_instructions(self):
        return INSTRUCTIONS

    def get_output_schema(self):
        return ParsedMenuPage

    def _resolve_model(self):
        """Override to bypass settings.LLM_MODEL — a vision-capable model is required,
        so we always use gpt-4o regardless of the global LLM_MODEL setting."""
        from ai.models import resolve_model
        return resolve_model(self.default_model)

    def get_context(self, **kwargs):
        return {}

    @classmethod
    def run(cls, image_data: bytes, **kwargs):
        """Run vision parsing on a single menu image.

        Args:
            image_data: Raw image bytes

        Uses agno's Image class to pass the image to the model.
        See agno docs: https://docs.agno.com/models/multimodal
        """
        from agno.media import Image as AgnoImage

        instance = cls()
        agent = instance._build_agent(**kwargs)
        result = agent.run(
            "Parse the menu from this photo.",
            images=[AgnoImage(content=image_data)],
        )
        return result.content
```

Note: The `agno.media.Image` class accepts `content` (raw bytes) or `url` (image URL). Verify the exact import path against the installed agno version and adjust if needed. If `agno.media` does not exist, try `from agno.models.message import Image`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_llm_agents.py::TestMenuParsingAgent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/llm/parse_agent.py backend/restaurants/tests/test_llm_agents.py
git commit -m "feat: add MenuParsingAgent for vision-based menu parsing"
```

### Task 6: Create MenuMergeAgent (Text)

**Files:**
- Create: `backend/restaurants/llm/merge_agent.py`
- Test: `backend/restaurants/tests/test_llm_agents.py` (append)

- [ ] **Step 1: Write test for MenuMergeAgent**

Append to `backend/restaurants/tests/test_llm_agents.py`:

```python
from restaurants.llm.merge_agent import MenuMergeAgent


class TestMenuMergeAgent:
    def test_agent_name(self):
        agent = MenuMergeAgent()
        assert agent.get_name() == "MenuMergeAgent"

    def test_output_schema(self):
        agent = MenuMergeAgent()
        assert agent.get_output_schema() is ParsedMenu

    def test_default_model_is_gpt4o_mini(self):
        agent = MenuMergeAgent()
        assert agent.default_model == "gpt-4o-mini"

    @patch("restaurants.llm.merge_agent.MenuMergeAgent._build_agent")
    def test_run_merges_pages(self, mock_build):
        page1 = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Drinks",
                    items=[
                        ParsedMenuItem(
                            name="Cola",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("3.00"))],
                        )
                    ],
                )
            ]
        )
        page2 = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Drinks",
                    items=[
                        ParsedMenuItem(
                            name="Sprite",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("3.00"))],
                        )
                    ],
                )
            ]
        )
        merged = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Drinks",
                    items=[
                        ParsedMenuItem(name="Cola", description=None, variants=[ParsedMenuVariant(label="Regular", price=Decimal("3.00"))]),
                        ParsedMenuItem(name="Sprite", description=None, variants=[ParsedMenuVariant(label="Regular", price=Decimal("3.00"))]),
                    ],
                )
            ]
        )
        mock_result = MagicMock()
        mock_result.content = merged
        mock_agent = MagicMock()
        mock_agent.run.return_value = mock_result
        mock_build.return_value = mock_agent

        result = MenuMergeAgent.run(pages=[page1, page2])
        assert isinstance(result, ParsedMenu)
        assert len(result.categories) == 1
        assert len(result.categories[0].items) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_llm_agents.py::TestMenuMergeAgent -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create MenuMergeAgent**

Create `backend/restaurants/llm/merge_agent.py`:

```python
import json

from ai.base_agent import BaseAgent
from restaurants.llm.schemas import ParsedMenu, ParsedMenuPage

INSTRUCTIONS = """You are a menu organizer. You receive parsed menu data from multiple pages of a restaurant menu. Your job is to merge them into a single, clean, deduplicated menu.

Rules:
- Merge categories with the same or very similar names (e.g. "Drinks" and "Beverages" should become one category)
- Use the most common or most descriptive category name
- Remove duplicate items (same name and similar price)
- If the same item appears with different prices, keep the one that appears most frequently
- Preserve all unique items
- Order categories logically: appetizers/starters first, then mains, then sides, then desserts, then drinks
- Order items within each category alphabetically
- Do not invent new items or modify prices
"""


class MenuMergeAgent(BaseAgent):
    default_model = "gpt-4o-mini"

    def get_name(self):
        return "MenuMergeAgent"

    def get_instructions(self):
        return INSTRUCTIONS

    def get_output_schema(self):
        return ParsedMenu

    def get_context(self, **kwargs):
        pages = kwargs.get("pages", [])
        pages_json = json.dumps(
            [page.model_dump(mode="json") for page in pages], indent=2
        )
        return {"parsed_menu_pages": pages_json}

    @classmethod
    def run(cls, pages: list[ParsedMenuPage], **kwargs):
        """Merge multiple parsed menu pages into a single unified menu.

        Args:
            pages: List of ParsedMenuPage results from parallel parsing
        """
        if len(pages) == 1:
            return ParsedMenu(categories=pages[0].categories)

        instance = cls()
        agent = instance._build_agent(pages=pages, **kwargs)
        result = agent.run("Merge these menu pages into a single unified menu.")
        return result.content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_llm_agents.py::TestMenuMergeAgent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/llm/merge_agent.py backend/restaurants/tests/test_llm_agents.py
git commit -m "feat: add MenuMergeAgent for deduplicating parsed menu pages"
```

---

## Chunk 3: Backend Services & API

### Task 7: Create MenuVersionService

**Files:**
- Create: `backend/restaurants/services/menu_version_service.py`
- Test: `backend/restaurants/tests/test_menu_version_service.py`

- [ ] **Step 1: Write tests for MenuVersionService**

Create `backend/restaurants/tests/test_menu_version_service.py`:

```python
import pytest
from django.utils import timezone
from restaurants.models import MenuVersion, MenuCategory, MenuItem, MenuItemVariant, MenuItemModifier, Restaurant
from restaurants.services.menu_version_service import MenuVersionService


@pytest.mark.django_db
class TestMenuVersionService:
    def test_generate_default_name(self, restaurant):
        name = MenuVersionService.generate_default_name(restaurant)
        today = timezone.now().strftime("%b %d, %Y")
        assert name == f"Menu - {today}"

    def test_generate_default_name_with_duplicate(self, restaurant):
        today = timezone.now().strftime("%b %d, %Y")
        MenuVersion.objects.create(
            restaurant=restaurant, name=f"Menu - {today}", source="manual"
        )
        name = MenuVersionService.generate_default_name(restaurant)
        assert name == f"Menu - {today} (2)"

    def test_activate_version(self, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="V1", is_active=True, source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="V2", is_active=False, source="manual"
        )
        MenuVersionService.activate_version(restaurant, v2)
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True

    def test_cannot_delete_active_version(self, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Active", is_active=True, source="manual"
        )
        with pytest.raises(ValueError, match="Cannot delete the active menu version"):
            MenuVersionService.delete_version(v)

    def test_delete_inactive_version(self, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=False, source="manual"
        )
        version_id = v.id
        MenuVersionService.delete_version(v)
        assert not MenuVersion.objects.filter(id=version_id).exists()

    def test_rename_version(self, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Old Name", source="manual"
        )
        MenuVersionService.rename_version(v, "New Name")
        v.refresh_from_db()
        assert v.name == "New Name"

    def test_list_versions_with_item_count(self, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="V1", is_active=True, source="manual"
        )
        cat = MenuCategory.objects.create(version=v, name="Mains")
        MenuItem.objects.create(category=cat, name="Burger")
        MenuItem.objects.create(category=cat, name="Fries")

        versions = MenuVersionService.list_versions(restaurant)
        assert len(versions) == 1
        assert versions[0]["item_count"] == 2

    def test_duplicate_version(self, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="Original", is_active=True, source="manual"
        )
        cat = MenuCategory.objects.create(version=v1, name="Mains")
        item = MenuItem.objects.create(category=cat, name="Burger", description="Beef")
        MenuItemVariant.objects.create(menu_item=item, label="Regular", price="12.00")
        MenuItemModifier.objects.create(menu_item=item, name="Cheese", price_adjustment="1.50")

        v2 = MenuVersionService.duplicate_version(v1, "Copy")
        assert v2.name == "Copy"
        assert v2.categories.count() == 1
        new_cat = v2.categories.first()
        assert new_cat.name == "Mains"
        assert new_cat.items.count() == 1
        new_item = new_cat.items.first()
        assert new_item.name == "Burger"
        assert new_item.variants.count() == 1
        assert new_item.modifiers.count() == 1

    def test_duplicate_version_into(self, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="Source", is_active=True, source="manual"
        )
        cat = MenuCategory.objects.create(version=v1, name="Mains")
        item = MenuItem.objects.create(category=cat, name="Burger", description="Beef")
        MenuItemVariant.objects.create(menu_item=item, label="Regular", price="12.00")
        MenuItemModifier.objects.create(menu_item=item, name="Cheese", price_adjustment="1.50")

        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="Target", source="ai_upload"
        )
        MenuVersionService.duplicate_version_into(v1, v2)
        assert v2.categories.count() == 1
        new_item = v2.categories.first().items.first()
        assert new_item.name == "Burger"
        assert new_item.variants.count() == 1
        assert new_item.modifiers.count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_version_service.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create MenuVersionService**

Create `backend/restaurants/services/menu_version_service.py`:

```python
from django.db import transaction
from django.utils import timezone

from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    MenuVersion,
)


class MenuVersionService:
    @staticmethod
    def generate_default_name(restaurant):
        today = timezone.now().strftime("%b %d, %Y")
        base_name = f"Menu - {today}"
        if not MenuVersion.objects.filter(restaurant=restaurant, name=base_name).exists():
            return base_name
        counter = 2
        while MenuVersion.objects.filter(
            restaurant=restaurant, name=f"{base_name} ({counter})"
        ).exists():
            counter += 1
        return f"{base_name} ({counter})"

    @staticmethod
    @transaction.atomic
    def activate_version(restaurant, version):
        MenuVersion.objects.filter(restaurant=restaurant, is_active=True).update(
            is_active=False
        )
        version.is_active = True
        version.save(update_fields=["is_active", "updated_at"])

    @staticmethod
    def delete_version(version):
        if version.is_active:
            raise ValueError("Cannot delete the active menu version.")
        version.delete()

    @staticmethod
    def rename_version(version, new_name):
        version.name = new_name
        version.save(update_fields=["name", "updated_at"])

    @staticmethod
    def list_versions(restaurant):
        versions = MenuVersion.objects.filter(restaurant=restaurant)
        result = []
        for v in versions:
            item_count = MenuItem.objects.filter(category__version=v).count()
            result.append(
                {
                    "id": v.id,
                    "name": v.name,
                    "is_active": v.is_active,
                    "source": v.source,
                    "created_at": v.created_at,
                    "item_count": item_count,
                }
            )
        return result

    @staticmethod
    def duplicate_version_into(source_version, target_version):
        """Copy all categories/items/variants/modifiers from source into target version."""
        for old_cat in source_version.categories.prefetch_related(
            "items__variants", "items__modifiers"
        ):
            new_cat = MenuCategory.objects.create(
                version=target_version,
                name=old_cat.name,
                sort_order=old_cat.sort_order,
                is_active=old_cat.is_active,
            )
            for old_item in old_cat.items.all():
                new_item = MenuItem.objects.create(
                    category=new_cat,
                    name=old_item.name,
                    description=old_item.description,
                    image_url=old_item.image_url,
                    is_active=old_item.is_active,
                    sort_order=old_item.sort_order,
                )
                MenuItemVariant.objects.bulk_create([
                    MenuItemVariant(
                        menu_item=new_item,
                        label=v.label,
                        price=v.price,
                        is_default=v.is_default,
                    )
                    for v in old_item.variants.all()
                ])
                MenuItemModifier.objects.bulk_create([
                    MenuItemModifier(
                        menu_item=new_item,
                        name=m.name,
                        price_adjustment=m.price_adjustment,
                    )
                    for m in old_item.modifiers.all()
                ])

    @staticmethod
    @transaction.atomic
    def duplicate_version(source_version, new_name):
        new_version = MenuVersion.objects.create(
            restaurant=source_version.restaurant,
            name=new_name,
            source=source_version.source,
        )
        MenuVersionService.duplicate_version_into(source_version, new_version)
        return new_version
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_version_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/services/menu_version_service.py backend/restaurants/tests/test_menu_version_service.py
git commit -m "feat: add MenuVersionService for version CRUD operations"
```

### Task 8: Create MenuUploadService

**Files:**
- Create: `backend/restaurants/services/menu_upload_service.py`
- Test: `backend/restaurants/tests/test_menu_upload_service.py`

- [ ] **Step 1: Write tests for MenuUploadService**

Create `backend/restaurants/tests/test_menu_upload_service.py`:

```python
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from restaurants.models import MenuVersion, MenuCategory, MenuItem, MenuItemVariant
from restaurants.services.menu_upload_service import MenuUploadService
from restaurants.llm.schemas import (
    ParsedMenu,
    ParsedMenuCategory,
    ParsedMenuItem,
    ParsedMenuVariant,
    ParsedMenuPage,
)


@pytest.mark.django_db
class TestMenuUploadServiceParse:
    @patch("restaurants.services.menu_upload_service.MenuParsingAgent")
    @patch("restaurants.services.menu_upload_service.MenuMergeAgent")
    def test_parse_single_image(self, mock_merge_cls, mock_parse_cls):
        page = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        mock_parse_cls.run.return_value = page

        result = MenuUploadService.parse_images([b"fake-image"])
        assert isinstance(result, ParsedMenu)
        assert len(result.categories) == 1
        # Single image skips merge
        mock_merge_cls.run.assert_not_called()

    @patch("restaurants.services.menu_upload_service.MenuParsingAgent")
    @patch("restaurants.services.menu_upload_service.MenuMergeAgent")
    def test_parse_multiple_images_calls_merge(self, mock_merge_cls, mock_parse_cls):
        page = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Drinks",
                    items=[
                        ParsedMenuItem(
                            name="Cola",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("3.00"))],
                        )
                    ],
                )
            ]
        )
        mock_parse_cls.run.return_value = page
        merged = ParsedMenu(categories=page.categories)
        mock_merge_cls.run.return_value = merged

        result = MenuUploadService.parse_images([b"img1", b"img2"])
        assert isinstance(result, ParsedMenu)
        mock_merge_cls.run.assert_called_once()

    @patch("restaurants.services.menu_upload_service.MenuParsingAgent")
    def test_parse_handles_individual_failure(self, mock_parse_cls):
        page = ParsedMenuPage(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        mock_parse_cls.run.side_effect = [page, Exception("API error")]

        result = MenuUploadService.parse_images([b"img1", b"img2"])
        assert isinstance(result, ParsedMenu)
        assert len(result.categories) == 1


@pytest.mark.django_db
class TestMenuUploadServiceSave:
    def test_save_overwrite_creates_new_version(self, restaurant):
        old_version = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=True, source="manual"
        )
        parsed = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description="Beef burger",
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        new_version = MenuUploadService.save_menu(
            restaurant=restaurant,
            parsed_menu=parsed,
            mode="overwrite",
            version_name="New Menu",
        )
        old_version.refresh_from_db()
        assert old_version.is_active is False
        assert new_version.is_active is True
        assert new_version.name == "New Menu"
        assert new_version.source == "ai_upload"
        assert new_version.categories.count() == 1
        assert MenuItem.objects.filter(category__version=new_version).count() == 1

    def test_save_append_copies_existing_items(self, restaurant):
        old_version = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=True, source="manual"
        )
        old_cat = MenuCategory.objects.create(version=old_version, name="Sides")
        old_item = MenuItem.objects.create(category=old_cat, name="Fries")
        MenuItemVariant.objects.create(menu_item=old_item, label="Regular", price="5.00")

        parsed = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        new_version = MenuUploadService.save_menu(
            restaurant=restaurant,
            parsed_menu=parsed,
            mode="append",
            version_name="Combined",
        )
        assert new_version.categories.count() == 2  # Sides + Mains
        total_items = MenuItem.objects.filter(category__version=new_version).count()
        assert total_items == 2  # Fries + Burger
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_upload_service.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create MenuUploadService**

Create `backend/restaurants/services/menu_upload_service.py`:

```python
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import transaction

from restaurants.llm.merge_agent import MenuMergeAgent
from restaurants.llm.parse_agent import MenuParsingAgent
from restaurants.llm.schemas import ParsedMenu, ParsedMenuPage
from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemModifier,
    MenuItemVariant,
    MenuVersion,
)
from restaurants.services.menu_version_service import MenuVersionService

logger = logging.getLogger(__name__)


class MenuUploadService:
    @staticmethod
    def parse_images(image_data_list: list[bytes]) -> ParsedMenu:
        """Parse menu images in parallel, then merge results."""
        pages: list[ParsedMenuPage] = []

        with ThreadPoolExecutor(max_workers=min(len(image_data_list), 5)) as executor:
            futures = {
                executor.submit(MenuParsingAgent.run, image_data=img): i
                for i, img in enumerate(image_data_list)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    page = future.result()
                    pages.append(page)
                except Exception:
                    logger.exception("Failed to parse menu image %d", idx)

        if not pages:
            raise ValueError("Failed to parse any menu images.")

        if len(pages) == 1:
            return ParsedMenu(categories=pages[0].categories)

        return MenuMergeAgent.run(pages=pages)

    @staticmethod
    @transaction.atomic
    def save_menu(restaurant, parsed_menu: ParsedMenu, mode: str, version_name: str | None = None):
        """Save parsed menu as a new version.

        Args:
            restaurant: Restaurant instance
            parsed_menu: The parsed (and possibly user-edited) menu data
            mode: "overwrite" or "append"
            version_name: Optional name. Auto-generated if not provided.
        """
        if not version_name:
            version_name = MenuVersionService.generate_default_name(restaurant)

        new_version = MenuVersion.objects.create(
            restaurant=restaurant,
            name=version_name,
            source=MenuVersion.Source.AI_UPLOAD,
        )

        if mode == "append":
            active_version = restaurant.menu_versions.filter(is_active=True).first()
            if active_version:
                MenuVersionService.duplicate_version_into(active_version, new_version)

        for cat_data in parsed_menu.categories:
            category = MenuCategory.objects.create(
                version=new_version,
                name=cat_data.name,
            )
            for item_data in cat_data.items:
                item = MenuItem.objects.create(
                    category=category,
                    name=item_data.name,
                    description=item_data.description or "",
                )
                variants = [
                    MenuItemVariant(
                        menu_item=item,
                        label=v.label,
                        price=v.price,
                        is_default=(i == 0),
                    )
                    for i, v in enumerate(item_data.variants)
                ]
                MenuItemVariant.objects.bulk_create(variants)

        MenuVersionService.activate_version(restaurant, new_version)
        return new_version
```

Note: `duplicate_version_into` and `duplicate_version` are already defined in `MenuVersionService` (Task 7).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_upload_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/services/menu_upload_service.py backend/restaurants/services/menu_version_service.py backend/restaurants/tests/test_menu_upload_service.py
git commit -m "feat: add MenuUploadService for parsing and saving uploaded menus"
```

### Task 9: Create Serializers for Upload & Version Endpoints

**Files:**
- Create: `backend/restaurants/serializers/menu_upload_serializers.py`
- Test: `backend/restaurants/tests/test_menu_upload_serializers.py`

- [ ] **Step 1: Write tests for serializers**

Create `backend/restaurants/tests/test_menu_upload_serializers.py`:

```python
import pytest
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from restaurants.serializers.menu_upload_serializers import (
    MenuUploadParseSerializer,
    MenuSaveSerializer,
    MenuVersionSerializer,
)


class TestMenuUploadParseSerializer:
    def test_valid_single_image(self):
        image = SimpleUploadedFile("menu.jpg", b"fake-image", content_type="image/jpeg")
        serializer = MenuUploadParseSerializer(data={"images": [image]})
        assert serializer.is_valid(), serializer.errors

    def test_rejects_non_image(self):
        file = SimpleUploadedFile("doc.pdf", b"fake", content_type="application/pdf")
        serializer = MenuUploadParseSerializer(data={"images": [file]})
        assert not serializer.is_valid()

    def test_rejects_too_many_images(self):
        images = [
            SimpleUploadedFile(f"menu{i}.jpg", b"fake", content_type="image/jpeg")
            for i in range(11)
        ]
        serializer = MenuUploadParseSerializer(data={"images": images})
        assert not serializer.is_valid()


class TestMenuSaveSerializer:
    def test_valid_overwrite(self):
        data = {
            "menu": {
                "categories": [
                    {
                        "name": "Mains",
                        "items": [
                            {
                                "name": "Burger",
                                "description": "Beef burger",
                                "variants": [{"label": "Regular", "price": "12.00"}],
                            }
                        ],
                    }
                ]
            },
            "mode": "overwrite",
        }
        serializer = MenuSaveSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_rejects_invalid_mode(self):
        data = {
            "menu": {"categories": []},
            "mode": "invalid",
        }
        serializer = MenuSaveSerializer(data=data)
        assert not serializer.is_valid()

    def test_version_name_optional(self):
        data = {
            "menu": {"categories": []},
            "mode": "overwrite",
        }
        serializer = MenuSaveSerializer(data=data)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestMenuVersionSerializer:
    def test_serializes_version(self, menu_version):
        serializer = MenuVersionSerializer(menu_version)
        data = serializer.data
        assert "id" in data
        assert data["name"] == menu_version.name
        assert "is_active" in data
        assert "source" in data
        assert "created_at" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_upload_serializers.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create serializers**

Create `backend/restaurants/serializers/menu_upload_serializers.py`:

```python
from rest_framework import serializers
from restaurants.models import MenuVersion


class MenuUploadParseSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=10,
    )

    def validate_images(self, images):
        max_size = 10 * 1024 * 1024  # 10MB
        for img in images:
            if img.size > max_size:
                raise serializers.ValidationError(
                    f"Image '{img.name}' exceeds 10MB limit."
                )
        return images


class ParsedVariantInput(serializers.Serializer):
    label = serializers.CharField()
    price = serializers.DecimalField(max_digits=8, decimal_places=2)


class ParsedItemInput(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    variants = ParsedVariantInput(many=True, min_length=1)


class ParsedCategoryInput(serializers.Serializer):
    name = serializers.CharField()
    items = ParsedItemInput(many=True)


class ParsedMenuInput(serializers.Serializer):
    categories = ParsedCategoryInput(many=True)


class MenuSaveSerializer(serializers.Serializer):
    menu = ParsedMenuInput()
    mode = serializers.ChoiceField(choices=["overwrite", "append"])
    version_name = serializers.CharField(required=False, allow_blank=True, default="")


class MenuVersionSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = MenuVersion
        fields = ["id", "name", "is_active", "source", "created_at", "item_count"]
        read_only_fields = fields

    def get_item_count(self, obj):
        from restaurants.models import MenuItem
        return MenuItem.objects.filter(category__version=obj).count()


class MenuVersionRenameSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_upload_serializers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/serializers/menu_upload_serializers.py backend/restaurants/tests/test_menu_upload_serializers.py
git commit -m "feat: add serializers for menu upload and version endpoints"
```

### Task 10: Create Views & URL Patterns

**Files:**
- Create: `backend/restaurants/views_menu_upload.py`
- Modify: `backend/restaurants/urls.py`
- Test: `backend/restaurants/tests/test_menu_upload_views.py`

- [ ] **Step 1: Write tests for views**

Create `backend/restaurants/tests/test_menu_upload_views.py`:

```python
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.test import override_settings
from rest_framework.test import APIClient
from restaurants.models import MenuVersion, MenuCategory, MenuItem, MenuItemVariant
from restaurants.llm.schemas import ParsedMenu, ParsedMenuCategory, ParsedMenuItem, ParsedMenuVariant


@pytest.mark.django_db
class TestMenuUploadParseView:
    def test_requires_auth(self, api_client, restaurant):
        resp = api_client.post(f"/api/restaurants/{restaurant.slug}/menu/upload/parse/")
        assert resp.status_code == 401

    @patch("restaurants.views_menu_upload.MenuUploadService.parse_images")
    def test_parse_returns_menu(self, mock_parse, auth_client, restaurant):
        mock_parse.return_value = ParsedMenu(
            categories=[
                ParsedMenuCategory(
                    name="Mains",
                    items=[
                        ParsedMenuItem(
                            name="Burger",
                            description=None,
                            variants=[ParsedMenuVariant(label="Regular", price=Decimal("12.00"))],
                        )
                    ],
                )
            ]
        )
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = SimpleUploadedFile("menu.jpg", b"fake-image-data", content_type="image/jpeg")
        resp = auth_client.post(
            f"/api/restaurants/{restaurant.slug}/menu/upload/parse/",
            {"images": [image]},
            format="multipart",
        )
        assert resp.status_code == 200
        assert "categories" in resp.json()


@pytest.mark.django_db
class TestMenuUploadSaveView:
    def test_save_overwrite(self, auth_client, restaurant):
        MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=True, source="manual"
        )
        data = {
            "menu": {
                "categories": [
                    {
                        "name": "Mains",
                        "items": [
                            {
                                "name": "Burger",
                                "description": "Beef",
                                "variants": [{"label": "Regular", "price": "12.00"}],
                            }
                        ],
                    }
                ]
            },
            "mode": "overwrite",
            "version_name": "New Menu",
        }
        resp = auth_client.post(
            f"/api/restaurants/{restaurant.slug}/menu/upload/save/",
            data,
            format="json",
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "New Menu"


@pytest.mark.django_db
class TestMenuVersionViews:
    def test_list_versions(self, auth_client, restaurant):
        MenuVersion.objects.create(
            restaurant=restaurant, name="V1", is_active=True, source="manual"
        )
        resp = auth_client.get(f"/api/restaurants/{restaurant.slug}/menu/versions/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_activate_version(self, auth_client, restaurant):
        v1 = MenuVersion.objects.create(
            restaurant=restaurant, name="V1", is_active=True, source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="V2", is_active=False, source="manual"
        )
        resp = auth_client.post(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v2.id}/activate/"
        )
        assert resp.status_code == 200
        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.is_active is False
        assert v2.is_active is True

    def test_rename_version(self, auth_client, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", source="manual"
        )
        resp = auth_client.patch(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v.id}/",
            {"name": "New Name"},
            format="json",
        )
        assert resp.status_code == 200
        v.refresh_from_db()
        assert v.name == "New Name"

    def test_delete_inactive_version(self, auth_client, restaurant):
        MenuVersion.objects.create(
            restaurant=restaurant, name="Active", is_active=True, source="manual"
        )
        v2 = MenuVersion.objects.create(
            restaurant=restaurant, name="Old", is_active=False, source="manual"
        )
        resp = auth_client.delete(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v2.id}/"
        )
        assert resp.status_code == 204

    def test_cannot_delete_active_version(self, auth_client, restaurant):
        v = MenuVersion.objects.create(
            restaurant=restaurant, name="Active", is_active=True, source="manual"
        )
        resp = auth_client.delete(
            f"/api/restaurants/{restaurant.slug}/menu/versions/{v.id}/"
        )
        assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_upload_views.py -v`
Expected: FAIL — views not created

- [ ] **Step 3: Create views**

Create `backend/restaurants/views_menu_upload.py`:

```python
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.llm.schemas import ParsedMenu
from restaurants.models import MenuVersion
from restaurants.serializers.menu_upload_serializers import (
    MenuSaveSerializer,
    MenuUploadParseSerializer,
    MenuVersionRenameSerializer,
    MenuVersionSerializer,
)
from restaurants.services.menu_upload_service import MenuUploadService
from restaurants.services.menu_version_service import MenuVersionService
from restaurants.views import RestaurantMixin


class MenuUploadParseView(RestaurantMixin, APIView):
    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = MenuUploadParseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_files = serializer.validated_data["images"]
        image_data = [f.read() for f in image_files]

        parsed_menu = MenuUploadService.parse_images(image_data)
        return Response(parsed_menu.model_dump(mode="json"))


class MenuUploadSaveView(RestaurantMixin, APIView):
    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = MenuSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        parsed_menu = ParsedMenu(**data["menu"])
        version_name = data.get("version_name") or None

        new_version = MenuUploadService.save_menu(
            restaurant=restaurant,
            parsed_menu=parsed_menu,
            mode=data["mode"],
            version_name=version_name,
        )
        return Response(
            MenuVersionSerializer(new_version).data,
            status=status.HTTP_201_CREATED,
        )


class MenuVersionListView(RestaurantMixin, APIView):
    def get(self, request, slug):
        restaurant = self.get_restaurant()
        versions = MenuVersion.objects.filter(restaurant=restaurant)
        serializer = MenuVersionSerializer(versions, many=True)
        return Response(serializer.data)


class MenuVersionDetailView(RestaurantMixin, APIView):
    def patch(self, request, slug, pk):
        restaurant = self.get_restaurant()
        version = _get_version_or_404(restaurant, pk)
        serializer = MenuVersionRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        MenuVersionService.rename_version(version, serializer.validated_data["name"])
        return Response(MenuVersionSerializer(version).data)

    def delete(self, request, slug, pk):
        restaurant = self.get_restaurant()
        version = _get_version_or_404(restaurant, pk)
        try:
            MenuVersionService.delete_version(version)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _get_version_or_404(restaurant, pk):
    """Shared helper to fetch a MenuVersion or raise NotFound."""
    try:
        return MenuVersion.objects.get(restaurant=restaurant, pk=pk)
    except MenuVersion.DoesNotExist:
        from rest_framework.exceptions import NotFound
        raise NotFound("Menu version not found.")


class MenuVersionActivateView(RestaurantMixin, APIView):
    def post(self, request, slug, pk):
        restaurant = self.get_restaurant()
        version = _get_version_or_404(restaurant, pk)
        MenuVersionService.activate_version(restaurant, version)
        return Response(MenuVersionSerializer(version).data)
```

- [ ] **Step 4: Add URL patterns**

Add to `backend/restaurants/urls.py`:

```python
from restaurants.views_menu_upload import (
    MenuUploadParseView,
    MenuUploadSaveView,
    MenuVersionActivateView,
    MenuVersionDetailView,
    MenuVersionListView,
)

# Add these URL patterns:
path("<slug:slug>/menu/upload/parse/", MenuUploadParseView.as_view()),
path("<slug:slug>/menu/upload/save/", MenuUploadSaveView.as_view()),
path("<slug:slug>/menu/versions/", MenuVersionListView.as_view()),
path("<slug:slug>/menu/versions/<int:pk>/", MenuVersionDetailView.as_view()),
path("<slug:slug>/menu/versions/<int:pk>/activate/", MenuVersionActivateView.as_view()),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest restaurants/tests/test_menu_upload_views.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/views_menu_upload.py backend/restaurants/urls.py backend/restaurants/tests/test_menu_upload_views.py
git commit -m "feat: add API views and URLs for menu upload and version management"
```

---

## Chunk 4: Frontend Implementation

### Task 11: Handle FormData in API Client

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Check if apiFetch sets Content-Type header**

Read `frontend/src/lib/api.ts` and check if the `apiFetch` function hardcodes `Content-Type: application/json`. If it does, it will break `FormData` uploads because the browser needs to set the `Content-Type` with the multipart boundary automatically.

- [ ] **Step 2: Update apiFetch to handle FormData**

If needed, modify `apiFetch` to skip setting `Content-Type` when the body is a `FormData` instance:

```typescript
const headers: Record<string, string> = {};
if (!(options?.body instanceof FormData)) {
  headers["Content-Type"] = "application/json";
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "fix: handle FormData in apiFetch — skip Content-Type for multipart"
```

### Task 12: Add TypeScript Types & API Functions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add types**

Add to `frontend/src/types/index.ts`:

```typescript
export interface MenuVersion {
  id: number;
  name: string;
  is_active: boolean;
  source: "manual" | "ai_upload";
  created_at: string;
  item_count: number;
}

export interface ParsedMenuVariant {
  label: string;
  price: string;
}

export interface ParsedMenuItem {
  name: string;
  description: string | null;
  variants: ParsedMenuVariant[];
}

export interface ParsedMenuCategory {
  name: string;
  items: ParsedMenuItem[];
}

export interface ParsedMenu {
  categories: ParsedMenuCategory[];
}
```

- [ ] **Step 2: Add API functions**

Add to `frontend/src/lib/api.ts`:

```typescript
export async function parseMenuImages(slug: string, images: File[]): Promise<ParsedMenu> {
  const formData = new FormData();
  images.forEach((img) => formData.append("images", img));
  return apiFetch<ParsedMenu>(`/api/restaurants/${slug}/menu/upload/parse/`, {
    method: "POST",
    body: formData,
    // Do not set Content-Type — browser sets it with boundary for multipart
  });
}

export async function saveUploadedMenu(
  slug: string,
  menu: ParsedMenu,
  mode: "overwrite" | "append",
  versionName?: string
): Promise<MenuVersion> {
  return apiFetch<MenuVersion>(`/api/restaurants/${slug}/menu/upload/save/`, {
    method: "POST",
    body: JSON.stringify({ menu, mode, version_name: versionName || "" }),
  });
}

export async function fetchMenuVersions(slug: string): Promise<MenuVersion[]> {
  return apiFetch<MenuVersion[]>(`/api/restaurants/${slug}/menu/versions/`);
}

export async function activateMenuVersion(slug: string, versionId: number): Promise<MenuVersion> {
  return apiFetch<MenuVersion>(`/api/restaurants/${slug}/menu/versions/${versionId}/activate/`, {
    method: "POST",
  });
}

export async function renameMenuVersion(slug: string, versionId: number, name: string): Promise<MenuVersion> {
  return apiFetch<MenuVersion>(`/api/restaurants/${slug}/menu/versions/${versionId}/`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function deleteMenuVersion(slug: string, versionId: number): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/menu/versions/${versionId}/`, {
    method: "DELETE",
  });
}
```

Note: For the `parseMenuImages` function, ensure the `apiFetch` function does NOT set `Content-Type` header when body is `FormData` — the browser must set it with the multipart boundary. Check if `apiFetch` currently hardcodes `Content-Type: application/json` and adjust accordingly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat: add TypeScript types and API functions for menu upload"
```

### Task 13: Create React Query Hooks

**Files:**
- Create: `frontend/src/hooks/use-menu-versions.ts`
- Create: `frontend/src/hooks/use-menu-upload.ts`

- [ ] **Step 1: Create version hooks**

Create `frontend/src/hooks/use-menu-versions.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchMenuVersions,
  activateMenuVersion,
  renameMenuVersion,
  deleteMenuVersion,
} from "@/lib/api";

export function useMenuVersions(slug: string) {
  return useQuery({
    queryKey: ["menu-versions", slug],
    queryFn: () => fetchMenuVersions(slug),
    enabled: !!slug,
  });
}

export function useActivateVersion(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: number) => activateMenuVersion(slug, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}

export function useRenameVersion(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ versionId, name }: { versionId: number; name: string }) =>
      renameMenuVersion(slug, versionId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
    },
  });
}

export function useDeleteVersion(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versionId: number) => deleteMenuVersion(slug, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
```

- [ ] **Step 2: Create upload hooks**

Create `frontend/src/hooks/use-menu-upload.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { parseMenuImages, saveUploadedMenu } from "@/lib/api";
import { ParsedMenu } from "@/types";

export function useParseMenuImages(slug: string) {
  return useMutation({
    mutationFn: (images: File[]) => parseMenuImages(slug, images),
  });
}

export function useSaveUploadedMenu(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      menu,
      mode,
      versionName,
    }: {
      menu: ParsedMenu;
      mode: "overwrite" | "append";
      versionName?: string;
    }) => saveUploadedMenu(slug, menu, mode, versionName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["menu-versions", slug] });
      queryClient.invalidateQueries({ queryKey: ["admin-menu", slug] });
    },
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/use-menu-versions.ts frontend/src/hooks/use-menu-upload.ts
git commit -m "feat: add React Query hooks for menu upload and version management"
```

### Task 14: Create ParsedMenuEditor Component

**Files:**
- Create: `frontend/src/components/parsed-menu-editor.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/parsed-menu-editor.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { ParsedMenu, ParsedMenuCategory, ParsedMenuItem, ParsedMenuVariant } from "@/types";

interface ParsedMenuEditorProps {
  menu: ParsedMenu;
  onChange: (menu: ParsedMenu) => void;
}

export function ParsedMenuEditor({ menu, onChange }: ParsedMenuEditorProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<number>>(new Set());

  const toggleCategory = (index: number) => {
    const next = new Set(collapsedCategories);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    setCollapsedCategories(next);
  };

  const updateCategory = (catIndex: number, updates: Partial<ParsedMenuCategory>) => {
    const categories = [...menu.categories];
    categories[catIndex] = { ...categories[catIndex], ...updates };
    onChange({ categories });
  };

  const removeCategory = (catIndex: number) => {
    onChange({ categories: menu.categories.filter((_, i) => i !== catIndex) });
  };

  const updateItem = (catIndex: number, itemIndex: number, updates: Partial<ParsedMenuItem>) => {
    const categories = [...menu.categories];
    const items = [...categories[catIndex].items];
    items[itemIndex] = { ...items[itemIndex], ...updates };
    categories[catIndex] = { ...categories[catIndex], items };
    onChange({ categories });
  };

  const removeItem = (catIndex: number, itemIndex: number) => {
    const categories = [...menu.categories];
    categories[catIndex] = {
      ...categories[catIndex],
      items: categories[catIndex].items.filter((_, i) => i !== itemIndex),
    };
    onChange({ categories });
  };

  const updateVariant = (
    catIndex: number,
    itemIndex: number,
    varIndex: number,
    updates: Partial<ParsedMenuVariant>
  ) => {
    const categories = [...menu.categories];
    const items = [...categories[catIndex].items];
    const variants = [...items[itemIndex].variants];
    variants[varIndex] = { ...variants[varIndex], ...updates };
    items[itemIndex] = { ...items[itemIndex], variants };
    categories[catIndex] = { ...categories[catIndex], items };
    onChange({ categories });
  };

  const totalItems = menu.categories.reduce((sum, cat) => sum + cat.items.length, 0);

  return (
    <div>
      <p className="text-sm text-muted-foreground mb-4">
        AI found <strong>{menu.categories.length}</strong> categories and{" "}
        <strong>{totalItems}</strong> items. Edit anything that looks off.
      </p>

      <div className="space-y-3">
        {menu.categories.map((cat, catIndex) => (
          <div key={catIndex} className="border rounded-lg">
            <div className="flex items-center justify-between bg-muted/50 px-4 py-2">
              <button
                className="flex items-center gap-2 font-semibold text-sm"
                onClick={() => toggleCategory(catIndex)}
              >
                {collapsedCategories.has(catIndex) ? (
                  <ChevronRight className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
                <Input
                  value={cat.name}
                  onChange={(e) => updateCategory(catIndex, { name: e.target.value })}
                  className="h-7 w-48 font-semibold"
                  onClick={(e) => e.stopPropagation()}
                />
                <span className="text-muted-foreground font-normal">
                  ({cat.items.length} items)
                </span>
              </button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => removeCategory(catIndex)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>

            {!collapsedCategories.has(catIndex) && (
              <div className="divide-y">
                {cat.items.map((item, itemIndex) => (
                  <div key={itemIndex} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 space-y-1">
                        <Input
                          value={item.name}
                          onChange={(e) =>
                            updateItem(catIndex, itemIndex, { name: e.target.value })
                          }
                          className="h-7 font-medium"
                        />
                        <Input
                          value={item.description || ""}
                          onChange={(e) =>
                            updateItem(catIndex, itemIndex, {
                              description: e.target.value || null,
                            })
                          }
                          placeholder="Description (optional)"
                          className="h-7 text-sm text-muted-foreground"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        {item.variants.map((variant, varIndex) => (
                          <div key={varIndex} className="flex items-center gap-1">
                            {item.variants.length > 1 && (
                              <Input
                                value={variant.label}
                                onChange={(e) =>
                                  updateVariant(catIndex, itemIndex, varIndex, {
                                    label: e.target.value,
                                  })
                                }
                                className="h-7 w-20 text-xs"
                              />
                            )}
                            <div className="flex items-center">
                              <span className="text-sm">$</span>
                              <Input
                                value={variant.price}
                                onChange={(e) =>
                                  updateVariant(catIndex, itemIndex, varIndex, {
                                    price: e.target.value,
                                  })
                                }
                                className="h-7 w-20 text-right"
                              />
                            </div>
                          </div>
                        ))}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => removeItem(catIndex, itemIndex)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/parsed-menu-editor.tsx
git commit -m "feat: add ParsedMenuEditor component for editing AI-parsed menus"
```

- [ ] **Step 3: Verify build passes**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors

### Task 15: Create MenuUploadModal Component

**Files:**
- Create: `frontend/src/components/menu-upload-modal.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/menu-upload-modal.tsx`:

```tsx
"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Upload, X, Loader2, Check } from "lucide-react";
import toast from "react-hot-toast";
import { ParsedMenu } from "@/types";
import { ParsedMenuEditor } from "./parsed-menu-editor";
import { useParseMenuImages, useSaveUploadedMenu } from "@/hooks/use-menu-upload";

interface MenuUploadModalProps {
  slug: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  hasExistingMenu: boolean;
}

type Step = "upload" | "parsing" | "review" | "success";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/heic", "image/heif"];
const MAX_FILES = 10;
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

export function MenuUploadModal({ slug, open, onOpenChange, hasExistingMenu }: MenuUploadModalProps) {
  const [step, setStep] = useState<Step>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [parsedMenu, setParsedMenu] = useState<ParsedMenu | null>(null);
  const [mode, setMode] = useState<"overwrite" | "append">("overwrite");
  const [versionName, setVersionName] = useState("");

  const parseMutation = useParseMenuImages(slug);
  const saveMutation = useSaveUploadedMenu(slug);

  const reset = () => {
    setStep("upload");
    setFiles([]);
    setParsedMenu(null);
    setMode("overwrite");
    setVersionName("");
  };

  const handleClose = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
        ACCEPTED_TYPES.includes(f.type)
      );
      setFiles((prev) => [...prev, ...droppedFiles].slice(0, MAX_FILES));
    },
    []
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...selected].slice(0, MAX_FILES));
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const validateFiles = (): boolean => {
    for (const f of files) {
      if (!ACCEPTED_TYPES.includes(f.type)) {
        toast.error(`${f.name} is not a supported image type.`);
        return false;
      }
      if (f.size > MAX_SIZE) {
        toast.error(`${f.name} exceeds 10MB limit.`);
        return false;
      }
    }
    return true;
  };

  const handleParse = async () => {
    if (!validateFiles()) return;
    setStep("parsing");
    try {
      const result = await parseMutation.mutateAsync(files);
      setParsedMenu(result);
      setStep("review");
    } catch {
      toast.error("Failed to parse menu photos. Please try again.");
      setStep("upload");
    }
  };

  const handleSave = async () => {
    if (!parsedMenu) return;
    try {
      await saveMutation.mutateAsync({ menu: parsedMenu, mode, versionName: versionName || undefined });
      setStep("success");
      toast.success("Menu saved successfully!");
      setTimeout(() => handleClose(false), 1500);
    } catch {
      toast.error("Failed to save menu. Please try again.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === "upload" && "Upload Menu Photos"}
            {step === "parsing" && "Analyzing Menu..."}
            {step === "review" && "Review Parsed Menu"}
            {step === "success" && "Menu Saved!"}
          </DialogTitle>
        </DialogHeader>

        {step === "upload" && (
          <div className="space-y-4">
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed rounded-xl p-10 text-center cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => document.getElementById("menu-file-input")?.click()}
            >
              <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="font-medium">Drop menu photos here or click to browse</p>
              <p className="text-sm text-muted-foreground mt-1">
                Up to {MAX_FILES} photos. JPG, PNG, HEIC supported.
              </p>
              <input
                id="menu-file-input"
                type="file"
                multiple
                accept={ACCEPTED_TYPES.join(",")}
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>

            {files.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {files.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 bg-muted rounded-lg px-3 py-1.5 text-sm"
                  >
                    {f.name}
                    <button onClick={() => removeFile(i)}>
                      <X className="h-3 w-3 text-muted-foreground" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <Button
              onClick={handleParse}
              disabled={files.length === 0}
              className="w-full bg-purple-600 hover:bg-purple-700"
            >
              Parse Menu with AI
            </Button>
          </div>
        )}

        {step === "parsing" && (
          <div className="py-12 text-center">
            <Loader2 className="h-8 w-8 mx-auto mb-3 animate-spin text-purple-600" />
            <p className="font-medium">Analyzing your menu photos...</p>
            <p className="text-sm text-muted-foreground mt-1">
              This usually takes 10-15 seconds
            </p>
          </div>
        )}

        {step === "review" && parsedMenu && (
          <div className="space-y-4">
            <ParsedMenuEditor menu={parsedMenu} onChange={setParsedMenu} />

            {hasExistingMenu && (
              <div className="grid grid-cols-2 gap-3">
                <button
                  className={`border rounded-lg p-3 text-center transition-colors ${
                    mode === "overwrite"
                      ? "border-purple-600 bg-purple-50"
                      : "border-border"
                  }`}
                  onClick={() => setMode("overwrite")}
                >
                  <p className="font-medium text-sm">Replace Entire Menu</p>
                  <p className="text-xs text-muted-foreground">
                    Discard current menu, use this one
                  </p>
                </button>
                <button
                  className={`border rounded-lg p-3 text-center transition-colors ${
                    mode === "append"
                      ? "border-purple-600 bg-purple-50"
                      : "border-border"
                  }`}
                  onClick={() => setMode("append")}
                >
                  <p className="font-medium text-sm">Add to Existing Menu</p>
                  <p className="text-xs text-muted-foreground">
                    Keep current items, add these
                  </p>
                </button>
              </div>
            )}

            <Input
              value={versionName}
              onChange={(e) => setVersionName(e.target.value)}
              placeholder="Version name (e.g. Lunch Menu, Spring 2026)"
            />

            <Button
              onClick={handleSave}
              disabled={saveMutation.isPending}
              className="w-full"
            >
              {saveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Save Menu
            </Button>
          </div>
        )}

        {step === "success" && (
          <div className="py-12 text-center">
            <Check className="h-8 w-8 mx-auto mb-3 text-green-600" />
            <p className="font-medium">Menu saved successfully!</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/menu-upload-modal.tsx
git commit -m "feat: add MenuUploadModal component with full upload flow"
```

- [ ] **Step 3: Verify build passes**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors

### Task 16: Create VersionPicker Component

**Files:**
- Create: `frontend/src/components/version-picker.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/version-picker.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDown, Check, Pencil, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { MenuVersion } from "@/types";
import {
  useMenuVersions,
  useActivateVersion,
  useRenameVersion,
  useDeleteVersion,
} from "@/hooks/use-menu-versions";

interface VersionPickerProps {
  slug: string;
}

export function VersionPicker({ slug }: VersionPickerProps) {
  const { data: versions, isLoading } = useMenuVersions(slug);
  const activateMutation = useActivateVersion(slug);
  const renameMutation = useRenameVersion(slug);
  const deleteMutation = useDeleteVersion(slug);

  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");

  if (isLoading || !versions) return null;

  const activeVersion = versions.find((v) => v.is_active);

  const handleActivate = async (versionId: number) => {
    try {
      await activateMutation.mutateAsync(versionId);
      toast.success("Menu version activated.");
    } catch {
      toast.error("Failed to activate version.");
    }
  };

  const handleStartRename = (version: MenuVersion) => {
    setRenamingId(version.id);
    setRenameValue(version.name);
  };

  const handleRename = async () => {
    if (!renamingId || !renameValue.trim()) return;
    try {
      await renameMutation.mutateAsync({ versionId: renamingId, name: renameValue.trim() });
      toast.success("Version renamed.");
    } catch {
      toast.error("Failed to rename version.");
    }
    setRenamingId(null);
  };

  const handleDelete = async (versionId: number) => {
    try {
      await deleteMutation.mutateAsync(versionId);
      toast.success("Version deleted.");
    } catch {
      toast.error("Cannot delete the active version.");
    }
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">
        Active: <strong>{activeVersion?.name || "None"}</strong>
      </span>

      {versions.length > 1 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              {versions.length} versions <ChevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            {versions.map((v) => (
              <div key={v.id}>
                {renamingId === v.id ? (
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <Input
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleRename()}
                      className="h-7 text-sm"
                      autoFocus
                    />
                    <Button size="sm" variant="ghost" onClick={handleRename}>
                      <Check className="h-3 w-3" />
                    </Button>
                  </div>
                ) : (
                  <DropdownMenuItem
                    className="flex items-center justify-between"
                    onSelect={(e) => e.preventDefault()}
                  >
                    <div className="flex items-center gap-2">
                      {v.is_active && <Check className="h-3 w-3 text-green-600" />}
                      <div>
                        <p className="text-sm font-medium">{v.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {v.item_count} items &middot; {v.source === "ai_upload" ? "AI" : "Manual"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {!v.is_active && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleActivate(v.id)}
                          className="h-6 text-xs"
                        >
                          Activate
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleStartRename(v)}
                        className="h-6 px-1"
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                      {!v.is_active && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 px-1 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(v.id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </DropdownMenuItem>
                )}
              </div>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/version-picker.tsx
git commit -m "feat: add VersionPicker component for menu version management"
```

- [ ] **Step 3: Verify build passes**

Run: `cd frontend && npx tsc --noEmit`
Expected: No TypeScript errors

### Task 17: Integrate into Menu Page

**Files:**
- Modify: `frontend/src/app/account/restaurants/[slug]/menu/page.tsx`

- [ ] **Step 1: Read the current menu page**

Read the full file to understand current structure before modifying.

- [ ] **Step 2: Add upload button, version picker, and modal**

Add to the menu page:

1. Import the new components:
```tsx
import { MenuUploadModal } from "@/components/menu-upload-modal";
import { VersionPicker } from "@/components/version-picker";
```

2. Add state for modal:
```tsx
const [uploadOpen, setUploadOpen] = useState(false);
```

3. Add the upload button next to existing "Add Category" button:
```tsx
<Button
  onClick={() => setUploadOpen(true)}
  className="bg-purple-600 hover:bg-purple-700"
>
  Upload Menu Photos
</Button>
```

4. Add the VersionPicker below the heading area:
```tsx
<VersionPicker slug={slug} />
```

5. Add the modal at the bottom of the component:
```tsx
<MenuUploadModal
  slug={slug}
  open={uploadOpen}
  onOpenChange={setUploadOpen}
  hasExistingMenu={!!adminMenu?.categories?.length}
/>
```

- [ ] **Step 3: Verify the page renders**

Run: `cd frontend && npm run dev`
Navigate to a restaurant's menu page and verify the upload button and version picker appear.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/account/restaurants/[slug]/menu/page.tsx
git commit -m "feat: integrate menu upload modal and version picker into menu page"
```

---

## Chunk 5: Testing & Polish

### Task 18: Install pillow-heif for HEIC Support

**Files:**
- Modify: `backend/pyproject.toml` (or `requirements.txt`)

- [ ] **Step 1: Install pillow-heif**

Run: `cd backend && poetry add pillow-heif`

This enables Pillow to validate HEIC/HEIF images in DRF's `ImageField`. Without it, HEIC uploads accepted by the frontend will be rejected by the backend serializer.

- [ ] **Step 2: Verify HEIC support**

Run: `cd backend && python -c "from pillow_heif import register_heif_opener; register_heif_opener(); print('HEIC support OK')"`
Expected: "HEIC support OK"

- [ ] **Step 3: Register HEIC opener in Django settings**

Add to `backend/config/settings.py` (or a startup file):

```python
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass
```

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/poetry.lock backend/config/settings.py
git commit -m "feat: add pillow-heif for HEIC image support in menu uploads"
```

### Task 19: End-to-End Verification

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Manual smoke test**

1. Start backend: `cd backend && python manage.py runserver`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to a restaurant's menu page
4. Verify version picker shows "Default" version
5. Click "Upload Menu Photos" button
6. Upload a menu photo
7. Verify the parsed menu appears in the review step
8. Edit an item name, verify it updates
9. Select "Replace Entire Menu" and save
10. Verify new version appears in version picker
11. Test activating/renaming/deleting versions

- [ ] **Step 4: Fix any issues found during smoke test**

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: end-to-end verification and fixes for menu upload feature"
```
