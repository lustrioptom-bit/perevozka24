# Perevozka24 — Гибридная биржа логистики и пассажирских перевозок

## Быстрый старт

1. Клонируйте проект и установите зависимости:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Создайте файл `.env` из примера:
   ```
   copy .env.example .env
   ```
   Заполните токен бота, ID администраторов, URL БД.

3. Создайте базу данных PostgreSQL:
   ```
   createdb perevozka
   ```

4. Запустите миграции:
   ```
   alembic upgrade head
   ```

5. Запустите приложение:
   ```
   python app.py
   ```
   Бот + WebApp сервер запустятся одновременно.

6. Настройте WebApp URL в настройках BotFather → WebApp → URL.

## Команды бота
- `/start` — регистрация + кнопка запуска WebApp
- `/help` — инструкция по использованию
- `/stats` — статистика (только админы)

## Структура проекта
```
├── app.py                  # Точка входа (bot + web)
├── config.py               # Настройки из .env
├── db/
│   ├── engine.py           # SQLAlchemy engine + сессии
│   └── models.py           # User, Vehicle, Order, Bid
├── bot/
│   ├── setup.py            # Bot + Dispatcher factory
│   ├── handlers/           # /start, /help, /stats, /broadcast
│   ├── keyboards/          # Inline клавиатуры
│   ├── middlewares/        # Database middleware
│   └── utils/              # geo.py, helpers.py, channel.py
├── webapp/
│   ├── app.py              # FastAPI app
│   ├── routers/api.py      # REST API эндпоинты
│   ├── static/css/         # style.css
│   ├── static/js/app.js    # Frontend JS
│   └── templates/          # index.html
└── alembic/                # Миграции
```

## Монетизация (MVP)
Первые 150 сделок — 0% комиссии. Счётчик отображается в профиле водителя.
После 150 сделок активируется комиссия за подтверждённые сделки.

## API Эндпоинты
| Method | Path | Описание |
|--------|------|----------|
| GET | `/api/user/{id}` | Профиль пользователя |
| POST | `/api/user/role` | Обновить роль |
| GET | `/api/vehicles` | Список транспорта |
| POST | `/api/vehicles` | Добавить транспорт |
| DELETE | `/api/vehicles/{id}` | Удалить транспорт |
| POST | `/api/orders` | Создать заказ |
| GET | `/api/orders/feed` | Лента заказов |
| GET | `/api/orders/map` | Заказы в радиусе (Haversine) |
| GET | `/api/orders/{id}` | Детали заказа |
| GET | `/api/orders/{id}/bids` | Ставки на заказ |
| POST | `/api/bids` | Откликнуться на заказ |
| POST | `/api/bids/respond` | Принять/отклонить ставку |
| POST | `/api/orders/{id}/complete` | Завершить заказ |
| POST | `/api/orders/{id}/rate` | Оценить водителя |
| GET | `/api/stats/promo` | Статистика промо-акции |
| GET | `/api/geocode` | Геокодирование адреса |
