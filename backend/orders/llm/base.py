from typing import Literal

from pydantic import BaseModel, Field


class ParsedOrderItem(BaseModel):
    menu_item_id: int
    variant_id: int
    quantity: int = 1
    modifier_ids: list[int] = Field(default_factory=list)
    special_requests: str = ""


class ParsedOrder(BaseModel):
    items: list[ParsedOrderItem]
    allergies: list[str] = Field(default_factory=list)
    language: str = "en"


class AgentResponse(BaseModel):
    """Union response from the OrderAgent — either an order or a recommendation intent."""
    intent: Literal["order", "recommendation"]
    order: ParsedOrder | None = None
    recommendation_context: str | None = None
