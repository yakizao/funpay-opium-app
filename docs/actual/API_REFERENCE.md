# Opium — API Reference

> **Версия**: 2.0 — 2026-02-15
> **Base URL**: `http://localhost:8000/api`
> **Auth**: `Authorization: Bearer <JWT>` (все эндпоинты кроме отмеченных как public)

---

## Аутентификация

Все запросы к API (кроме `/health`, `/auth/login`, `/auth/config`) требуют JWT токен в заголовке:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

Получить токен: `POST /api/auth/login`

---

## 1. Auth (`/api/auth`)

### POST `/api/auth/login` (public)

Получение JWT токена.

**Request:**
```json
{ "username": "admin", "password": "your_password" }
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "username": "admin"
}
```

**Errors:** `401` — Invalid credentials, `429` — Too many attempts (brute force ban)

---

### GET `/api/auth/me`

Текущий пользователь.

**Response (200):**
```json
{ "username": "admin", "issued_at": 1705312000, "expires_at": 1705315600 }
```

---

### POST `/api/auth/refresh`

Обновить JWT (требует действующий токен).

**Response (200):**
```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600 }
```

---

### GET `/api/auth/config` (public)

Security конфигурация (без секретов).

**Response (200):**
```json
{ "auth_enabled": true }
```

---

## 2. System

### GET `/api/status`

Статус системы.

**Response (200):**
```json
{ "running": true, "accounts": 2, "modules": 3 }
```

---

### GET `/api/health` (public)

Health check.

**Response (200):**
```json
{ "status": "ok", "timestamp": 1705312000.123 }
```

---

### GET `/api/modules/available`

Список зарегистрированных модулей (все `@register_module_class`).

**Response (200):**
```json
{ "modules": ["steam_rent", "auto_delivery"] }
```

---

## 3. Accounts (`/api/accounts`)

### GET `/api/accounts`

Список всех аккаунтов.

**Response (200):** `AccountInfo[]`
```json
[
  {
    "account_id": "{account_id}",
    "username": "{account_id}",
    "fp_id": 12345,
    "state": "running",
    "is_running": true,
    "last_error": null,
    "modules": ["steam_rent"]
  }
]
```

---

### POST `/api/accounts` → `202`

Создать аккаунт. Инициализация в фоне.

**Request:**
```json
{
  "account_id": "my_shop",
  "golden_key": "abc123...",
  "user_agent": "Mozilla/5.0...",
  "proxy": null,
  "anti_detect": null,
  "rate_limit": null,
  "disable_messages": false,
  "disable_orders": false
}
```

**Response (202):**
```json
{
  "status": "initializing",
  "account_id": "my_shop",
  "state": "initializing",
  "message": "Account registered. Initializing in background. Poll GET /api/accounts/{id} for status."
}
```

---

### GET `/api/accounts/{account_id}`

Детали аккаунта.

**Response (200):** `AccountInfo`

**Errors:** `404` — Account not found

---

### DELETE `/api/accounts/{account_id}`

Удалить аккаунт (disable + stop).

**Response (200):**
```json
{ "status": "deleted", "account_id": "my_shop" }
```

---

### GET `/api/accounts/{account_id}/config`

Конфигурация аккаунта.

**Response (200):**
```json
{
  "golden_key": "abc123...",
  "user_agent": "Mozilla/5.0...",
  "proxy": null,
  "anti_detect": null,
  "rate_limit": null,
  "reconnect": null,
  "disable_messages": false,
  "disable_orders": false
}
```

---

### PATCH `/api/accounts/{account_id}/config`

Обновить конфигурацию (partial update).

**Request:** Любые поля из конфига:
```json
{ "proxy": {"http": "socks5://..."}, "disable_messages": true }
```

**Response (200):** Полный конфиг после обновления.

---

### POST `/api/accounts/{account_id}/start` → `202`

Запустить аккаунт. Non-blocking.

**Response (202):**
```json
{ "status": "starting", "account_id": "{account_id}", "state": "starting" }
```

---

### POST `/api/accounts/{account_id}/stop` → `202`

Остановить аккаунт. Non-blocking.

**Response (202):**
```json
{ "status": "stopping", "account_id": "{account_id}", "state": "stopping" }
```

---

## 4. Modules (`/api/accounts/{account_id}/modules`)

### GET `/api/accounts/{account_id}/modules`

Список модулей аккаунта.

**Response (200):**
```json
[
  { "name": "steam_rent", "config": { "change_password_on_rent": true } }
]
```

