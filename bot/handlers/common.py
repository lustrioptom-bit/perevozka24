from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import settings
from bot.keyboards.inline import get_start_keyboard, get_help_keyboard, get_share_keyboard, prefs_main_keyboard
from bot.utils.helpers import get_or_create_user, get_admin_stats, COMPLETED_DEALS_PROMO_LIMIT
from db.models import UserRole

router = Router()


def _webapp_url(user_id: int = 0) -> str:
    base = settings.WEBAPP_BASE_URL
    if user_id:
        return f"{base}?user_id={user_id}"
    return base


@router.message(CommandStart())
async def cmd_start(message: Message, session):
    user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.full_name)
    url = _webapp_url(message.from_user.id)

    payload = message.text.replace("/start", "").strip()
    if payload.startswith("order_"):
        order_id = payload.replace("order_", "")
        url += f"&startapp=order_{order_id}"
        await message.answer(
            f"Откройте приложение, чтобы откликнуться на заказ #{order_id}:",
            reply_markup=get_start_keyboard(url),
            parse_mode="HTML",
        )
        return

    if payload == "driver":
        if user.role == UserRole.client:
            user.role = UserRole.driver
        elif user.role == UserRole.both:
            pass
        else:
            user.role = UserRole.driver
        await session.commit()
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n\n"
            "<b>Perevozka24</b> — платформа для водителей.\n\n"
            "<b>Как начать:</b>\n"
            "— Откройте приложение\n"
            "— Смотрите ленту заказов на карте\n"
            "— Откликайтесь с ценой и зарабатывайте!\n\n"
            f"До <b>{COMPLETED_DEALS_PROMO_LIMIT}</b> сделок — 0% комиссии!\n\n"
            "<b>Настройте уведомления о новых заказах:</b>",
            reply_markup=prefs_main_keyboard(),
            parse_mode="HTML",
        )
        return

    if payload == "client":
        if user.role == UserRole.driver:
            user.role = UserRole.both
        elif user.role == UserRole.client:
            pass
        else:
            user.role = UserRole.both
        await session.commit()
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n\n"
            "<b>Perevozka24</b> — платформа для поиска попутчиков и грузоперевозок.\n\n"
            "<b>Как создать заказ:</b>\n"
            "— Откройте приложение\n"
            "— Укажите маршрут, дату и бюджет\n"
            "— Получите предложения от водителей\n"
            "— Выберите лучшее и поезжайте!\n\n"
            f"До <b>{COMPLETED_DEALS_PROMO_LIMIT}</b> сделок — 0% комиссии!",
            reply_markup=get_start_keyboard(url),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        "<b>Perevozka24</b> — платформа для поиска попутчиков и грузоперевозок.\n\n"
        "<b>Как это работает:</b>\n"
        "— Создайте заказ (поездка или доставка)\n"
        "— Водители откликаются с ценой\n"
        "— Выбираете лучшее предложение и едете!\n\n"
        f"<b>Акция:</b> первые {COMPLETED_DEALS_PROMO_LIMIT} сделок — бесплатно!",
        reply_markup=get_start_keyboard(url),
        parse_mode="HTML",
    )


@router.message(Command("share"))
async def cmd_share(message: Message):
    await message.answer(
        "Поделитесь ботом с друзьями и коллегами:\n\n"
        "— пассажиры найдут попутчиков и перевозчиков\n"
        "— водители получат доступ к ленте заказов\n\n"
        "Спасибо за поддержку!",
        reply_markup=get_share_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    url = _webapp_url(message.from_user.id)
    await message.answer(
        "<b>Как пользоваться сервисом</b>\n\n"
        "<b>Для пассажиров / грузоотправителей:</b>\n"
        "1. Откройте приложение\n"
        "2. Перейдите во вкладку «Создать заказ»\n"
        "3. Выберите тип: Поездка или Груз\n"
        "4. Укажите маршрут, дату и бюджет\n"
        "5. Ожидайте откликов водителей\n\n"
        "<b>Для водителей / перевозчиков:</b>\n"
        "1. Откройте приложение\n"
        "2. Во вкладке «Лента заказов» найдите подходящий заказ\n"
        "3. Нажмите «Откликнуться» и предложите цену\n"
        "4. После принятия — свяжитесь с клиентом\n\n"
        f"Лента заказов: <a href=\"{settings.CHANNEL_LINK}\">@perevozkauakh</a>",
        reply_markup=get_help_keyboard(url),
        parse_mode="HTML",
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, session):
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("Нет доступа.")
        return
    stats = await get_admin_stats(session)
    await message.answer(
        f"<b>Статистика</b>\n\n"
        f"Пользователей: {stats['total_users']}\n"
        f"Активных заказов: {stats['active_orders']}\n"
        f"Выполнено сделок: {stats['completed_deals']} / {COMPLETED_DEALS_PROMO_LIMIT}",
        parse_mode="HTML",
    )
