"""
Menu parsing agent using GPT-4o vision.

Accepts raw image bytes and returns a structured ParsedMenuPage describing
the categories and items visible in the image.
"""

from typing import Any

from agno.media import Image
from pydantic import BaseModel

from ai.base_agent import BaseAgent
from ai.models import resolve_model
from restaurants.llm.schemas import ParsedMenuPage

INSTRUCTIONS = """\
You are a menu digitisation assistant. Given an image of a restaurant menu page, \
extract every visible category, item, and price variant into structured JSON.

Rules:
- Preserve the category names exactly as they appear on the menu.
- For each item, include the name, an optional description if present, \
and at least one variant with a label (e.g. "Regular", "Large", or the \
size/option name shown) and a price.
- If only one price is shown for an item, create a single variant with \
label "Standard" and that price.
- Prices must be numeric decimals (e.g. 9.50). Do not include currency symbols.
- If a category has no visible items, omit it.
- Do not invent items or prices that are not clearly visible.
"""


class MenuParsingAgent(BaseAgent):
    default_model = "gpt-4o"

    def get_name(self) -> str:
        return "MenuParsingAgent"

    def get_instructions(self) -> str:
        return INSTRUCTIONS

    def get_output_schema(self) -> type[BaseModel] | None:
        return ParsedMenuPage

    def _resolve_model(self):
        """Always use gpt-4o regardless of the global LLM_MODEL setting."""
        return resolve_model(self.default_model)

    @classmethod
    def run(cls, image_data: bytes, **kwargs: Any) -> ParsedMenuPage:  # type: ignore[override]
        """
        Parse a single menu page image.

        Args:
            image_data: Raw bytes of the image (JPEG, PNG, WEBP, etc.).

        Returns:
            A ParsedMenuPage with all extracted categories and items.
        """
        instance = cls()
        agent = instance._build_agent()

        image = Image(content=image_data)
        result = agent.run(
            "Extract all menu categories, items, and prices from this image.",
            images=[image],
        )
        if not isinstance(result.content, ParsedMenuPage):
            raise ValueError(
                f"MenuParsingAgent expected ParsedMenuPage but got {type(result.content).__name__}: "
                f"{str(result.content)[:200]}"
            )
        return result.content
