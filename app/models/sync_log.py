from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class SyncLog(Base, TimestampMixin):
    """
    Tracks sync metadata per municipal feed:
    - ETags for Socrata 304 Not Modified conditional requests
    - Row count drift detection
    - Execution duration and status
    """
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jurisdiction: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)  # "socrata" | "accela"
    dataset_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS")  # "SUCCESS" | "UNCHANGED" | "FAILED" | "DRIFT_WARNING"
    etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    previous_row_count: Mapped[int] = mapped_column(Integer, default=0)
    drift_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
