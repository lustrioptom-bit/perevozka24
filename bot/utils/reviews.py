from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Review, User
from bot.keyboards.inline import reviews_pagination_keyboard

PAGE_SIZE = 5


async def count_reviews(session: AsyncSession, user_id: int) -> int:
    return (
        await session.execute(
            select(func.count(Review.id)).where(Review.reviewee_id == user_id)
        )
    ).scalar() or 0


async def get_reviews(session: AsyncSession, user_id: int, offset: int = 0, limit: int = PAGE_SIZE) -> list[Review]:
    result = await session.execute(
        select(Review)
        .where(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def reviews_page_text(session: AsyncSession, user_id: int, offset: int = 0) -> str:
    reviewee = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    total = await count_reviews(session, user_id)
    name = (reviewee.full_name or reviewee.username or f"ID {user_id}") if reviewee else f"ID {user_id}"
    lines = [f"Отзывы о {name} ({total})", ""]
    reviews = await get_reviews(session, user_id, offset)
    reviewers = {}
    for r in reviews:
        reviewer = (
            await session.execute(select(User).where(User.id == r.reviewer_id))
        ).scalar_one_or_none()
        if reviewer:
            reviewers[r.reviewer_id] = (reviewer.full_name or reviewer.username or f"ID {reviewer.id}")
    if not reviews:
        lines.append("Пока нет отзывов.")
    for r in reviews:
        stars = "⭐" * r.rating
        from datetime import datetime
        date = r.created_at.strftime("%d.%m.%Y") if isinstance(r.created_at, datetime) else ""
        comment = f"\n\"{r.comment}\"" if r.comment else ""
        lines.append(f"{stars} {reviewers.get(r.reviewer_id, 'Пользователь')} | {date}{comment}")
    return "\n".join(lines)


def reviews_pagination_markup(user_id: int, offset: int, has_more: bool):
    return reviews_pagination_keyboard(user_id, offset, has_more)


async def apply_review(session: AsyncSession, order_id: int, reviewer_id: int, reviewee_id: int, rating: int, comment: str | None = None, reason: str | None = None) -> None:
    review = Review(
        order_id=order_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        rating=max(1, min(5, rating)),
        comment=comment,
        reason=reason,
    )
    session.add(review)

    reviewee = (await session.execute(select(User).where(User.id == reviewee_id))).scalar_one_or_none()
    if reviewee:
        old_count = reviewee.rating_count or 0
        old_sum = reviewee.rating * old_count
        new_count = old_count + 1
        reviewee.rating = round((old_sum + review.rating) / new_count, 1)
        reviewee.rating_count = new_count

    await session.commit()
    await session.refresh(reviewee) if reviewee else None