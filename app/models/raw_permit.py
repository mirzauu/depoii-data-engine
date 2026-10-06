from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Integer, String, Text, JSON, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class RawPermit(Base, TimestampMixin):
    """
    Immutable raw staging table for ingested municipal permits.
    Preserves raw JSON payload for auditability and replayable re-normalization.
    """
    __tablename__ = "raw_permits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_permit_number: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)  # "socrata" | "accela" | "energov"
    source_priority: Mapped[int] = mapped_column(Integer, default=3)        # 1=accela, 2=energov, 3=socrata
    issue_date: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("idx_raw_permit_dedup", "raw_permit_number", "jurisdiction", "issue_date"),
    )
