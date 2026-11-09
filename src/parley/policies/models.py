from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class PolicyCategory(StrEnum):
    REFUNDS = "refunds"
    SHIPPING = "shipping"
    SUBSCRIPTIONS = "subscriptions"
    BILLING = "billing"
    ESCALATION = "escalation"
    GENERAL = "general"


class Region(StrEnum):
    GLOBAL = "global"
    US = "US"
    CA = "CA"
    UK = "UK"
    EU = "EU"
    TR = "TR"


class PolicyDoc(BaseModel):
    doc_id: str = Field(pattern=r"^POL-[A-Z]{3,4}-\d{3}$")
    title: str = Field(min_length=3)
    version: int = Field(ge=1)
    effective_date: date
    category: PolicyCategory
    regions: list[Region] = Field(default_factory=lambda: [Region.GLOBAL], min_length=1)
    overrides: list[str] = Field(default_factory=list)
    body: str = Field(min_length=1)

    @property
    def key(self) -> str:
        return f"{self.doc_id}@v{self.version}"

    @property
    def filename(self) -> str:
        return f"{self.doc_id}_v{self.version}.md"

    def applies_to(self, region: Region) -> bool:
        return Region.GLOBAL in self.regions or region in self.regions
