from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Order, OrderStatus, OrderType, UserRole


COMPLETED_DEALS_PROMO_LIMIT = 150


async def get_or_create_user(
    session: AsyncSession, user_id: int, username: str | None = None, full_name: str | None = None
) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(id=user_id, username=username, full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        if username and user.username != username:
            user.username = username
        if full_name and user.full_name != full_name:
            user.full_name = full_name
        await session.commit()
    return user


async def get_admin_stats(session: AsyncSession) -> dict:
    total_users = (await session.execute(select(func.count(User.id)))).scalar() or 0
    active_orders = (
        await session.execute(
            select(func.count(Order.id)).where(Order.status.in_([OrderStatus.new, OrderStatus.active]))
        )
    ).scalar() or 0
    completed_deals = (await session.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.completed))).scalar() or 0
    return {"total_users": total_users, "active_orders": active_orders, "completed_deals": completed_deals}


async def notify_drivers_new_order(session: AsyncSession, order: Order, bot, webapp_url: str) -> None:
    from bot.keyboards.inline import get_order_notification_keyboard

    type_label = "Груз" if order.type == OrderType.freight else "Пассажиры"
    result = await session.execute(select(User).where(User.role.in_([UserRole.driver, UserRole.both])))
    drivers = result.scalars().all()
    for driver in drivers:
        if driver.id == order.customer_id:
            continue
        try:
            await bot.send_message(
                driver.id,
                f"Новый заказ #{order.id}\n"
                f"{type_label}\n"
                f"{order.from_text} \u2192 {order.to_text}\n"
                f"{order.date_time.strftime('%d.%m.%Y %H:%M')}\n"
                f"{order.price} \u20b4\n"
                f"{order.description or 'Без описания'}",
                reply_markup=get_order_notification_keyboard(webapp_url, order.id),
            )
        except Exception:
            pass
