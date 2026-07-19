from __future__ import annotations

from aiogram import Bot
from sqlalchemy import select

from config import settings
from db.engine import async_session
from db.models import Order, OrderType, User, BidStatus
from bot.keyboards.inline import get_channel_keyboard


async def post_order_to_channel(bot: Bot, order: Order) -> None:
    if not settings.CHANNEL_ID:
        return

    type_label = "Грузоперевозка" if order.type == OrderType.freight else "Поездка (Пассажиры)"
    budget_text = f"{order.price} \u20b4"
    date_text = order.date_time.strftime("%d.%m.%Y в %H:%M")

    text = (
        f"<b>НОВЫЙ ЗАКАЗ #{order.id}</b>\n\n"
        f"{type_label}\n"
        f"Маршрут: {order.from_text} \u2192 {order.to_text}\n"
        f"Дата: {date_text}\n"
        f"Бюджет: {budget_text}\n"
    )
    if order.road_distance_km:
        text += f"Расстояние: {order.road_distance_km} км (по дороге)\n"
    text += (
        f"Детали: {order.description or 'Без описания'}\n\n"
        "Нажмите кнопку ниже, чтобы предложить свою цену:"
    )

    await bot.send_message(
        settings.CHANNEL_ID,
        text,
        reply_markup=get_channel_keyboard(order.id, _get_webapp_url()),
        parse_mode="HTML",
    )


async def post_review_to_channel(bot: Bot, order: Order, driver_name: str, driver_rating: float, review_text: str) -> None:
    if not settings.CHANNEL_ID:
        return

    completed_count = 0
    async with async_session() as session:
        from sqlalchemy import func
        result = await session.execute(select(func.count(Order.id)).where(Order.status == OrderStatus.completed))
        completed_count = result.scalar() or 0

    from db.models import OrderStatus
    text = (
        f"<b>УСПЕШНАЯ ПЕРЕВОЗКА #{order.id}</b>\n\n"
        f"Водитель: {driver_name} (Рейтинг: {driver_rating:.1f})\n"
        f"Маршрут: {order.from_text} \u2192 {order.to_text}\n"
        f"Отзыв: \"{review_text}\"\n\n"
        f"Успешных сделок в сервисе: {completed_count} / {150}"
    )
    await bot.send_message(settings.CHANNEL_ID, text, parse_mode="HTML")


def _get_webapp_url() -> str:
    return settings.WEBAPP_BASE_URL


from db.models import OrderStatus  # noqa: E402 (avoid circular at top)
