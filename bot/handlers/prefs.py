from __future__ import annotations

import json
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.filters import Command

from sqlalchemy import select

from db.models import DriverPreference, NotifFrequency
from bot.keyboards.inline import (
    prefs_type_keyboard,
    prefs_cities_keyboard,
    prefs_radius_keyboard,
    prefs_frequency_keyboard,
    prefs_main_keyboard,
    PREF_CITY_LABELS,
)
from bot.utils.helpers import get_or_create_user
from bot.utils.chat_state import PREFS_STATE, PREFS_ADDING_CITY

router = Router()


async def _load_prefs(session, user_id: int) -> DriverPreference:
    result = await session.execute(select(DriverPreference).where(DriverPreference.driver_id == user_id))
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = DriverPreference(driver_id=user_id, order_types="both", cities="[]", radius_km=50)
        session.add(pref)
        await session.commit()
        await session.refresh(pref)
    return pref


def _default_state(pref: DriverPreference) -> dict:
    try:
        cities = json.loads(pref.cities or "[]")
    except Exception:
        cities = []
    return {
        "type": pref.order_types,
        "cities": cities,
        "radius_km": pref.radius_km,
        "frequency": pref.frequency.value if hasattr(pref.frequency, "value") else str(pref.frequency),
    }


@router.message(Command("settings"))
@router.message(Command("preferences"))
@router.message(Command("notifications"))
async def cmd_settings(message: Message, session):
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.full_name)
    pref = await _load_prefs(session, user.id)
    PREFS_STATE[user.id] = _default_state(pref)
    st = PREFS_STATE[user.id]
    await message.answer(
        "Настройка уведомлений\n\n"
        "Какие заказы тебе интересны?\n\n"
        "Выбери тип:", 
        reply_markup=prefs_type_keyboard(st["type"]),
    )


