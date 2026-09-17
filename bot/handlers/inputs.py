from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message

from sqlalchemy import select, and_

from db.models import Order, OrderStatus, Bid, DriverPreference
from bot.utils.chat_state import PREFS_ADDING_CITY, PREFS_STATE, PRICE_STATE, REVIEW_STATE
from bot.utils.reviews import apply_review
from bot.keyboards.inline import (
    PREF_CITY_LABELS,
    prefs_cities_keyboard,
    review_reason_keyboard,
    get_bid_notification_keyboard,
)
from config import settings
from bot.utils.helpers import get_or_create_user
from bot.utils.notifications import _user_display

router = Router()


@router.message(F.text)
async def text_input_dispatch(message: Message, session):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id in PREFS_ADDING_CITY:
        await _handle_add_city(message, text)
        return

    order_id = PRICE_STATE.get(user_id)
    if order_id is not None:
        await _handle_bid_price(message, session, order_id, text)
        return

    state = REVIEW_STATE.get(user_id)
    if state is not None and state.get("step") == "comment":
        state["comment"] = text[:500]
        if state.get("rating", 5) <= 2:
            state["step"] = "reason"
            await message.answer(
                "Что пошло не так?",
                reply_markup=review_reason_keyboard(state["order_id"]),
            )
        else:
            await message.answer("Спасибо за отзыв!")
            REVIEW_STATE.pop(user_id, None)
            await apply_review(
                session,
                state["order_id"],
                user_id,
                state["reviewee_id"],
                state["rating"],
                state.get("comment"),
                state.get("reason"),
            )
        return


async def _handle_add_city(message: Message, text: str) -> None:
    user_id = message.from_user.id
    PREFS_ADDING_CITY.discard(user_id)
    if len(text) > 40:
        await message.answer("Слишком длинное название. Попробуй короче.")
        return
    state = PREFS_STATE.setdefault(user_id, {})
    cities = list(state.get("cities", []))
    label = PREF_CITY_LABELS.get(text.lower(), text)
    if label.lower() not in [c.lower() for c in cities]:
        cities.append(label)
    state["cities"] = cities
    await message.answer(
        f"Город {label} добавлен в список.",
        reply_markup=prefs_cities_keyboard(cities),
    )


async def _handle_bid_price(message: Message, session, order_id: int, text: str) -> None:
    user_id = message.from_user.id
    if not text.isdigit() or int(text) <= 0:
        await message.answer("Введи цену числом (например: 1400).")
        return
    PRICE_STATE.pop(user_id, None)
    price = int(text)
    order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not order or order.status != OrderStatus.new:
        await message.answer("Заказ больше не актуален.")
        return
    ok, msg = await _create_bid(session, user_id, order_id, price)
    await message.answer(msg)


async def _create_bid(session, driver_id: int, order_id: int, price: int) -> tuple[bool, str]:
    from aiogram import Bot

    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return False, "Заказ не найден."
    if order.status != OrderStatus.new:
        return False, "Заказ уже закрыт."
    if order.customer_id == driver_id:
        return False, "Нельзя откликнуться на свой заказ."
    existing = await session.execute(
        select(Bid).where(and_(Bid.order_id == order_id, Bid.driver_id == driver_id))
    )
    if existing.scalar_one_or_none():
        return False, "Ты уже откликнулся на этот заказ."

    bid = Bid(order_id=order_id, driver_id=driver_id, proposed_price=price)
    session.add(bid)
    await session.commit()
    await session.refresh(bid)

    try:
        bot = Bot(token=settings.BOT_TOKEN)
        driver = await get_or_create_user(session, driver_id)
        pref = (
            await session.execute(select(DriverPreference).where(DriverPreference.driver_id == driver_id))
        ).scalar_one_or_none()
        if pref:
            from datetime import datetime
            pref.last_active_at = datetime.utcnow()
            await session.commit()
        await bot.send_message(
            order.customer_id,
            f"Водитель {_user_display(driver)} (рейтинг: {driver.rating:.1f}) "
            f"предложил {price} грн за заказ #{order_id}.",
            reply_markup=get_bid_notification_keyboard(settings.WEBAPP_BASE_URL, order_id, order.customer_id),
        )
        await bot.session.close()
    except Exception:
        pass

    return True, f"Отклик отправлен! Предложил {price} грн за заказ #{order_id}."