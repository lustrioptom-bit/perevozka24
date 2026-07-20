from fastapi import APIRouter, Request, Depends
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import get_session
from db.models import User, Order, Bid, Vehicle, OrderStatus, OrderType, BidStatus, UserRole
from webapp.routers.schemas import (
    OrderCreate, BidCreate, BidResponse, RatingSubmit, VehicleCreate, RoleUpdate, PhoneUpdate,
)
from bot.utils.geo import haversine, geocode_address, get_road_route
from bot.utils.helpers import COMPLETED_DEALS_PROMO_LIMIT

router = APIRouter(prefix="/api", tags=["api"])


def _get_user_id(request: Request) -> int:
    return int(request.query_params.get("user_id", 0))


# ─── User endpoints ───

@router.get("/user/{user_id}")
async def get_user(user_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        await _ensure_user(session, user_id)
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    if not user:
        return {"error": "not_found"}
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role.value,
        "rating": user.rating,
        "deals_completed": user.deals_completed,
        "promo_deals_used": user.promo_deals_used,
    }


@router.post("/user/role")
async def update_role(body: RoleUpdate, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"error": "not_found"}
    user.role = UserRole(body.role)
    await session.commit()
    return {"ok": True}


@router.post("/user/phone")
async def update_phone(body: PhoneUpdate, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"error": "not_found"}
    user.phone = body.phone
    await session.commit()
    return {"ok": True}


# ─── Vehicle endpoints ───

@router.get("/vehicles")
async def list_vehicles(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Vehicle).where(Vehicle.user_id == user_id))
    vehicles = result.scalars().all()
    return [
        {"id": v.id, "type": v.type.value, "make_model": v.make_model,
         "license_plate": v.license_plate, "capacity_kg": v.capacity_kg,
         "capacity_seats": v.capacity_seats}
        for v in vehicles
    ]


