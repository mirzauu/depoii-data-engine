from typing import Optional
from sqlalchemy import Integer, String, Float, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class Parcel(Base, TimestampMixin):
    """
    Commercial real estate parcel footprint from County Appraisal District (CAD).
    """
    __tablename__ = "parcels"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Parcel / Account ID
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    county: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(10), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    building_sqft: Mapped[int] = mapped_column(Integer, index=True, default=0)
    land_sqft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_built: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    property_type: Mapped[str] = mapped_column(String(100), default="Commercial Warehouse")
    owner_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    data_source: Mapped[str] = mapped_column(String(100), default="TAD")
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_valuation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geometry_geojson: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("idx_parcel_location", "city", "county", "building_sqft"),
    )
