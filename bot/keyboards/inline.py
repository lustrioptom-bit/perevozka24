from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app={"url": webapp_url})]
        ]
    )


def get_help_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app={"url": webapp_url})],
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
            ]
        ]
    )