@router.post("/vehicles")
async def create_vehicle(body: VehicleCreate, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    vehicle = Vehicle(
        user_id=user_id,
        type=body.type,
        make_model=body.make_model,
        license_plate=body.license_plate,
        capacity_kg=body.capacity_kg,
        capacity_seats=body.capacity_seats,
    )
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return {"id": vehicle.id, "ok": True}


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(
        select(Vehicle).where(and_(Vehicle.id == vehicle_id, Vehicle.user_id == user_id))
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        return {"error": "not_found"}
    await session.delete(vehicle)
    await session.commit()
    return {"ok": True}


# ─── Order endpoints ───

@router.post("/orders")
async def create_order(body: OrderCreate, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    if not user_id:
        return {"error": "missing_user_id"}

    await _ensure_user(session, user_id)

    order = Order(
        customer_id=user_id,
        type=OrderType(body.type),
        from_text=body.from_text,
        to_text=body.to_text,
        from_lat=body.from_lat,
        from_lng=body.from_lng,
        to_lat=body.to_lat,
        to_lng=body.to_lng,
        date_time=body.date_time,
        price=body.price,
        description=body.description,
    )

    route = await get_road_route(body.from_lat, body.from_lng, body.to_lat, body.to_lng)
    if route:
        order.road_distance_km = route["distance_km"]
        order.route_geometry = route["geometry"]

    session.add(order)
    await session.commit()
    await session.refresh(order)

    try:
        from aiogram import Bot
        from config import settings
        bot = Bot(token=settings.BOT_TOKEN)
        from bot.utils.channel import post_order_to_channel
        await post_order_to_channel(bot, order)
        await bot.session.close()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Channel post failed: %s", e, exc_info=True)

    try:
        from bot.utils.helpers import notify_drivers_new_order
        from aiogram import Bot
        from config import settings
        bot = Bot(token=settings.BOT_TOKEN)
        await notify_drivers_new_order(session, order, bot, _get_webapp_url())
        await bot.session.close()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Driver notify failed: %s", e, exc_info=True)

    return {"id": order.id, "ok": True}


@router.get("/orders/feed")
async def orders_feed(
    type_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Order).where(Order.status == OrderStatus.new)
    if type_filter in ("passenger", "freight"):
        query = query.where(Order.type == OrderType(type_filter))
    query = query.order_by(Order.created_at.desc()).limit(50)
    result = await session.execute(query)
    orders = result.scalars().all()
    return [_order_to_dict(o) for o in orders]


@router.get("/orders/my")
async def my_orders(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    query = select(Order).where(
        or_(Order.customer_id == user_id, Order.driver_id == user_id),
    ).order_by(Order.created_at.desc())
    result = await session.execute(query)
    orders = result.scalars().all()
    out = []
    for o in orders:
        d = _order_to_dict(o)
        if o.driver_id and o.driver_id != user_id:
            driver = (await session.execute(select(User).where(User.id == o.driver_id))).scalar_one_or_none()
            if driver:
                d["driver_name"] = driver.full_name or driver.username or str(driver.id)
                d["driver_phone"] = driver.phone
                d["driver_rating"] = driver.rating
        if o.customer_id and o.customer_id != user_id:
            customer = (await session.execute(select(User).where(User.id == o.customer_id))).scalar_one_or_none()
            if customer:
                d["customer_name"] = customer.full_name or customer.username or str(customer.id)
                d["customer_phone"] = customer.phone
        out.append(d)
    return out


@router.get("/orders/history")
async def order_history(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    query = select(Order).where(
        or_(Order.customer_id == user_id, Order.driver_id == user_id),
        Order.status.in_([OrderStatus.completed, OrderStatus.cancelled]),
    ).order_by(Order.created_at.desc()).limit(30)
    result = await session.execute(query)
    orders = result.scalars().all()
    return [_order_to_dict(o) for o in orders]


@router.get("/orders/map")
async def orders_map(
    lat: float,
    lng: float,
    radius: float = 150.0,
    type_filter: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Order).where(Order.status == OrderStatus.new)
    result = await session.execute(query)
    orders = result.scalars().all()

    nearby = []
    for o in orders:
        dist = haversine(lat, lng, o.from_lat, o.from_lng)
        if dist <= radius:
            if type_filter in ("passenger", "freight") and o.type.value != type_filter:
                continue
            d = _order_to_dict(o)
            d["distance_km"] = round(dist, 1)
            nearby.append(d)
    nearby.sort(key=lambda x: x["distance_km"])
    return nearby


@router.get("/orders/{order_id}")
async def get_order(order_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return {"error": "not_found"}
    d = _order_to_dict(order)
    if order.driver_id:
        driver = (await session.execute(select(User).where(User.id == order.driver_id))).scalar_one_or_none()
        if driver:
            d["driver_name"] = driver.full_name or driver.username or str(driver.id)
            d["driver_phone"] = driver.phone
            d["driver_rating"] = driver.rating
    if order.customer_id:
        customer = (await session.execute(select(User).where(User.id == order.customer_id))).scalar_one_or_none()
        if customer:
            d["customer_name"] = customer.full_name or customer.username or str(customer.id)
            d["customer_phone"] = customer.phone
    return d


@router.get("/orders/{order_id}/bids")
async def get_order_bids(order_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Bid, User).join(User, Bid.driver_id == User.id).where(Bid.order_id == order_id)
    )
    rows = result.all()
    return [
        {
            "bid_id": bid.id,
            "driver_id": bid.driver_id,
            "driver_name": user.full_name or user.username or str(user.id),
            "driver_rating": user.rating,
            "proposed_price": bid.proposed_price,
            "status": bid.status.value,
        }
        for bid, user in rows
    ]


@router.post("/bids")
async def create_bid(body: BidCreate, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    order_result = await session.execute(select(Order).where(Order.id == body.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        return {"error": "order_not_found"}
    if order.customer_id == user_id:
        return {"error": "cannot_bid_own_order"}

    existing = await session.execute(
        select(Bid).where(and_(Bid.order_id == body.order_id, Bid.driver_id == user_id))
    )
    if existing.scalar_one_or_none():
        return {"error": "already_bid"}

    bid = Bid(order_id=body.order_id, driver_id=user_id, proposed_price=body.proposed_price)
    session.add(bid)
    await session.commit()
    await session.refresh(bid)

    try:
        from aiogram import Bot
        from config import settings
        from bot.keyboards.inline import get_bid_notification_keyboard
        from bot.utils.helpers import get_or_create_user

        bot = Bot(token=settings.BOT_TOKEN)
        driver_user = await get_or_create_user(session, user_id)
        webapp_url = _get_webapp_url()
        await bot.send_message(
            order.customer_id,
            f"Водитель {driver_user.full_name or driver_user.username} "
            f"(рейтинг: {driver_user.rating:.1f}) предложил {bid.proposed_price} \u20b4.",
            reply_markup=get_bid_notification_keyboard(webapp_url, order.id),
        )
        await bot.session.close()
    except Exception:
        pass

    return {"id": bid.id, "ok": True}


@router.post("/bids/respond")
async def respond_to_bid(body: BidResponse, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Bid).where(Bid.id == body.bid_id))
    bid = result.scalar_one_or_none()
    if not bid:
        return {"error": "not_found"}

    order_result = await session.execute(select(Order).where(Order.id == bid.order_id))
    order = order_result.scalar_one_or_none()
    if not order or order.customer_id != user_id:
        return {"error": "forbidden"}

    if body.action == "accept":
        bid.status = BidStatus.accepted
        order.driver_id = bid.driver_id
        order.price = bid.proposed_price
        order.status = OrderStatus.active

        other_bids = await session.execute(
            select(Bid).where(and_(Bid.order_id == order.id, Bid.id != bid.id, Bid.status == BidStatus.pending))
        )
        for ob in other_bids.scalars().all():
            ob.status = BidStatus.rejected

        try:
            from aiogram import Bot
            from config import settings
            bot = Bot(token=settings.BOT_TOKEN)
            driver = (await session.execute(select(User).where(User.id == bid.driver_id))).scalar_one_or_none()
            if driver:
                customer = (await session.execute(select(User).where(User.id == order.customer_id))).scalar_one_or_none()
                phone_text = f"\nТелефон: {customer.phone}" if customer and customer.phone else ""
                await bot.send_message(
                    bid.driver_id,
                    f"Вашу ставку на заказ #{order.id} приняли!\n"
                    f"Маршрут: {order.from_text} -> {order.to_text}\n"
                    f"Цена: {order.price} \u20b4{phone_text}\n\n"
                    f"Свяжитесь с клиентом для деталей.",
                )
            await bot.session.close()
        except Exception:
            pass
    else:
        bid.status = BidStatus.rejected

    await session.commit()
    return {"ok": True}


@router.post("/orders/{order_id}/in_transit")
async def order_in_transit(order_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return {"error": "not_found"}
    if order.driver_id != user_id:
        return {"error": "forbidden"}
    if order.status != OrderStatus.active:
        return {"error": "wrong_status"}
    order.status = OrderStatus.in_transit
    await session.commit()

    try:
        from aiogram import Bot
        from config import settings
        bot = Bot(token=settings.BOT_TOKEN)
        await bot.send_message(order.customer_id, f"Водитель выехал по заказу #{order.id}!")
        await bot.session.close()
    except Exception:
        pass

    return {"ok": True}


@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return {"error": "not_found"}
    if order.driver_id != user_id:
        return {"error": "forbidden"}
    if order.status not in (OrderStatus.active, OrderStatus.in_transit):
        return {"error": "wrong_status"}

    order.status = OrderStatus.completed

    if order.driver_id:
        driver_result = await session.execute(select(User).where(User.id == order.driver_id))
        driver = driver_result.scalar_one_or_none()
        if driver:
            driver.deals_completed += 1
            driver.promo_deals_used += 1

    customer_result = await session.execute(select(User).where(User.id == order.customer_id))
    customer = customer_result.scalar_one_or_none()
    if customer:
        customer.promo_deals_used += 1

    await session.commit()

    try:
        from aiogram import Bot
        from config import settings
        bot = Bot(token=settings.BOT_TOKEN)
        await bot.send_message(order.customer_id, f"Заказ #{order.id} выполнен! Оцените водителя в приложении.")
        await bot.session.close()
    except Exception:
        pass

    return {"ok": True}


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return {"error": "not_found"}
    if order.customer_id != user_id:
        return {"error": "forbidden"}
    if order.status not in (OrderStatus.new, OrderStatus.active):
        return {"error": "wrong_status"}
    order.status = OrderStatus.cancelled
    await session.commit()
    return {"ok": True}


@router.post("/orders/{order_id}/rate")
async def rate_order(order_id: int, body: RatingSubmit, request: Request, session: AsyncSession = Depends(get_session)):
    user_id = _get_user_id(request)
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return {"error": "not_found"}
    if order.customer_id != user_id:
        return {"error": "forbidden"}
    if not order.driver_id:
        return {"error": "no_driver"}
    if order.status != OrderStatus.completed:
        return {"error": "not_completed"}

    driver_result = await session.execute(select(User).where(User.id == order.driver_id))
    driver = driver_result.scalar_one_or_none()
    if driver:
        total = driver.rating * driver.deals_completed
        driver.rating = round((total + body.rating) / (driver.deals_completed + 1), 1)

    await session.commit()

    try:
        from aiogram import Bot
        from config import settings
        from bot.utils.channel import post_review_to_channel
        bot = Bot(token=settings.BOT_TOKEN)
        await post_review_to_channel(bot, order, driver.full_name or driver.username, driver.rating, body.review or "")
        await bot.session.close()
    except Exception:
        pass

    return {"ok": True}


@router.get("/stats/promo")
async def promo_stats(session: AsyncSession = Depends(get_session)):
    completed = (
        await session.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.completed))
    ).scalar() or 0
    return {"completed": completed, "limit": COMPLETED_DEALS_PROMO_LIMIT, "is_promo_active": completed < COMPLETED_DEALS_PROMO_LIMIT}


@router.get("/geocode")
async def api_geocode(address: str):
    result = await geocode_address(address)
    if result:
        return {"lat": result[0], "lng": result[1]}
    return {"error": "not_found"}


# ─── Helpers ───

def _order_to_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "customer_id": o.customer_id,
        "driver_id": o.driver_id,
        "type": o.type.value,
        "from_text": o.from_text,
        "to_text": o.to_text,
        "from_lat": o.from_lat,
        "from_lng": o.from_lng,
        "to_lat": o.to_lat,
        "to_lng": o.to_lng,
        "date_time": o.date_time.isoformat(),
        "price": o.price,
        "description": o.description,
        "road_distance_km": o.road_distance_km,
        "route_geometry": o.route_geometry,
        "status": o.status.value,
        "created_at": o.created_at.isoformat(),
    }


def _get_webapp_url() -> str:
    from config import settings
    return settings.WEBAPP_BASE_URL


async def _ensure_user(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        user = User(id=user_id)
        session.add(user)
        await session.commit()
