from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class ClassificationOutput(BaseModel):
    is_children_activity: bool = Field(description="True if event is designed for or suitable for children")
    is_toddler_friendly: bool = Field(description="True if event is suitable for toddlers (ages 0-3)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the classification, 0.0 to 1.0")


class LocationEnrichmentOutput(BaseModel):
    normalized_address: str = Field(description="Clean address without prefixes like 'de ', 'calle ', 'avenida '")
    neighborhood: str = Field(default="", description="Madrid neighborhood or district name")
    metro: str = Field(default="", description="Nearest Madrid metro station name")


@dataclass
class ClassificationResult:
    is_children_activity: bool
    is_toddler_friendly: bool
    confidence: float
    raw_response: str
