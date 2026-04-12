"""
MenuUploadService — orchestrates menu image parsing and persistence.

parse_images() fans out to MenuParsingAgent in parallel then merges results
via MenuMergeAgent. save_menu() writes the parsed structure to the database,
either as a fresh version (overwrite) or appended to an existing one (append).
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import transaction

from restaurants.llm.merge_agent import MenuMergeAgent
from restaurants.llm.parse_agent import MenuParsingAgent
from restaurants.llm.schemas import ParsedMenu, ParsedMenuPage
from restaurants.models import (
    MenuCategory,
    MenuItem,
    MenuItemVariant,
    MenuVersion,
    Restaurant,
)
from restaurants.services.menu_version_service import MenuVersionService

logger = logging.getLogger(__name__)


class MenuUploadService:
    # ── Parsing ────────────────────────────────────────────────────────────────

    @staticmethod
    def parse_images(image_data_list: list[bytes]) -> ParsedMenu:
        """
        Parse a list of raw image bytes into a single merged ParsedMenu.

        Each image is parsed in parallel using MenuParsingAgent. If an
        individual image fails, it is skipped with a warning. The successful
        ParsedMenuPage results are then merged via MenuMergeAgent.

        Returns an empty ParsedMenu if all images fail.
        """
        pages: list[ParsedMenuPage] = []

        def _parse_one(image_data: bytes) -> ParsedMenuPage:
            return MenuParsingAgent.run(image_data=image_data)

        with ThreadPoolExecutor() as executor:
            future_to_index = {
                executor.submit(_parse_one, data): i
                for i, data in enumerate(image_data_list)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    page = future.result()
                    pages.append(page)
                except Exception as exc:
                    logger.warning(
                        "MenuParsingAgent failed for image %d: %s", index, exc
                    )

        return MenuMergeAgent.run(pages=pages)

    # ── Saving ─────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def save_menu(
        restaurant: Restaurant,
        parsed_menu: ParsedMenu,
        mode: str = "overwrite",
        version_name: str | None = None,
    ) -> MenuVersion:
        """
        Persist a ParsedMenu to the database.

        Args:
            restaurant: The restaurant this menu belongs to.
            parsed_menu: The merged ParsedMenu to persist.
            mode: "overwrite" creates a fresh new version; "append" copies
                  categories/items from the currently active version first, then
                  adds the parsed data on top.
            version_name: Optional custom name for the new version. Defaults to
                          the result of MenuVersionService.generate_default_name.

        Returns:
            The newly created MenuVersion.
        """
        if version_name is None:
            version_name = MenuVersionService.generate_default_name(restaurant)

        new_version = MenuVersion.objects.create(
            restaurant=restaurant,
            name=version_name,
            source=MenuVersion.Source.AI_UPLOAD,
            is_active=False,
        )

        if mode == "append":
            active_version = restaurant.menu_versions.filter(is_active=True).first()
            if active_version:
                MenuVersionService.duplicate_version_into(active_version, new_version)

        for parsed_category in parsed_menu.categories:
            category = MenuCategory.objects.create(
                version=new_version,
                name=parsed_category.name,
                sort_order=0,
            )
            for sort_idx, parsed_item in enumerate(parsed_category.items):
                item = MenuItem.objects.create(
                    category=category,
                    name=parsed_item.name,
                    description=parsed_item.description or "",
                    image_url=parsed_item.image_url or "",
                    sort_order=sort_idx,
                )
                for variant in parsed_item.variants:
                    MenuItemVariant.objects.create(
                        menu_item=item,
                        label=variant.label,
                        price=variant.price,
                        is_default=False,
                    )

        # Auto-activate if no active version exists (e.g. first upload during onboarding)
        if not restaurant.menu_versions.filter(is_active=True).exists():
            new_version.is_active = True
            new_version.save(update_fields=["is_active", "updated_at"])

        return new_version