---

### POST `/api/accounts/{account_id}/modules`

Добавить модуль к аккаунту.

**Request:**
```json
{ "module_name": "steam_rent", "config": null }
```

**Response (200):**
```json
{ "status": "added", "module": "steam_rent", "account_id": "{account_id}" }
```

---

### GET `/api/accounts/{account_id}/modules/{module_name}`

Конфиг модуля.

**Response (200):**
```json
{
  "name": "steam_rent",
  "config": { "change_password_on_rent": true, "kick_devices_on_rent": true },
  "storage_path": "accounts/{account_id}/modules/steam_rent"
}
```

---

### PUT `/api/accounts/{account_id}/modules/{module_name}`

Обновить конфиг модуля (full replace).

**Request:**
```json
{ "config": { "change_password_on_rent": false } }
```

**Response (200):**
```json
{ "status": "updated", "module": "steam_rent", "config": {...} }
```

---

## 5. Chats (`/api/accounts/{account_id}/chats`)

### GET `/api/accounts/{account_id}/chats`

Список чатов.

**Query params:**
- `update` (bool, default `true`) — запросить актуальные данные с FunPay

**Response (200):**
```json
{
  "chats": [
    {
      "chat_id": 12345,
      "name": "Покупатель",
      "last_message": "Здравствуйте!",
      "unread": true,
      "media_url": null
    }
  ],
  "total": 1
}
```

---

### GET `/api/accounts/{account_id}/chats/{chat_id}`

Детали чата + сообщения.

**Response (200):**
```json
{
  "id": 12345,
  "name": "Покупатель",
  "messages": [
    {
      "id": 111,
      "text": "Привет!",
      "html": "Привет!",
      "author": "Покупатель",
      "author_id": 12345,
      "is_my": false,
      "image_url": null
    }
  ]
}
```

---

### GET `/api/accounts/{account_id}/chats/{chat_id}/history`

История сообщений.

**Query params:**
- `last_message_id` (int, default `99999999999999`) — для пагинации

**Response (200):**
```json
{
  "chat_id": 12345,
  "messages": [...],
  "count": 50
}
```

---

### POST `/api/accounts/{account_id}/chats/{chat_id}/send`

Отправить сообщение.

**Request:**
```json
{ "text": "Здравствуйте! Чем могу помочь?" }
```

**Response (200):**
```json
{ "status": "sent", "chat_id": 12345 }
```

---

## 6. Orders (`/api/accounts/{account_id}/orders`)

### GET `/api/accounts/{account_id}/orders`

Список заказов (продаж).

**Query params:**
- `include_paid` (bool, default `true`)
- `include_closed` (bool, default `true`)
- `include_refunded` (bool, default `true`)

**Response (200):**
```json
{
  "orders": [
    {
      "order_id": "ABC12345",
      "description": "CS2 аренда Steam аккаунта 12 часов",
      "price": "150.0",
      "buyer": "Покупатель",
      "buyer_id": 12345,
      "status": "paid",
      "date": "2024-01-15 12:00:00"
    }
  ],
  "total": 88,
  "next_order_id": "XYZ99999"
}
```

---

### GET `/api/accounts/{account_id}/order-tags`

Теги заказов от всех модулей (для фильтрации на фронте).

**Response (200):**
```json
{
  "tags": {
    "ABC123": { "module": "steam_rent", "game_id": "cs2", "game_name": "CS2" },
    "DEF456": { "module": "auto_delivery", "product_id": "p_001" }
  },
  "modules": ["steam_rent", "auto_delivery"],
  "games": {
    "steam_rent": [
      { "game_id": "cs2", "game_name": "CS2" },
      { "game_id": "dayz", "game_name": "dayz" }
    ]
  }
}
```

---

### GET `/api/accounts/{account_id}/orders/{order_id}`

Детали заказа.

**Response (200):**
```json
{
  "order_id": "ABC12345",
  "status": "paid",
  "description": "CS2 аренда Steam аккаунта 12 часов",
  "price": "150.0",
  "buyer": "Покупатель",
  "buyer_id": 12345,
  "review": null,
  "chat_id": 67890,
  "date": "2024-01-15 12:00:00"
}
```

---

### POST `/api/accounts/{account_id}/orders/{order_id}/refund`

Возврат средств.

**Response (200):**
```json
{ "status": "refunded", "order_id": "ABC12345" }
```

---

## 7. Balance

### GET `/api/accounts/{account_id}/balance`

Баланс аккаунта.

