from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Column
from sqlmodel import Relationship, SQLModel, Field


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: int = Field(default=None, primary_key=True)
    note: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RealEstate(SQLModel, table=True):
    __tablename__ = "real_estates"

    id: int = Field(default=None, primary_key=True)
    external_id: str
    cluster_id: str
    address: str
    size_m2: float = Field(ge=0)
    rooms: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    prices: List["RealEstatePrice"] = Relationship(back_populates="listing")


class RealEstatePrice(SQLModel, table=True):
    __tablename__ = "real_estate_prices"

    id: int = Field(default=None, primary_key=True)
    listing_id: Optional[int] = Field(
        default=None, foreign_key="real_estates.id", index=True
    )
    price: float = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    listing: RealEstate = Relationship(back_populates="prices")
