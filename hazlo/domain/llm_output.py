from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


class ClassificationOutput(BaseModel):
    is_children_activity: bool = Field(description="True if event is designed for or suitable for children")
    is_toddler_friendly: bool = Field(description="True if event is suitable for toddlers (ages 0-3)")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the classification, 0.0 to 1.0")


class LocationEnrichmentOutput(BaseModel):
    normalized_address: str = Field(
        description=(
            "Full official Madrid street address with correct prefix "
            "(e.g., 'Paseo de Recoletos, 20'). "
            "Fix typos, incomplete names, or wrong formats."
        )
    )
    neighborhood: str = Field(
        default="",
        description=(
            "Official Madrid barrio name (e.g., 'Recoletos', 'Justicia', 'Malasaña'). Use barrio, not district."
        ),
    )
    metro: str = Field(default="", description="Nearest official Madrid metro station name by walking distance.")


class DateParsingOutput(BaseModel):
    start_at: str | None = Field(
        default=None,
        description="Event start datetime in ISO 8601 format. Use current year if year not specified.",
    )
    end_at: str | None = Field(
        default=None,
        description="Event end datetime in ISO 8601 format. None if single-day event.",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the date parsing, 0.0 to 1.0")


@dataclass
class ClassificationResult:
    is_children_activity: bool
    is_toddler_friendly: bool
    confidence: float
    raw_response: str


class ReparseEventOutput(BaseModel):
    title: str
    description: str | None = None
    address: str
    neighborhood: str
    metro: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    price_amount_cents: int | None = None
    is_free: bool
    price_notes: str | None = None
    ticket_url: str | None = None
    ticket_notes: str | None = None
    is_children_activity: bool
    is_toddler_friendly: bool
    confidence: float = Field(ge=0.0, le=1.0)
    field_confidence: dict[str, float] = Field(
        description="Confidence per field: title, description, location, dates, price, ticket, classification"
    )
    reasoning: str = Field(description="Brief explanation of what changed and why")
