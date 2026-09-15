from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Order, OrderStatus


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
