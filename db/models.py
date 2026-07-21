from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.engine import Base


class UserRole(str, enum.Enum):
    client = "client"
    driver = "driver"
    both = "both"


class VehicleType(str, enum.Enum):
    car = "car"
    minivan = "minivan"
    truck_3_5t = "truck_3_5t"
    heavy_truck = "heavy_truck"


class OrderType(str, enum.Enum):
    passenger = "passenger"
    freight = "freight"


class OrderStatus(str, enum.Enum):
    new = "new"
    active = "active"
    in_transit = "in_transit"
    completed = "completed"
    cancelled = "cancelled"


class BidStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.client)
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    deals_completed: Mapped[int] = mapped_column(Integer, default=0)
    promo_deals_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    orders: Mapped[list["Order"]] = relationship(
        back_populates="customer", foreign_keys="Order.customer_id", cascade="all, delete-orphan"
    )
    driver_orders: Mapped[list["Order"]] = relationship(
        back_populates="driver", foreign_keys="Order.driver_id"
    )
    bids: Mapped[list["Bid"]] = relationship(back_populates="driver", cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    type: Mapped[VehicleType] = mapped_column(String(20), nullable=False)
    make_model: Mapped[str] = mapped_column(String(128), nullable=False)
    license_plate: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="vehicles")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    driver_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    type: Mapped[OrderType] = mapped_column(String(20), nullable=False)
    from_text: Mapped[str] = mapped_column(String(256), nullable=False)
    to_text: Mapped[str] = mapped_column(String(256), nullable=False)
    from_lat: Mapped[float] = mapped_column(Float, nullable=False)
    from_lng: Mapped[float] = mapped_column(Float, nullable=False)
    to_lat: Mapped[float] = mapped_column(Float, nullable=False)
    to_lng: Mapped[float] = mapped_column(Float, nullable=False)
    date_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    road_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_geometry: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(String(20), default=OrderStatus.new)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    customer: Mapped["User"] = relationship(foreign_keys=[customer_id], back_populates="orders")
    driver: Mapped["User | None"] = relationship(foreign_keys=[driver_id], back_populates="driver_orders")
    bids: Mapped[list["Bid"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    driver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    proposed_price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BidStatus] = mapped_column(String(20), default=BidStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="bids")
    driver: Mapped["User"] = relationship(back_populates="bids")
