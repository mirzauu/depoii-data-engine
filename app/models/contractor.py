from typing import Optional, List
from sqlalchemy import Integer, String, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class CanonicalContractor(Base, TimestampMixin):
    """
    Deduplicated legal contractor entity.
    Aggregates market share across noisy municipal permit filings.
    """
    __tablename__ = "canonical_contractors"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g. "CTR-KPOST-ROOFING"
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    primary_license: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    headquarters_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    headquarters_state: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    total_permits: Mapped[int] = mapped_column(Integer, default=0)
    total_valuation: Mapped[float] = mapped_column(Float, default=0.0)
    primary_roof_system: Mapped[str] = mapped_column(String(100), default="TPO Single-Ply")

    aliases: Mapped[List["ContractorAlias"]] = relationship("ContractorAlias", back_populates="contractor", cascade="all, delete-orphan")


class ContractorAlias(Base, TimestampMixin):
    """
    Mapping table linking raw municipal variations and spellings to a canonical contractor.
    """
    __tablename__ = "contractor_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[str] = mapped_column(String(100), ForeignKey("canonical_contractors.id"), nullable=False)
    raw_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    raw_license: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)

    contractor: Mapped["CanonicalContractor"] = relationship("CanonicalContractor", back_populates="aliases")

    __table_args__ = (
        Index("idx_alias_raw_name_lic", "raw_name", "raw_license"),
    )
