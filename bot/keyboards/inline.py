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


def get_bid_notification_keyboard(webapp_url: str, order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Выбрать водителя",
                    web_app={"url": f"{webapp_url}?startapp=order_{order_id}&user_id={user_id}"},
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


# ─── Notification buttons (new order) ───

def get_notification_actions_keyboard(webapp_url: str, order_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Откликнуться",
                    callback_data=f"notif:reply:{order_id}",
                ),
                InlineKeyboardButton(
                    text="Подробнее",
                    callback_data=f"notif:details:{order_id}",
                ),
                InlineKeyboardButton(
                    text="Не интересно",
                    callback_data=f"notif:skip:{order_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Открыть в приложении",
                    web_app={"url": f"{webapp_url}?startapp=order_{order_id}&user_id={user_id}"},
                )
            ],
        ]
    )


def get_bid_price_keyboard(order_id: int, budget: int) -> InlineKeyboardMarkup:
    presets = []
    seen = set()
    for p in (budget, budget - 100, budget - 200, budget - 300):
        if p > 0 and p not in seen:
            presets.append(p)
            seen.add(p)
    rows = [InlineKeyboardButton(text=f"{p} грн", callback_data=f"notif:price:{order_id}:{p}") for p in presets]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            rows,
            [InlineKeyboardButton(text="Вернуться к заказу", callback_data=f"notif:back:{order_id}")],
        ]
    )


def get_feed_keyboard(webapp_url: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть ленту заказов", web_app={"url": f"{webapp_url}?user_id={user_id}"})],
        ]
    )


def get_restore_instant_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, мгновенно", callback_data="prefs:restore:instant"),
                InlineKeyboardButton(text="Нет, оставить", callback_data="prefs:restore:daily"),
            ]
        ]
    )


# ─── Driver preferences wizard ───

COMMON_CITIES = [
    "Харьков", "Киев", "Днепр", "Одесса",
    "Львов", "Запорожье", "Винница", "Полтава",
]

PREF_CITY_LABELS = {
    "харків": "Харьков", "харьков": "Харьков", "київ": "Киев", "киев": "Киев",
    "дніпро": "Днепр", "днепр": "Днепр", "одеса": "Одесса", "одесса": "Одесса",
    "львів": "Львов", "львов": "Львов", "запоріжжя": "Запорожье", "запорожье": "Запорожье",
    "вінниця": "Винница", "винница": "Винница", "полтава": "Полтава",
}


def prefs_type_keyboard(selected: str) -> InlineKeyboardMarkup:
    def label(key: str, text: str) -> str:
        return f"{'✔ ' if selected == key else ''}{text}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(label("cargo", "Только грузы"), callback_data="prefs:type:cargo")],
            [InlineKeyboardButton(label("passenger", "Только пассажиры"), callback_data="prefs:type:passenger")],
            [InlineKeyboardButton(label("both", "И то, и другое"), callback_data="prefs:type:both")],
            [InlineKeyboardButton("Далее", callback_data="prefs:cities")],
        ]
    )


def prefs_cities_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for city in COMMON_CITIES:
        mark = "✔ " if city.lower() in [c.lower() for c in selected] else ""
        rows.append([InlineKeyboardButton(f"{mark}{city}", callback_data=f"prefs:city:{city.lower()}")])
    rows.append(
        [
            InlineKeyboardButton("Добавить свой город", callback_data="prefs:city_add"),
            InlineKeyboardButton("Далее", callback_data="prefs:radius"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prefs_radius_keyboard(opened: int) -> InlineKeyboardMarkup:
    def label(val: int, text: str) -> str:
        return f"{'✔ ' if opened == val else ''}{text}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(label(10, "10 км"), callback_data="prefs:radius:10")],
            [InlineKeyboardButton(label(50, "50 км"), callback_data="prefs:radius:50")],
            [InlineKeyboardButton(label(100, "100 км"), callback_data="prefs:radius:100")],
            [InlineKeyboardButton(label(9999, "Вся Украина"), callback_data="prefs:radius:9999")],
            [InlineKeyboardButton("Далее", callback_data="prefs:freq")],
        ]
    )


def prefs_frequency_keyboard(selected: str) -> InlineKeyboardMarkup:
    def label(key: str, text: str) -> str:
        return f"{'✔ ' if selected == key else ''}{text}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(label("instant", "Мгновенно"), callback_data="prefs:freq:instant")],
            [InlineKeyboardButton(label("hourly", "Раз в час (сводка)"), callback_data="prefs:freq:hourly")],
            [InlineKeyboardButton(label("daily", "Раз в день (9:00)"), callback_data="prefs:freq:daily")],
            [InlineKeyboardButton("Сохранить настройки", callback_data="prefs:save")],
            [InlineKeyboardButton("Назад", callback_data="prefs:radius")],
        ]
    )


def prefs_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("Изменить настройки", callback_data="prefs:start")],
        ]
    )


# ─── Reviews ───

def rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(str(i), callback_data=f"rev:rate:{order_id}:{i}")
                for i in range(1, 6)
            ]
        ]
    )


def review_comment_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("Пропустить", callback_data=f"rev:skipcomment:{order_id}")],
        ]
    )


REASONS = {
    "late": "Водитель опоздал",
    "rude": "Водитель был груб",
    "dirty": "Машина была грязной",
    "other": "Другое",
}


def review_reason_keyboard(order_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text, callback_data=f"rev:reason:{order_id}:{key}")]
        for key, text in REASONS.items()
    ]
    rows.append([InlineKeyboardButton("Пропустить", callback_data=f"rev:skipreason:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reviews_pagination_keyboard(user_id: int, offset: int, has_more: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_more:
        rows.append(
            [InlineKeyboardButton("Показать еще 5", callback_data=f"rev:more:{user_id}:{offset + 5}")]
        )
    rows.append([InlineKeyboardButton("Закрыть", callback_data=f"rev:close:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── Profile ───

def profile_keyboard(user: "User", self_view: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Отзывы", callback_data=f"rev:more:{user.id}:0"),
        ]
    ]
    if user.username:
        rows.append([InlineKeyboardButton("Написать", url=f"https://t.me/{user.username}")])
    if self_view:
        rows.append([InlineKeyboardButton("Настройки уведомлений", callback_data="prefs:start")])
    rows.append([_share_button()])
    return InlineKeyboardMarkup(inline_keyboard=rows)