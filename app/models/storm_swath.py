from typing import Optional
from sqlalchemy import Integer, String, Float, Text, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class StormSwath(Base, TimestampMixin):
    """
    NOAA NEXRAD Severe Convective Storm & Hail Swath footprint.
    Stores GeoJSON polygon geometry and meteorological parameters.
    """
    __tablename__ = "storm_swaths"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # e.g. "STORM-2024-05-28-DFW-HAIL"
    storm_name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_date: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # "2024-05-28"
    max_hail_inches: Mapped[float] = mapped_column(Float, default=2.0)
    max_gust_mph: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    affected_jurisdiction: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)

    # GeoJSON representation for portable geometry querying
    geometry_geojson: Mapped[dict] = mapped_column(JSON, nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
