from pydantic import BaseModel, Field


class ParsedMenuVariant(BaseModel):
    label: str
    price: float


class ParsedMenuItem(BaseModel):
    name: str
    description: str | None = None
    image_url: str | None = None
    variants: list[ParsedMenuVariant]


class ParsedMenuCategory(BaseModel):
    name: str
    items: list[ParsedMenuItem]


class ParsedMenuPage(BaseModel):
    categories: list[ParsedMenuCategory]


class ParsedMenu(BaseModel):
    categories: list[ParsedMenuCategory]
