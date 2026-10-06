from typing import Optional
from sqlalchemy import Integer, String, Float, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class NormalizedPermit(Base, TimestampMixin):
    """
    Production-grade canonical permit warehouse table.
    Upserted via the cross-source deduplication engine.
    """
    __tablename__ = "normalized_permits"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)  # Canonical ID: e.g. DEP-TX-DAL-COM-ROOF-26-000300
    raw_permit_number: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_priority: Mapped[int] = mapped_column(Integer, default=3)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    county: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Dates
    issue_date: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    applied_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    expiration_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Active")

    # Location
    normalized_address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    parcel_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    # Commercial Scope & Valuation
    valuation: Mapped[float] = mapped_column(Float, default=0.0)
    valuation_formatted: Mapped[str] = mapped_column(String(50), default="$0")
    category: Mapped[str] = mapped_column(String(100), index=True, default="Commercial Re-Roof")
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    square_footage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    probable_roof_system: Mapped[str] = mapped_column(String(100), index=True, default="Unspecified Commercial System")

    # Contractor
    contractor_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    contractor_license: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contractor_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Depoii Intelligence
    is_hail_storm_window: Mapped[bool] = mapped_column(Boolean, default=False)
    associated_storm_event: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_competitor_capture: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence_score: Mapped[int] = mapped_column(Integer, default=90)
    normalized_at: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        UniqueConstraint("raw_permit_number", "jurisdiction", "issue_date", name="uq_permit_jurisdiction_date"),
        Index("idx_permit_search", "jurisdiction", "issue_date", "valuation"),
    )
