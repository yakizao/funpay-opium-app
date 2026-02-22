# Opium — Полная документация проекта

> **Версия**: 2.0 — 2026-02-15
> **Назначение**: Единый справочник по архитектуре, компонентам и взаимосвязям.
> **Аудитория**: Разработчик (ты из будущего), AI-ассистент, новый контрибьютор.

---

## 1. Что такое Opium

Opium — платформа автоматизации FunPay-аккаунтов. Позволяет:
- Управлять несколькими FunPay-аккаунтами из одной админки
- Подключать **модули** для автоматизации (аренда Steam, автоответчик, и т.д.)
- Отслеживать заказы, чаты, баланс через веб-интерфейс
- Расширять функционал без изменения ядра

**Ключевой принцип**: модули — plug-and-play. Положил папку — всё заработало.

---

## 2. Стек технологий

| Слой | Технология | Версия |
|------|-----------|--------|
| Backend | Python + FastAPI + Uvicorn | 3.11+ |
| Frontend | React 19 + TypeScript + MUI v6 + Vite | — |
| Внешняя API | FunPayAPI (форк) | — |
| Reverse Proxy | Caddy | — |
| БД | Файловая (JSON per entity) | — |
| Auth | JWT (custom, без PyJWT) | — |

---

## 3. Структура проекта

```
opium/
├── main.py                  # Точка входа (uvicorn)
├── requirements.txt         # Python зависимости
├── Caddyfile               # Reverse proxy (prod)
├── start.bat / stop.bat    # Управление сервисом
│
├── core/                    # ══ ЯДРО (НЕ ТРОГАТЬ при разработке модулей) ══
│   ├── __init__.py          # Публичный API ядра (все экспорты)
│   ├── core.py              # OpiumCore — главный оркестратор
│   ├── runtime.py           # AccountRuntime — polling, команды, anti-detect
│   ├── event_bus.py         # EventBus — асинхронная шина событий
│   ├── commands.py          # Command, CommandType, CommandResult
│   ├── module.py            # Module ABC, реестр модулей, Subscription
│   ├── storage.py           # Storage, AccountStorage, ModuleStorage
│   ├── converters.py        # FunPay events → OpiumEvent + сериализаторы
│   ├── rate_limiter.py      # RateLimiter + AntiDetectConfig
│   └── logging.py           # setup_logging (консоль + файл + ротация)
│
├── FunPayAPI/               # ══ ФОРК ВНЕШНЕЙ БИБЛИОТЕКИ ══
│   ├── account.py           # Account — HTTP клиент FunPay
│   ├── updater/runner.py    # Runner — long-polling событий
│   ├── updater/events.py    # Типы событий FunPay
│   ├── types.py             # ChatShortcut, OrderShortcut, etc.
│   └── common/              # enums, exceptions, utils
│
├── api/                     # ══ REST API ══
│   ├── main.py              # FastAPI app, lifespan, роуты, RequestLoggingMiddleware
│   ├── deps.py              # DI: get_core(), get_module()
│   ├── serializers.py       # Сериализация для фронтенда
│   └── static/              # Собранный frontend (npm run build)
│
├── security/                # ══ БЕЗОПАСНОСТЬ ══
│   ├── auth.py              # JWT, PBKDF2-SHA256, TokenData
│   ├── middleware.py         # Auth, RateLimit, IPWhitelist, SecureHeaders
│   ├── endpoints.py         # /auth/login, /auth/me, /auth/refresh
│   ├── brute_force.py       # BruteForceProtector
│   ├── config.py            # SecurityConfig (из .env + security.json)
│   ├── setup.py             # setup_security(app) — точка интеграции
│   ├── rate_limit.py        # Token Bucket per IP
│   └── security_log.py      # Security audit log (JSON lines)
│
├── modules/                 # ══ МОДУЛИ (РАСШИРЕНИЯ) ══
│   ├── __init__.py          # Auto-discovery через pkgutil
│   ├── steam_rent/          # Модуль аренды Steam-аккаунтов
│   │   ├── __init__.py      # @register_module_class + экспорты
│   │   ├── module.py        # SteamRentModule (наследник Module)
│   │   ├── handlers.py      # Бизнес-логика обработки событий
│   │   ├── storage.py       # SteamRentStorage (обёртка над ModuleStorage)
│   │   ├── models/          # Dataclass-модели (rental.py, proxy.py)
│   │   ├── steam/           # Steam API клиент (http, guard, session, operations)
│   │   ├── proxy.py         # ProxyManager (singleton)
│   │   ├── scheduler.py     # RentalScheduler (фоновые задачи)
│   │   ├── messages.py      # Шаблоны сообщений (конфигурируемые)
│   │   ├── migrate.py       # Миграции данных
│   │   └── api_router.py    # REST API роутер модуля (37 эндпоинтов)
│   │
│   ├── telegram_bot/        # Telegram-бот (уведомления + удалённое управление)
│   │   ├── __init__.py
│   │   ├── module.py        # TelegramBotModule — обработка событий, команды, кнопки
│   │   ├── bot.py           # TelegramBot — async aiohttp клиент, long polling
│   │   ├── formatters.py    # Форматирование OpiumEvent → Telegram HTML
│   │   ├── log_handler.py   # TelegramLogHandler — перехват логов → бот
│   │   ├── storage.py       # TelegramBotStorage (whitelist, log watchers, кнопки)
│   │   └── api_router.py    # REST API роутер (19 эндпоинтов)
│   │
│   └── auto_raise/          # Автоподнятие лотов по cooldown
│       ├── __init__.py
│       ├── module.py        # AutoRaiseModule — scheduler, категории, raise loop
│       ├── storage.py       # AutoRaiseStorage (конфиг, лог)
│       └── api_router.py    # REST API роутер (6 эндпоинтов)
│
├── frontend/                # ══ ФРОНТЕНД ══
│   ├── src/
│   │   ├── App.tsx          # Роутинг + auth guard
│   │   ├── main.tsx         # Точка входа (AuthProvider)
│   │   ├── theme.ts         # MUI тема (тёмная)
│   │   ├── api/client.ts    # Axios + типы + interceptors
│   │   ├── auth/            # AuthContext, useAuth
│   │   ├── components/      # Layout, GlowCard, PageHeader, TablePaper
│   │   ├── hooks/           # useAccountActions, useCountdown, usePolling
│   │   ├── pages/           # Dashboard, Accounts, Chats, Orders, Login
│   │   └── modules/         # Фронтенд модулей (auto-discovery)
│   │       ├── index.ts     # ModuleManifest, getModuleManifests()
│   │       ├── steam_rent/  # UI модуля Steam Rent
│   │       ├── telegram_bot/ # UI модуля Telegram Bot
│   │       └── auto_raise/  # UI модуля Auto Raise
│   └── vite.config.ts       # Vite (proxy → localhost:8000)
│
├── accounts/                # ══ ДАННЫЕ (runtime, git-ignored) ══
│   └── {account_id}/
│       ├── account.json     # Конфиг аккаунта
│       └── modules/
│           └── {module_name}/
│               ├── config.json
│               └── ...      # Данные модуля
│
├── logs/                    # Логи (auto-rotated, 30 дней)
└── docs/                    # Документация
```

