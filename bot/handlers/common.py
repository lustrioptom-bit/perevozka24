from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import settings
from bot.keyboards.inline import get_start_keyboard, get_help_keyboard
from bot.utils.helpers import get_or_create_user, get_admin_stats, COMPLETED_DEALS_PROMO_LIMIT

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
        f"Лента заказов: {settings.CHANNEL_ID}",
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
