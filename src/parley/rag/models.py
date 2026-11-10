from datetime import date

from pydantic import BaseModel

from parley.policies.models import PolicyCategory, Region


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    version: int
    title: str
    category: PolicyCategory
    regions: list[Region]
    effective_date: date
    expires_date: date | None
    section: str | None
    text: str

    @property
    def doc_key(self) -> str:
        return f"{self.doc_id}@v{self.version}"

    @property
    def citation(self) -> str:
        return f"{self.doc_key} / {self.section}" if self.section else self.doc_key

    def is_in_force(self, as_of: date) -> bool:
        expired = self.expires_date is not None and self.expires_date < as_of
        return self.effective_date <= as_of and not expired

    def applies_to(self, region: Region) -> bool:
        return Region.GLOBAL in self.regions or region in self.regions