---

## 4. Архитектура (поток данных)

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + MUI v6)                                   │
│  http://localhost:3000                                           │
│  ├── pages/: Dashboard, Accounts, Chats, Orders                 │
│  └── modules/steam_rent/: Dashboard, Games, Rentals, ...        │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP (axios)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  REST API (FastAPI)                                              │
│  http://localhost:8000                                           │
│  ├── api/main.py: Core endpoints (accounts, chats, orders)      │
│  ├── modules/*/api_router.py: Module-specific endpoints          │
│  └── security/: Auth, Rate Limit, IP Whitelist                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Python imports
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  OpiumCore                                                       │
│                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐       │
│  │ EventBus │───▶│ Module       │───▶│ Commands          │       │
│  │          │    │ .handle_     │    │ (send_message,    │       │
│  │ fan-out  │    │  event()     │    │  refund, etc.)    │       │
│  └────▲─────┘    └──────────────┘    └────────┬─────────┘       │
│       │                                        │                  │
│  ┌────┴──────────────────────────────────────┐ │                  │
│  │ AccountRuntime                             │ │                  │
│  │ ├── FunPayAPI Account (HTTP client)        │◀┘                 │
│  │ ├── FunPayAPI Runner (long-polling)        │                   │
│  │ ├── Rate Limiter + Anti-Detect             │                   │
│  │ └── State Machine (created→running→stopped)│                   │
│  └────────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### Жизненный цикл события

```
1. FunPay сервер отдаёт данные через long-polling
2. Runner парсит HTML ответ → FunPayAPI Event (NewMessageEvent, NewOrderEvent, ...)
3. AccountRuntime конвертирует → OpiumEvent (через core/converters.py)
4. EventBus fan-out → Module.handle_event(event)
5. Module анализирует, возвращает list[Command]
6. Core.execute() → AccountRuntime.execute() → FunPayAPI Account.method()
7. Результат → CommandResult (ok/fail)
```

---

## 5. Логирование

Система имеет **сквозное логирование всех действий** — от входящего HTTP-запроса до выполнения команды на FunPay.

### 5.1. Настройка (`core/logging.py`)

```python
from core.logging import setup_logging
setup_logging()  # console=DEBUG, file=DEBUG, rotation=daily, 30 days
```

| Параметр | Значение |
|----------|---------|
| Иерархия | `opium.*` (все компоненты) |
| Формат | `%(asctime)s \| %(levelname)-8s \| %(name)s \| %(message)s` |
| Консоль | DEBUG |
| Файл | `logs/opium_YYYY-MM-DD.log`, daily rotation, 30 дней |
| Шумные библиотеки | urllib3, httpx, asyncio → WARNING |

### 5.2. Иерархия логгеров

| Logger | Что логирует |
|--------|-------------|
| `opium.core` | Регистрация аккаунтов, загрузка модулей, маршрутизация команд, подписки |
| `opium.runtime` | Выполнение команд (тип + params), dispatch решения, send_message, runner loop, initialize, session refresh |
| `opium.event_bus` | subscribe/unsubscribe/publish, количество matched handlers |
| `opium.converters` | Каждая конвертация FunPayAPI event → OpiumEvent с payload деталями |
| `opium.api` | Каждый HTTP запрос: `METHOD /path → status (Xms)` |
| `opium.steam_rent.*` | handle_event routing, обработка сообщений, парсинг команд, рефанды |
| `opium.telegram_bot.*` | Broadcast, bot commands, callback queries, send/poll, log handler |
| `opium.auto_raise` | Raise loop тики, циклы по категориям, ручной raise_now |

### 5.3. RequestLoggingMiddleware (`api/main.py`)

Логирует **каждый** HTTP-запрос к API:
```
2026-02-15 12:00:01 | INFO     | opium.api | GET /api/accounts → 200 (12ms)
2026-02-15 12:00:02 | INFO     | opium.api | POST /api/accounts/{account_id}/start → 202 (3ms)
```

### 5.4. TelegramLogHandler (`modules/telegram_bot/log_handler.py`)

Перехватывает логи `opium.*` (кроме `opium.telegram_bot.*` для избежания рекурсии) и пересылает в Telegram по настроенным log watchers:
- Каждый watcher фильтрует по regex-паттерну на имя логгера
- Минимальный уровень: по watcher'у (INFO/WARNING/ERROR)

### 5.5. Что логируется (покрытие)

| Точка | Уровень | Пример |
|-------|---------|--------|
| HTTP запрос | INFO | `GET /api/status → 200 (5ms)` |
| EventBus.publish | DEBUG | `Publishing new_order for account {account_id}` |
| EventBus match | DEBUG | `2 handler(s) matched: steam_rent_handler, telegram_bot_handler` |
| Event conversion | INFO | `new_message: chat=12345 author=Ivan text='Привет! ...'` |
| Module handle_event | DEBUG | `Event new_order received → 2 commands (send_message, send_message)` |
| Command routing | DEBUG | `Routing command send_message to runtime` |
| Command execution | INFO | `Executing send_message: chat_id=12345` |
| Command result | INFO/ERROR | `Command send_message executed by steam_rent: OK` |
| Own-message skip | DEBUG | `Skipping own message in chat 12345` |
| Broadcast | INFO | `Broadcast new_order: 2/2 delivered` |
| Raise cycle | INFO | `Raise cycle: 3 categories (CS2, DOTA2, Rust)` |

---

## 6. Ключевые компоненты ядра

### 6.1. OpiumCore (`core/core.py`)

Оркестратор. Управляет аккаунтами, модулями, маршрутизацией событий и команд.

```python
core = OpiumCore(base_path=".")

# Жизненный цикл
await core.load_accounts(auto_start=True)  # Non-blocking
await core.start()                          # EventBus + Runtimes
await core.stop()                           # Graceful shutdown

# Аккаунты
runtime = core.get_runtime("shop_1")
modules = core.get_account_modules("shop_1")

# Команды
result = await core.execute("shop_1", Command("send_message", {"chat_id": 123, "text": "Hi"}))
```

### 6.2. AccountRuntime (`core/runtime.py`)

Изолированный runtime одного FunPay-аккаунта. Содержит:
- FunPayAPI Account + Runner
- Rate Limiter (задержки между операциями)
- Anti-Detect (случайные задержки при старте/стопе)
- State Machine: `CREATED → INITIALIZING → READY → STARTING → RUNNING → STOPPING → STOPPED → ERROR`
- Reconnect с exponential backoff + circuit breaker (max 50 retries)

### 6.3. EventBus (`core/event_bus.py`)

Асинхронная шина событий с fan-out и фильтрацией.

```python
# Подписка с фильтрами
sub_id = event_bus.subscribe(
    handler=my_handler,
    event_types=["new_order", "new_message"],  # None = все
    account_ids=["shop_1"],                     # None = все
)
```

### 6.4. Система команд (`core/commands.py`)

```python
# Создание команды
cmd = Command(command_type="send_message", params={"chat_id": 123, "text": "Hello"})
cmd = Command(command_type=CommandType.REFUND, params={"order_id": "ABC123"})

# Результат
result = await core.execute(account_id, cmd)
if result.success:
    data = result.data
else:
    error = result.error
```

**Доступные CommandType:**
| Тип | Параметры |
|-----|----------|
| `send_message` | `chat_id: int, text: str` |
| `send_image` | `chat_id: int, image: bytes/file` |
| `get_chat_history` | `chat_id: int` |
| `get_order` | `order_id: str` |
| `get_sells` | `include_paid, include_closed, include_refunded` |
| `refund` | `order_id: str` |
| `send_review` | `order_id, text, rating` |
| `get_balance` | — |
| `raise_lots` | `category_ids, wait` |
| `get_lot_fields` | `offer_id` |
| `save_lot` | `offer_id, fields` |

### 6.5. Module ABC (`core/module.py`)

Базовый класс для всех модулей. **Подробнее → [MODULE_GUIDE.md](MODULE_GUIDE.md)**

### 6.6. Storage (`core/storage.py`)

Файловое хранилище. Три уровня:
- **Storage** — корневой (`./accounts/`)
- **AccountStorage** — аккаунт (`./accounts/{id}/`)
- **ModuleStorage** — модуль (`./accounts/{id}/modules/{name}/`)

ModuleStorage API:
```python
storage.config                     # dict (cached, from config.json)
storage.get(key, default)          # get from config
storage.save_config(dict)          # write config.json
storage.update_config(**kwargs)    # merge into config
storage.read_json("file.json")    # read any JSON
storage.write_json("file.json", data)  # write any JSON
storage.get_file_path("file.txt") # Path object
storage.file_exists("file.txt")   # bool
storage.get_db_path("data")       # Path to SQLite DB
```

---

## 7. REST API

**Base URL**: `http://localhost:8000/api`

### 7.1. Core endpoints (`api/main.py`)

| Method | URL | Описание |
|--------|-----|----------|
| GET | `/accounts` | Список аккаунтов |
| POST | `/accounts` | Создать аккаунт (→ 202) |
| GET | `/accounts/{id}` | Детали аккаунта |
| DELETE | `/accounts/{id}` | Удалить аккаунт |
| GET | `/accounts/{id}/config` | Конфиг аккаунта |
| PATCH | `/accounts/{id}/config` | Обновить конфиг |
| POST | `/accounts/{id}/start` | Запустить (→ 202) |
| POST | `/accounts/{id}/stop` | Остановить (→ 202) |
| GET | `/accounts/{id}/modules` | Модули аккаунта |
| POST | `/accounts/{id}/modules` | Добавить модуль |
| GET | `/accounts/{id}/modules/{name}` | Конфиг модуля |
| PUT | `/accounts/{id}/modules/{name}` | Обновить конфиг модуля |
| GET | `/accounts/{id}/chats` | Список чатов |
| GET | `/accounts/{id}/chats/{chat_id}/history` | История чата |
| POST | `/accounts/{id}/chats/{chat_id}/send` | Отправить сообщение (body: `{"text": "..."}`) |
| GET | `/accounts/{id}/orders` | Заказы |
| GET | `/accounts/{id}/orders/{order_id}` | Детали заказа |
| POST | `/accounts/{id}/orders/{order_id}/refund` | Возврат |
| GET | `/accounts/{id}/order-tags` | Теги заказов от модулей |
| GET | `/accounts/{id}/balance` | Баланс |
| GET | `/status` | Статус системы |
| GET | `/modules/available` | Доступные модули |

### 7.2. Auth endpoints (`security/endpoints.py`)

| Method | URL | Описание |
|--------|-----|----------|
| POST | `/auth/login` | Логин (→ JWT) |
| GET | `/auth/me` | Текущий пользователь |
| POST | `/auth/refresh` | Обновить токен |
| GET | `/auth/config` | Настройки auth (public) |
| GET | `/health` | Health check (public) |

### 7.3. Module endpoints подключаются автоматически

Каждый `modules/*/api_router.py` с объектом `router` монтируется в FastAPI app при старте.

Текущие модульные роутеры:

| Модуль | Base prefix | Эндпоинты |
|--------|-------------|------------|
| `steam_rent` | `/api/accounts/{id}/modules/steam_rent` | 37 |
| `telegram_bot` | `/api/accounts/{id}/modules/telegram_bot` | 19 |
| `auto_raise` | `/api/accounts/{id}/modules/auto_raise` | 6 |

---

## 8. Frontend

### Технологии
- React 19, TypeScript strict, MUI v6, react-router-dom
- Сборка: Vite (dev: `localhost:3000`, proxy → `localhost:8000`)
- Auth: JWT token в localStorage (`opium_token`), axios interceptors

### Модульная система фронтенда
- `frontend/src/modules/index.ts` — auto-discovery через `import.meta.glob('./*/index.tsx')`
- Каждый модуль экспортирует `ModuleManifest` (name, navigation, routes)
- `App.tsx` рендерит роуты из всех манифестов автоматически
- Текущие модули: steam_rent (7 страниц), telegram_bot (2 страницы), auto_raise (1 страница)

### Общие компоненты
- `Layout` — sidebar + content с drawer
- `PageHeader` — заголовок страницы + refresh + actions
- `TablePaper` — тёмная обёртка для таблиц
- `GlowCard` — карточка с glow-эффектом
- `AccountDialogs` — диалоги создания/настройки аккаунта

---

## 9. Безопасность

| Механизм | Реализация |
|----------|-----------|
| Auth | JWT (HS256, HMAC-SHA256), token в Bearer header |
| Пароль | PBKDF2-SHA256, 600K итераций, 32-byte salt |
| Rate limit | Token Bucket: 60 req/min общий, 5/min login |
| Brute force | 10 неудач → бан IP на 30 минут |
| IP whitelist | Опциональный, CIDR notation |
| Headers | HSTS, X-Frame-Options, CSP, X-Content-Type-Options |
| CORS | Настраивается через `OPIUM_CORS_ORIGINS` |
| Конфигурация | `.env` + `security.json` |

---

## 10. Запуск

```bash
# Установка
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# Запуск
python main.py              # Backend на :8000
# ИЛИ
start.bat                   # Backend :8000 + Frontend dev :3000

# Остановка
stop.bat
```

### Переменные окружения (.env)

```env
OPIUM_AUTH_ENABLED=true
OPIUM_SECRET_KEY=your-secret-key-here
OPIUM_ADMIN_USERNAME=admin
OPIUM_ADMIN_PASSWORD=your-password
OPIUM_CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

---

## 11. Auto-discovery (zero-config)

| Что | Механизм | Где |
|-----|---------|-----|
| Python-модули | `pkgutil.iter_modules` в `modules/__init__.py` | При старте Python |
| `@register_module_class` | Декоратор в `__init__.py` модуля | При импорте |
| API роутеры | `pkgutil.iter_modules` в `api/main.py` | При старте FastAPI |
| Frontend модули | `import.meta.glob('./*/index.tsx')` | При сборке Vite |
| Данные модулей | Сканирование `accounts/*/modules/*/config.json` | `load_accounts()` |

**Добавить новый модуль** = положить папки в `modules/` и `frontend/src/modules/`. Всё.

---

*Следующие документы: [MODULE_GUIDE.md](MODULE_GUIDE.md) — как написать свой модуль*
