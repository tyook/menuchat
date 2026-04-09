from pydantic import BaseModel, Field


class RecommendedItem(BaseModel):
    menu_item_id: int
    variant_id: int
    reason: str = Field(description="Brief explanation of why this item is recommended")


class Recommendation(BaseModel):
    items: list[RecommendedItem] = Field(
        description="Recommended menu items, ordered by relevance"
    )
    greeting: str = Field(
        description="A short, friendly message to the customer about these recommendations"
    )
