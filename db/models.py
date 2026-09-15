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
    Boolean,
    Enum as SAEnum,
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


class DriverLevel(str, enum.Enum):
    novice = "novice"
    verified = "verified"
    pro = "pro"
    expert = "expert"


class NotifFrequency(str, enum.Enum):
    instant = "instant"
    hourly = "hourly"
    daily = "daily"


class NotificationType(str, enum.Enum):
    new_order = "new_order"
    selected = "selected"
    cancelled = "cancelled"
    completed = "completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, create_type=False), default=UserRole.client)
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    deals_completed: Mapped[int] = mapped_column(Integer, default=0)
    promo_deals_used: Mapped[int] = mapped_column(Integer, default=0)
    driver_level: Mapped[DriverLevel] = mapped_column(SAEnum(DriverLevel, create_type=False), default=DriverLevel.novice)
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
    type: Mapped[VehicleType] = mapped_column(SAEnum(VehicleType, create_type=False), nullable=False)
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
    type: Mapped[OrderType] = mapped_column(SAEnum(OrderType, create_type=False), nullable=False)
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
    driver_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    driver_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    driver_location_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, create_type=False), default=OrderStatus.new
    )
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
    status: Mapped[BidStatus] = mapped_column(
        SAEnum(BidStatus, create_type=False), default=BidStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="bids")
    driver: Mapped["User"] = relationship(back_populates="bids")


class DriverPreference(Base):
    __tablename__ = "driver_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    order_types: Mapped[str] = mapped_column(String(20), default="both")
    cities: Mapped[str] = mapped_column(Text, default="[]")
    radius_km: Mapped[int] = mapped_column(Integer, default=50)
    frequency: Mapped[NotifFrequency] = mapped_column(
        SAEnum(NotifFrequency, create_type=False), default=NotifFrequency.instant
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notif_count_this_hour: Mapped[int] = mapped_column(Integer, default=0)
    notif_hour_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    reviewer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    reviewee_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, create_type=False), default=NotificationType.new_order
    )
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RouteSubscription(Base):
    __tablename__ = "route_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
