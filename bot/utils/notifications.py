from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Order,
    OrderType,
    User,
    Bid,
    DriverPreference,
    Notification,
    NotificationType,
    NotifFrequency,
)
from bot.utils.geo import haversine

MAX_NOTIF_PER_HOUR = 5
INACTIVE_DAYS = 3


def _user_display(user: User | None) -> str:
    if not user:
        return "Пользователь"
    return user.full_name or user.username or f"ID {user.id}"


def build_order_card_text(order: Order, customer: User | None) -> str:
    type_label = "Груз" if order.type == OrderType.freight else "Пассажиры"
    date_text = order.date_time.strftime("%d.%m.%Y, %H:%M") if order.date_time else "—"
    if customer:
        customer_name = _user_display(customer)
        customer_line = f"Клиент: {customer_name} (⭐ {customer.rating:.1f}, {customer.deals_completed} сделок)"
    else:
        customer_line = ""
    return (
        f"Новый заказ по твоему маршруту!\n\n"
        f"Маршрут: {order.from_text} → {order.to_text}\n"
        f"Дата: {date_text}\n"
        f"Тип: {type_label}\n"
        f"Бюджет клиента: {order.price} ₴\n"
        f"Описание: \"{order.description or '—'}\"\n\n"
        f"{customer_line}"
    ).strip()


def _cities_match(order: Order, cities: list[str]) -> bool:
    haystack = f"{order.from_text} {order.to_text}".lower()
    return any(c.strip().lower() in haystack for c in cities if c.strip())


async def _driver_last_location(session: AsyncSession, driver_id: int):
    result = await session.execute(
        select(Order.driver_lat, Order.driver_lng)
        .where(
            Order.driver_id == driver_id,
            Order.driver_lat.is_not(None),
            Order.driver_lng.is_not(None),
        )
        .order_by(Order.driver_location_updated_at.desc().nulls_last())
        .limit(1)
    )
    return result.first()


def _matches_order(pref: DriverPreference, order: Order, driver_loc) -> bool:
    if pref.order_types not in ("both", order.type.value):
        return False
    if pref.radius_km >= 9999:
        return True
    try:
        cities = json.loads(pref.cities or "[]")
    except Exception:
        cities = []
    if cities and _cities_match(order, cities):
        return True
    if driver_loc is not None and driver_loc.lat is not None and driver_loc.lng is not None:
        dist = haversine(order.from_lat, order.from_lng, float(driver_loc.lat), float(driver_loc.lng))
        if dist <= pref.radius_km:
            return True
    return False


async def _maybe_downgrade(session: AsyncSession, pref: DriverPreference, bot: Bot) -> None:
    if pref.frequency != NotifFrequency.instant:
        return
    if not pref.last_active_at:
        pref.last_active_at = datetime.utcnow()
        return
    if datetime.utcnow() - pref.last_active_at > timedelta(days=INACTIVE_DAYS):
        pref.frequency = NotifFrequency.daily
        try:
            from bot.keyboards.inline import get_restore_instant_keyboard
            await bot.send_message(
                pref.driver_id,
                "Заметили, что ты не активен. Сократили уведомления до 1 раза в день.\n"
                "Вернуть мгновенные?",
                reply_markup=get_restore_instant_keyboard(),
            )
        except Exception:
            pass


