from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram import Bot

from bot.keyboards.inline import (
    rating_keyboard,
    review_comment_keyboard,
    review_reason_keyboard,
    REASONS,
)
from bot.utils.reviews import (
    reviews_page_text,
    reviews_pagination_markup,
    count_reviews,
    apply_review,
)
from bot.utils.chat_state import REVIEW_STATE

router = Router()


async def request_review(bot: Bot, order_id: int, reviewer_id: int, reviewee_id: int, reviewee_display: str) -> None:
    REVIEW_STATE[reviewer_id] = {"order_id": order_id, "reviewee_id": reviewee_id, "step": "rating"}
    await bot.send_message(
        reviewer_id,
        f"Поездка завершена!\n\nКак прошла поездка с {reviewee_display}?",
        reply_markup=rating_keyboard(order_id),
    )


def _state(call: CallbackQuery) -> dict | None:
    return REVIEW_STATE.get(call.from_user.id)


@router.callback_query(F.data.startswith("rev:rate:"))
async def rev_rate(call: CallbackQuery, session):
    parts = call.data.split(":")
    order_id = int(parts[2])
    rating = int(parts[3])
    state = _state(call)
    if not state or state.get("order_id") != order_id or state.get("step") != "rating":
        await call.answer("Сессия оценки истекла.", show_alert=True)
        return
    state["rating"] = rating
    state["step"] = "comment"
    if rating <= 2:
        await call.message.edit_text(
            "Нам жаль, что поездка не понравилась.\n\nЧто пошло не так?",
            reply_markup=review_reason_keyboard(order_id),
        )
    else:
        await call.message.edit_text(
            "Оставь комментарий (необязательно):",
            reply_markup=review_comment_keyboard(order_id),
        )
    await call.answer()


@router.callback_query(F.data.startswith("rev:skipcomment:"))
async def rev_skipcomment(call: CallbackQuery, session):
    await _finish_or_reason(call, session, comment=None)


@router.callback_query(F.data.startswith("rev:reason:"))
async def rev_reason(call: CallbackQuery, session):
    parts = call.data.split(":")
    order_id = int(parts[2])
    key = parts[3]
    state = _state(call)
    if not state or state.get("order_id") != order_id:
        await call.answer("Сессия оценки истекла.", show_alert=True)
        return
    state["reason"] = REASONS.get(key, key)
    await call.message.edit_text("Спасибо за отзыв!", reply_markup=None)
    await _save(call, session, state)
    await call.answer()


@router.callback_query(F.data.startswith("rev:skipreason:"))
async def rev_skipreason(call: CallbackQuery, session):
    parts = call.data.split(":")
    order_id = int(parts[2])
    state = _state(call)
    if not state or state.get("order_id") != order_id:
        await call.answer("Сессия оценки истекла.", show_alert=True)
        return
    state["reason"] = None
    await call.message.edit_text("Спасибо за отзыв!", reply_markup=None)
    await _save(call, session, state)
    await call.answer()


async def _finish_or_reason(call: CallbackQuery, session, comment: str | None):
    state = _state(call)
    if not state:
        await call.answer("Сессия оценки истекла.", show_alert=True)
        return
    state["comment"] = comment
    if state.get("rating", 5) <= 2:
        state["step"] = "reason"
        await call.message.edit_text(
            "Что пошло не так?",
            reply_markup=review_reason_keyboard(state["order_id"]),
        )
    else:
        await call.message.edit_text("Спасибо за отзыв!", reply_markup=None)
        await _save(call, session, state)
    await call.answer()


async def _save(call: CallbackQuery, session, state: dict):
    REVIEW_STATE.pop(call.from_user.id, None)
    await apply_review(
        session,
        state["order_id"],
        call.from_user.id,
        state["reviewee_id"],
        state["rating"],
        state.get("comment"),
        state.get("reason"),
    )


# ─── Reviews list (pagination) ───

@router.callback_query(F.data.startswith("rev:more:"))
async def rev_more(call: CallbackQuery, session):
    parts = call.data.split(":")
    user_id = int(parts[2])
    offset = int(parts[3]) if len(parts) > 3 else 0
    total = await count_reviews(session, user_id)
    text = await reviews_page_text(session, user_id, offset)
    has_more = offset + 5 < total
    await call.message.edit_text(text, reply_markup=reviews_pagination_markup(user_id, offset, has_more))
    await call.answer()


@router.callback_query(F.data.startswith("rev:close:"))
async def rev_close(call: CallbackQuery):
    await call.message.edit_text("Отзывы закрыты.")
    await call.answer()