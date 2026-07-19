from datetime import datetime, timezone
from pydantic import BaseModel, field_validator


class OrderCreate(BaseModel):
    type: str  # "passenger" | "freight"
    from_text: str
    to_text: str
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    date_time: datetime
    price: int
    description: str | None = None

    @field_validator("date_time", mode="before")
    @classmethod
    def strip_tz(cls, v):
        if isinstance(v, datetime):
            return v.replace(tzinfo=None)
        if isinstance(v, str):
            dt = datetime.fromisoformat(v)
            return dt.replace(tzinfo=None)
        return v


class BidCreate(BaseModel):
    order_id: int
    proposed_price: int


class BidResponse(BaseModel):
    bid_id: int
    action: str  # "accept" | "reject"


class RatingSubmit(BaseModel):
    order_id: int
    rating: int  # 1-5
    review: str | None = None


class VehicleCreate(BaseModel):
    type: str
    make_model: str
    license_plate: str
    capacity_kg: int | None = None
    capacity_seats: int | None = None


class RoleUpdate(BaseModel):
    role: str  # "client" | "driver" | "both"