async def notify_drivers_new_order(
    session: AsyncSession,
    order: Order,
    bot: Bot,
    webapp_url: str,
) -> None:
    """Find drivers matching this order and notify them (with spam protection)."""
    from bot.keyboards.inline import get_feed_keyboard

    prefs = (await session.execute(select(DriverPreference))).scalars().all()
    now = datetime.utcnow()

    for pref in prefs:
        driver_id = pref.driver_id
        if driver_id == order.customer_id:
            continue
        if not _matches_order(pref, order, await _driver_last_location(session, driver_id)):
            continue
        seen = await session.execute(
            select(Notification.id).where(
                Notification.user_id == driver_id,
                Notification.order_id == order.id,
            )
        )
        if seen.scalar_one_or_none():
            continue
        has_bid = await session.execute(
            select(Bid.id).where(Bid.driver_id == driver_id, Bid.order_id == order.id)
        )
        if has_bid.scalar_one_or_none():
            continue

        await _maybe_downgrade(session, pref, bot)

        if pref.frequency == NotifFrequency.instant:
            if pref.notif_hour_start is None or now - pref.notif_hour_start >= timedelta(hours=1):
                pref.notif_hour_start = now
                pref.notif_count_this_hour = 0
            if pref.notif_count_this_hour < MAX_NOTIF_PER_HOUR:
                await _send_order_card(session, pref.driver_id, order, bot, webapp_url)
                pref.notif_count_this_hour += 1
                pref.last_notified_at = now
                session.add(
                    Notification(
                        user_id=driver_id,
                        order_id=order.id,
                        type=NotificationType.new_order,
                        sent=True,
                    )
                )
            else:
                session.add(
                    Notification(
                        user_id=driver_id,
                        order_id=order.id,
                        type=NotificationType.new_order,
                        sent=False,
                    )
                )
                pref.last_notified_at = now
        else:
            session.add(
                Notification(
                    user_id=driver_id,
                    order_id=order.id,
                    type=NotificationType.new_order,
                    sent=False,
                )
            )
            pref.last_notified_at = now

    await session.commit()


async def _send_order_card(
    session: AsyncSession,
    driver_id: int,
    order: Order,
    bot: Bot,
    webapp_url: str,
) -> None:
    from bot.keyboards.inline import get_notification_actions_keyboard

    customer = (
        await session.execute(select(User).where(User.id == order.customer_id))
    ).scalar_one_or_none()
    await bot.send_message(
        driver_id,
        build_order_card_text(order, customer),
        reply_markup=get_notification_actions_keyboard(webapp_url, order.id, driver_id),
    )


async def _send_digest_message(bot: Bot, webapp_url: str, user_id: int, count: int) -> None:
    from bot.keyboards.inline import get_feed_keyboard

    text = (
        f"За последнее время появилось {count} новых заказов по твоим интересам.\n"
        f"Открой ленту заказов:"
    )
    await bot.send_message(user_id, text, reply_markup=get_feed_keyboard(webapp_url, user_id))


async def send_hourly_digest(bot: Bot, webapp_url: str) -> None:
    from db.engine import async_session

    cutoff = datetime.utcnow() - timedelta(hours=3)
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Notification).where(
                    Notification.sent == False,  # noqa: E712
                    Notification.type == NotificationType.new_order,
                    Notification.created_at >= cutoff,
                )
            )
        ).scalars().all()
        by_user: dict[int, list[Notification]] = {}
        for n in rows:
            by_user.setdefault(n.user_id, []).append(n)
        for user_id, items in by_user.items():
            pref = (
                await session.execute(
                    select(DriverPreference).where(DriverPreference.driver_id == user_id)
                )
            ).scalar_one_or_none()
            if not pref or pref.frequency == NotifFrequency.daily:
                continue
            await _send_digest_message(bot, webapp_url, user_id, len(items))
            for n in items:
                n.sent = True
        await session.commit()


async def send_daily_digest(bot: Bot, webapp_url: str) -> None:
    from db.engine import async_session

    async with async_session() as session:
        rows = (
            await session.execute(
                select(Notification).where(
                    Notification.sent == False,  # noqa: E712
                    Notification.type == NotificationType.new_order,
                )
            )
        ).scalars().all()
        by_user: dict[int, list[Notification]] = {}
        for n in rows:
            by_user.setdefault(n.user_id, []).append(n)
        for user_id, items in by_user.items():
            pref = (
                await session.execute(
                    select(DriverPreference).where(DriverPreference.driver_id == user_id)
                )
            ).scalar_one_or_none()
            if not pref or pref.frequency != NotifFrequency.daily:
                continue
            await _send_digest_message(bot, webapp_url, user_id, len(items))
            for n in items:
                n.sent = True
        await session.commit()