@router.callback_query(F.data == "prefs:start")
async def prefs_start(call: CallbackQuery, session):
    user_id = call.from_user.id
    pref = await _load_prefs(session, user_id)
    PREFS_STATE[user_id] = _default_state(pref)
    st = PREFS_STATE[user_id]
    await call.message.edit_text(
        "Настройка уведомлений\n\nКакие заказы тебе интересны?",
        reply_markup=prefs_type_keyboard(st["type"]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("prefs:type:"))
async def prefs_type(call: CallbackQuery):
    user_id = call.from_user.id
    value = call.data.split(":")[2]
    state = PREFS_STATE.setdefault(user_id, {})
    state["type"] = value
    await call.message.edit_text(
        "Настройка уведомлений\n\nКакие заказы тебе интересны?",
        reply_markup=prefs_type_keyboard(value),
    )
    await call.answer()


@router.callback_query(F.data == "prefs:cities")
async def prefs_cities(call: CallbackQuery):
    user_id = call.from_user.id
    state = PREFS_STATE.setdefault(user_id, {})
    cities = state.get("cities", [])
    await call.message.edit_text(
        "Города отправления (можно добавить свои):",
        reply_markup=prefs_cities_keyboard(cities),
    )
    await call.answer()


@router.callback_query(F.data.startswith("prefs:city:"))
async def prefs_city_toggle(call: CallbackQuery):
    user_id = call.from_user.id
    city = call.data.split(":", 2)[2]
    state = PREFS_STATE.setdefault(user_id, {})
    cities = list(state.get("cities", []))
    idx = next((i for i, c in enumerate(cities) if c.lower() == city.lower()), None)
    if idx is not None:
        cities.pop(idx)
    else:
        cities.append(PREF_CITY_LABELS.get(city, city))
    state["cities"] = cities
    await call.message.edit_reply_markup(reply_markup=prefs_cities_keyboard(cities))
    await call.answer()


@router.callback_query(F.data == "prefs:city_add")
async def prefs_city_add(call: CallbackQuery):
    user_id = call.from_user.id
    PREFS_ADDING_CITY.add(user_id)
    await call.message.edit_text(
        "Напиши название города (например: Чернигов):",
        reply_markup=prefs_cities_keyboard(PREFS_STATE.setdefault(user_id, {}).get("cities", [])),
    )
    await call.answer()


@router.callback_query(F.data == "prefs:radius")
async def prefs_radius(call: CallbackQuery):
    user_id = call.from_user.id
    state = PREFS_STATE.setdefault(user_id, {})
    radius = state.get("radius_km", 50)
    await call.message.edit_text(
        "Радиус поиска (от города отправления):",
        reply_markup=prefs_radius_keyboard(radius),
    )
    await call.answer()


@router.callback_query(F.data.startswith("prefs:radius:"))
async def prefs_radius_set(call: CallbackQuery):
    user_id = call.from_user.id
    value = int(call.data.split(":")[2])
    state = PREFS_STATE.setdefault(user_id, {})
    state["radius_km"] = value
    await call.message.edit_text(
        "Радиус поиска:", reply_markup=prefs_radius_keyboard(value),
    )
    await call.answer()


@router.callback_query(F.data == "prefs:freq")
async def prefs_freq(call: CallbackQuery):
    user_id = call.from_user.id
    state = PREFS_STATE.setdefault(user_id, {})
    await call.message.edit_text(
        "Как часто присылать уведомления о новых заказах?",
        reply_markup=prefs_frequency_keyboard(state.get("frequency", "instant")),
    )
    await call.answer()


@router.callback_query(F.data.startswith("prefs:freq:"))
async def prefs_freq_set(call: CallbackQuery):
    user_id = call.from_user.id
    value = call.data.split(":")[2]
    state = PREFS_STATE.setdefault(user_id, {})
    state["frequency"] = value
    await call.message.edit_text(
        "Как часто присылать уведомления?",
        reply_markup=prefs_frequency_keyboard(value),
    )
    await call.answer()


@router.callback_query(F.data == "prefs:save")
async def prefs_save(call: CallbackQuery, session):
    user_id = call.from_user.id
    state = PREFS_STATE.get(user_id)
    if not state:
        await call.answer("Настройки не найдены. Начни заново.", show_alert=True)
        return
    pref = await _load_prefs(session, user_id)
    pref.order_types = state.get("type", "both")
    pref.cities = json.dumps(state.get("cities", []), ensure_ascii=False)
    pref.radius_km = state.get("radius_km", 50)
    freq = state.get("frequency", "instant")
    pref.frequency = NotifFrequency(freq) if freq in ("instant", "hourly", "daily") else NotifFrequency.instant
    pref.last_active_at = datetime.utcnow()
    await session.commit()

    cities_text = ", ".join(state.get("cities", [])) or "Не выбраны"
    radius_label = "Вся Украина" if pref.radius_km >= 9999 else f"{pref.radius_km} км"
    freq_labels = {"instant": "Мгновенно", "hourly": "Раз в час", "daily": "Раз в день (9:00)"}
    type_labels = {"cargo": "Только грузы", "passenger": "Только пассажиры", "both": "И то, и другое"}

    await call.message.edit_text(
        "Настройки сохранены!\n\n"
        f"Тип: {type_labels.get(pref.order_types, pref.order_types)}\n"
        f"Города: {cities_text}\n"
        f"Радиус: {radius_label}\n"
        f"Частота: {freq_labels.get(pref.frequency.value)}",
        reply_markup=prefs_main_keyboard(),
    )
    PREFS_STATE.pop(user_id, None)
    await call.answer("Сохранено!")


@router.callback_query(F.data.startswith("prefs:restore:"))
async def prefs_restore(call: CallbackQuery, session):
    user_id = call.from_user.id
    value = call.data.split(":")[2]
    pref = (await session.execute(select(DriverPreference).where(DriverPreference.driver_id == user_id))).scalar_one_or_none()
    if pref:
        pref.frequency = NotifFrequency.instant if value == "instant" else NotifFrequency.daily
        pref.last_active_at = datetime.utcnow()
        await session.commit()
    if value == "instant":
        await call.message.edit_text("Отлично! Вернули мгновенные уведомления.")
    else:
        await call.message.edit_text("Ок, уведомления останутся 1 раз в день.")
    await call.answer()