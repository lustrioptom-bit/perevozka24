from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from urllib.parse import quote

BOT_USERNAME = "perevozkakh_bot"


def _share_button(text: str = "Поделиться") -> InlineKeyboardButton:
    share_url = (
        "https://t.me/share/url?url="
        f"{quote('https://t.me/' + BOT_USERNAME, safe='')}"
        f"&text={quote('Perevozka24 — попутчики и перевозки в Telegram! Открывай и создавай первый заказ.', safe='')}"
    )
    return InlineKeyboardButton(text=text, url=share_url)


def get_start_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app={"url": webapp_url})],
            [_share_button()],
        ]
    )


def get_help_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app={"url": webapp_url})],
            [_share_button()],
        ]
    )


def get_share_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_share_button("Поделиться ботом")],
        ]
    )


def get_order_notification_keyboard(webapp_url: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Откликнуться в WebApp",
                    web_app={"url": f"{webapp_url}?startapp=order_{order_id}"},
                )
            ]
        ]
    )


def get_bid_notification_keyboard(webapp_url: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Выбрать водителя",
                    web_app={"url": f"{webapp_url}?startapp=order_{order_id}"},
                )
            ]
        ]
    )


def get_channel_keyboard(order_id: int, webapp_url: str, bot_username: str = "perevozkakh_bot") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Откликнуться на заказ",
                    url=f"https://t.me/{bot_username}?start=order_{order_id}",
                )
            ],
            [_share_button("Поделиться сервисом")],
        ]
    )