**Response (200):**
```json
{
  "total_rub": 5000.0,
  "available_rub": 4500.0,
  "total_usd": 0.0,
  "available_usd": 0.0,
  "total_eur": 0.0,
  "available_eur": 0.0
}
```

---

## 8. Module-specific endpoints

Модули подключают свои роутеры автоматически. Формат:
```
/api/accounts/{account_id}/modules/{module_name}/...
```

### 8.1. Steam Rent

| Method | URL | Описание |
|--------|-----|----------|
| GET | `.../steam_rent/overview` | Обзор модуля |
| GET | `.../steam_rent/games` | Список игр |
| POST | `.../steam_rent/games` | Добавить игру |
| GET | `.../steam_rent/steam-accounts` | Steam аккаунты |
| POST | `.../steam_rent/steam-accounts` | Добавить аккаунт |
| GET | `.../steam_rent/lot-mappings` | Привязки лотов |
| POST | `.../steam_rent/lot-mappings` | Создать привязку |
| GET | `.../steam_rent/rentals` | Список аренд |
| GET | `.../steam_rent/proxies` | Прокси |
| GET | `.../steam_rent/messages` | Шаблоны сообщений |
| PUT | `.../steam_rent/config` | Обновить конфиг |

### 8.2. Telegram Bot

| Method | URL | Описание |
|--------|-----|----------|
| GET | `.../telegram_bot/config` | Конфиг бота |
| PATCH | `.../telegram_bot/config` | Обновить конфиг (токен, notify_events) |
| GET | `.../telegram_bot/whitelist` | Список вайтлиста |
| POST | `.../telegram_bot/whitelist` | Добавить пользователя |
| PATCH | `.../telegram_bot/whitelist/{telegram_id}` | Обновить пользователя |
| DELETE | `.../telegram_bot/whitelist/{telegram_id}` | Удалить из вайтлиста |
| GET | `.../telegram_bot/events` | Лог событий |
| DELETE | `.../telegram_bot/events` | Очистить лог событий |
| GET | `.../telegram_bot/bot-info` | Информация о боте |
| POST | `.../telegram_bot/restart` | Перезапустить бота |
| POST | `.../telegram_bot/test` | Отправить тестовое сообщение |
| GET | `.../telegram_bot/log-watchers` | Список log watchers |
| POST | `.../telegram_bot/log-watchers` | Создать log watcher |
| PATCH | `.../telegram_bot/log-watchers/{watcher_id}` | Обновить watcher |
| DELETE | `.../telegram_bot/log-watchers/{watcher_id}` | Удалить watcher |
| GET | `.../telegram_bot/bot-buttons` | Список inline-кнопок |
| POST | `.../telegram_bot/bot-buttons` | Создать кнопку |
| PATCH | `.../telegram_bot/bot-buttons/{button_id}` | Обновить кнопку |
| DELETE | `.../telegram_bot/bot-buttons/{button_id}` | Удалить кнопку |

### 8.3. Auto Raise

| Method | URL | Описание |
|--------|-----|----------|
| GET | `.../auto_raise/config` | Конфиг модуля (enabled, delay_range) |
| PATCH | `.../auto_raise/config` | Обновить конфиг |
| GET | `.../auto_raise/status` | Статус (активен, категории, следующий raise) |
| POST | `.../auto_raise/raise` | Ручной запуск поднятия |
| GET | `.../auto_raise/log` | Лог поднятий |
| DELETE | `.../auto_raise/log` | Очистить лог |

---

## 9. Request Logging

Все HTTP-запросы логируются через `RequestLoggingMiddleware` (`api/main.py`):

```
2026-02-15 12:00:01 | INFO     | opium.api | GET /api/accounts → 200 (12ms)
2026-02-15 12:00:02 | INFO     | opium.api | POST /api/accounts/{account_id}/start → 202 (3ms)
```

Логируется: method, path, status code, response time (ms).

---

## HTTP Status Codes

| Код | Значение |
|-----|---------|
| `200` | Успех |
| `202` | Accepted (операция запущена в фоне: start, stop, create) |
| `400` | Bad request (невалидные данные, аккаунт не инициализирован) |
| `401` | Unauthorized (нет/невалидный токен) |
| `404` | Not found (аккаунт, модуль) |
| `429` | Rate limit / brute force ban |
| `500` | Internal error |
| `503` | Core not initialized (startup) |

---

## Rate Limiting

- **Общий лимит**: 60 requests/min per IP
- **Login**: 5 requests/min per IP
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
