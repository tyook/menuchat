"""
Tests for MenuUploadService.

All LLM agent calls are mocked — no API key required.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from restaurants.llm.schemas import (
    ParsedMenu,
    ParsedMenuCategory,
    ParsedMenuItem,
    ParsedMenuPage,
    ParsedMenuVariant,
)
from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    MenuVersion,
    Restaurant,
)
from restaurants.services.menu_upload_service import MenuUploadService

User = get_user_model()


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def restaurant(db):
    owner = User.objects.create_user(email="upload_owner@example.com", password="testpass123")
    return Restaurant.objects.create(name="Upload Test", slug="upload-test", owner=owner)


def _make_parsed_menu(category_name="Mains", item_name="Burger", price="10.00") -> ParsedMenu:
    return ParsedMenu(
        categories=[
            ParsedMenuCategory(
                name=category_name,
                items=[
                    ParsedMenuItem(
                        name=item_name,
                        description="Tasty",
                        variants=[ParsedMenuVariant(label="Standard", price=Decimal(price))],
                    )
                ],
            )
        ]
    )


def _make_parsed_page(category_name="Mains") -> ParsedMenuPage:
    return ParsedMenuPage(
        categories=[
            ParsedMenuCategory(
                name=category_name,
                items=[
                    ParsedMenuItem(
                        name="Item",
                        variants=[ParsedMenuVariant(label="Standard", price=Decimal("5.00"))],
                    )
                ],
            )
        ]
    )


# ── parse_images ───────────────────────────────────────────────────────────────


class TestParseImages:
    def test_parse_single_image_skips_merge_llm_call(self):
        """Single image: parse runs once, merge short-circuits without LLM."""
        page = _make_parsed_page()
        expected = ParsedMenu(categories=page.categories)

        with (
            patch(
                "restaurants.services.menu_upload_service.MenuParsingAgent.run",
                return_value=page,
            ) as mock_parse,
            patch(
                "restaurants.services.menu_upload_service.MenuMergeAgent.run",
                return_value=expected,
            ) as mock_merge,
        ):
            result = MenuUploadService.parse_images([b"img1"])

        mock_parse.assert_called_once_with(image_data=b"img1")
        mock_merge.assert_called_once()
        assert result is expected

    def test_parse_multiple_images_calls_merge(self):
        """Multiple images: each is parsed separately, then merge is called."""
        page1 = _make_parsed_page("Starters")
        page2 = _make_parsed_page("Mains")
        merged = _make_parsed_menu("All")

        parse_returns = [page1, page2]

        with (
            patch(
                "restaurants.services.menu_upload_service.MenuParsingAgent.run",
                side_effect=parse_returns,
            ) as mock_parse,
            patch(
                "restaurants.services.menu_upload_service.MenuMergeAgent.run",
                return_value=merged,
            ) as mock_merge,
        ):
            result = MenuUploadService.parse_images([b"img1", b"img2"])

        assert mock_parse.call_count == 2
        mock_merge.assert_called_once()
        assert result is merged

    def test_parse_handles_individual_image_failure(self):
        """If one image fails, the others are still parsed and merged."""
        good_page = _make_parsed_page("Mains")
        merged = ParsedMenu(categories=good_page.categories)

        call_count = {"n": 0}

        def _parse_side_effect(image_data):
            call_count["n"] += 1
            if image_data == b"bad":
                raise RuntimeError("Vision API error")
            return good_page

        with (
            patch(
                "restaurants.services.menu_upload_service.MenuParsingAgent.run",
                side_effect=_parse_side_effect,
            ),
            patch(
                "restaurants.services.menu_upload_service.MenuMergeAgent.run",
                return_value=merged,
            ) as mock_merge,
        ):
            result = MenuUploadService.parse_images([b"good", b"bad"])

        # merge called with only the good page
        called_pages = mock_merge.call_args[1]["pages"]
        assert len(called_pages) == 1
        assert called_pages[0] is good_page
        assert result is merged

    def test_all_images_fail_returns_empty_menu(self):
        """If every image fails, merge is called with empty list -> empty menu."""
        with (
            patch(
                "restaurants.services.menu_upload_service.MenuParsingAgent.run",
                side_effect=RuntimeError("fail"),
            ),
            patch(
                "restaurants.services.menu_upload_service.MenuMergeAgent.run",
                return_value=ParsedMenu(categories=[]),
            ) as mock_merge,
        ):
            result = MenuUploadService.parse_images([b"bad"])

        mock_merge.assert_called_once_with(pages=[])
        assert result.categories == []


# ── save_menu ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSaveMenu:
    def test_overwrite_creates_new_version(self, restaurant):
        parsed = _make_parsed_menu()
        version = MenuUploadService.save_menu(
            restaurant, parsed, mode="overwrite", version_name="AI Upload"
        )

        assert version.name == "AI Upload"
        assert version.source == MenuVersion.Source.AI_UPLOAD
        assert version.is_active is False
        assert MenuVersion.objects.filter(restaurant=restaurant).count() == 1

    def test_overwrite_saves_categories_and_items(self, restaurant):
        parsed = _make_parsed_menu(category_name="Burgers", item_name="Classic")
        version = MenuUploadService.save_menu(
            restaurant, parsed, mode="overwrite", version_name="Test"
        )

        categories = list(MenuCategory.objects.filter(version=version))
        assert len(categories) == 1
        assert categories[0].name == "Burgers"

        items = list(MenuItem.objects.filter(category__version=version))
        assert len(items) == 1
        assert items[0].name == "Classic"

    def test_overwrite_saves_variants(self, restaurant):
        parsed = _make_parsed_menu(price="12.50")
        version = MenuUploadService.save_menu(
            restaurant, parsed, mode="overwrite", version_name="Test"
        )

        variants = list(MenuItemVariant.objects.filter(menu_item__category__version=version))
        assert len(variants) == 1
        assert variants[0].price == Decimal("12.50")

    def test_append_copies_active_version_items_first(self, restaurant):
        # Set up an active version with an existing item
        active_v = MenuVersion.objects.create(
            restaurant=restaurant, name="Active", source="manual", is_active=True
        )
        existing_cat = MenuCategory.objects.create(version=active_v, name="Existing Cat", sort_order=0)
        MenuItem.objects.create(category=existing_cat, name="Existing Item", sort_order=0)

        parsed = _make_parsed_menu(category_name="New Cat", item_name="New Item")
        new_version = MenuUploadService.save_menu(
            restaurant, parsed, mode="append", version_name="Appended"
        )

        cat_names = set(MenuCategory.objects.filter(version=new_version).values_list("name", flat=True))
        assert "Existing Cat" in cat_names
        assert "New Cat" in cat_names

        item_names = set(MenuItem.objects.filter(category__version=new_version).values_list("name", flat=True))
        assert "Existing Item" in item_names
        assert "New Item" in item_names

    def test_append_with_no_active_version_still_works(self, restaurant):
        """If there's no active version, append behaves like overwrite."""
        parsed = _make_parsed_menu()
        version = MenuUploadService.save_menu(
            restaurant, parsed, mode="append", version_name="Appended"
        )

        assert version is not None
        items = MenuItem.objects.filter(category__version=version)
        assert items.count() == 1

    def test_default_name_used_when_version_name_is_none(self, restaurant):
        from datetime import date

        parsed = _make_parsed_menu()
        version = MenuUploadService.save_menu(restaurant, parsed)

        today = date.today()
        expected_base = f"Menu - {today.strftime('%b %-d, %Y')}"
        assert version.name == expected_base
