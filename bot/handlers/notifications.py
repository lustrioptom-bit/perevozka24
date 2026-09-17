from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery

from sqlalchemy import select, and_

from db.models import Bid, Order, OrderStatus, Notification, NotificationType, User
from config import settings
from bot.utils.notifications import _user_display, build_order_card_text
from bot.utils.chat_state import PRICE_STATE
from bot.keyboards.inline import (
    get_bid_price_keyboard,
    get_notification_actions_keyboard,
)

router = Router()


@router.callback_query(F.data.startswith("notif:reply:"))
async def notif_reply(call: CallbackQuery, session):
    order_id = int(call.data.split(":")[2])
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or order.status != OrderStatus.new:
        await call.answer("Заказ больше не актуален.", show_alert=True)
        return
    existing = await session.execute(
        select(Bid).where(and_(Bid.order_id == order_id, Bid.driver_id == call.from_user.id))
    )
    if existing.scalar_one_or_none():
        await call.answer("Ты уже откликнулся на этот заказ.", show_alert=True)
        return
    PRICE_STATE[call.from_user.id] = order_id
    await call.message.answer(
        f"Предложи свою цену за заказ #{order_id}:\n\n"
        "Или выбери из бюджета клиента:",
        reply_markup=get_bid_price_keyboard(order_id, order.price),
    )
    await call.answer()


@router.callback_query(F.data.startswith("notif:price:"))
async def notif_price_preset(call: CallbackQuery, session):
    parts = call.data.split(":")
    order_id = int(parts[2])
    price = int(parts[3])
    PRICE_STATE.pop(call.from_user.id, None)
    await _place_bid(call, session, order_id, price)


@router.callback_query(F.data.startswith("notif:details:"))
async def notif_details(call: CallbackQuery, session):
    order_id = int(call.data.split(":")[2])
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    customer = (await session.execute(select(User).where(User.id == order.customer_id))).scalar_one_or_none()

    if customer:
        from bot.utils.reviews import reviews_pagination_markup, count_reviews

        name = _user_display(customer)
        verified = "🛡 Проверенный телефон" if customer.phone_verified and customer.phone else ""
        total = await count_reviews(session, customer.id)
        text = (
            f"Профиль клиента: {name}\n"
            f"⭐ {customer.rating:.1f} ({customer.rating_count} отзывов)\n"
            f"✅ {customer.deals_completed} успешных заказов\n"
            f"{verified}\n\n"
            f"Заказ #{order_id}: {order.from_text} → {order.to_text}"
        )
        await call.message.edit_text(text, reply_markup=reviews_pagination_markup(customer.id, 0, total > 5))
    else:
        text = f"Заказ #{order_id}: {order.from_text} → {order.to_text}"
        await call.message.edit_text(text)
    await call.answer()


@router.callback_query(F.data.startswith("notif:skip:"))
async def notif_skip(call: CallbackQuery, session):
    order_id = int(call.data.split(":")[2])
    session.add(
        Notification(user_id=call.from_user.id, order_id=order_id, type=NotificationType.new_order, sent=True)
    )
    await session.commit()
    await call.message.edit_text("Ок, больше не пришлём этот заказ.")
    await call.answer()


@router.callback_query(F.data.startswith("notif:back:"))
async def notif_back(call: CallbackQuery, session):
    order_id = int(call.data.split(":")[2])
    PRICE_STATE.pop(call.from_user.id, None)
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        await call.answer("Заказ не найден.")
        return
    customer = (await session.execute(select(User).where(User.id == order.customer_id))).scalar_one_or_none()
    from bot.utils.notifications import build_order_card_text
    await call.message.edit_text(
        build_order_card_text(order, customer),
        reply_markup=get_notification_actions_keyboard(settings.WEBAPP_BASE_URL, order_id, call.from_user.id),
    )
    await call.answer()


async def _place_bid(call: CallbackQuery, session, order_id: int, price: int):
    from bot.handlers.inputs import _create_bid

    driver_id = call.from_user.id
    ok, msg = await _create_bid(session, driver_id, order_id, price)
    if not ok:
        await call.answer(msg, show_alert=True)
        return
    await call.message.edit_text(msg)
    await call.answer()