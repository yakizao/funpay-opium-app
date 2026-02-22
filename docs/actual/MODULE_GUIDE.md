# Opium — Полный гайд по написанию модуля

> **Версия**: 3.0 — 2026-02-15
> **Назначение**: Создать полностью совместимый plug-and-play модуль для Opium.
> **Аудитория**: Разработчик, AI-модель.

---

## Содержание

1. [Архитектура модуля](#1-архитектура-модуля)
2. [Быстрый старт — минимальный модуль](#2-быстрый-старт--минимальный-модуль)
3. [Backend: Module ABC (полный контракт)](#3-backend-module-abc-полный-контракт)
4. [Backend: Storage (хранилище данных)](#4-backend-storage-хранилище-данных)
5. [Backend: Events (входящие события)](#5-backend-events-входящие-события)
6. [Backend: Commands (исходящие команды)](#6-backend-commands-исходящие-команды)
7. [Backend: API Router (REST API модуля)](#7-backend-api-router-rest-api-модуля)
8. [Frontend: ModuleManifest (навигация и роуты)](#8-frontend-modulemanifest-навигация-и-роуты)
9. [Frontend: Страницы и компоненты](#9-frontend-страницы-и-компоненты)
10. [Frontend: API клиент модуля](#10-frontend-api-клиент-модуля)
11. [Order Tags — интеграция в страницу заказов](#11-order-tags--интеграция-в-страницу-заказов)
12. [Данные на диске](#12-данные-на-диске)
13. [Паттерн: модуль обработки заказов (lot mapping)](#13-паттерн-модуль-обработки-заказов-lot-mapping)
14. [Логирование в модулях](#14-логирование-в-модулях)
15. [Чеклист: готов ли модуль?](#15-чеклист-готов-ли-модуль)
16. [Полный пример: auto_delivery](#16-полный-пример-auto_delivery)

---

## 1. Архитектура модуля

Модуль Opium состоит из **3 слоёв**, каждый из которых автоматически обнаруживается при старте:

```
модуль (пример: "my_module")
├── Backend:   modules/my_module/        ← Python, обработка событий
├── REST API:  modules/my_module/api_router.py  ← FastAPI эндпоинты
└── Frontend:  frontend/src/modules/my_module/  ← React UI
```

### Auto-discovery (zero-config)

| Слой | Механизм | Файл-триггер |
|------|---------|-------------|
| Python-класс модуля | `pkgutil.iter_modules` → `@register_module_class` | `modules/my_module/__init__.py` |
| REST API роутер | `pkgutil.iter_modules` → `router` объект | `modules/my_module/api_router.py` |
| Frontend UI | `import.meta.glob('./*/index.tsx')` | `frontend/src/modules/my_module/index.tsx` |

**Добавить модуль = положить файлы → перезапустить. Никаких ручных регистраций.**

---

## 2. Быстрый старт — минимальный модуль

### Шаг 1: Backend (2 файла)

**`modules/my_module/__init__.py`**
```python
"""My Module — автоматически обнаруживается при старте."""
from .module import MyModule  # noqa: F401
```

**`modules/my_module/module.py`**
```python
from __future__ import annotations
from typing import Any, ClassVar
from core.module import Module, register_module_class, Subscription
from core.commands import Command
from core.event_bus import OpiumEvent


@register_module_class
class MyModule(Module):
    module_name: ClassVar[str] = "my_module"

    def get_subscriptions(self) -> list[Subscription]:
        return [Subscription(event_types=["new_message"])]

    async def handle_event(self, event: OpiumEvent) -> list[Command]:
        # Пока ничего не делаем
        return []
```

### Шаг 2: Подключить к аккаунту

В `accounts/{account_id}/modules/` создать папку `my_module/` (или через API):
```
POST /api/accounts/{account_id}/modules
Body: {"module_name": "my_module"}
```

### Шаг 3: Перезапустить Opium

Модуль загрузится автоматически. Проверить:
```
GET /api/accounts/{account_id}/modules → {"modules": ["my_module", ...]}
```

**Это уже рабочий модуль.** Дальше — подробности каждого слоя.

---

## 3. Backend: Module ABC (полный контракт)

Файл: `core/module.py` → класс `Module`

### 3.1. Обязательные элементы

```python
from core.module import Module, register_module_class, Subscription
from core.commands import Command
from core.event_bus import OpiumEvent
from core.storage import ModuleStorage
from typing import ClassVar, Any

@register_module_class
class MyModule(Module):
    # ═══ ОБЯЗАТЕЛЬНО ═══
    
    module_name: ClassVar[str] = "my_module"
    # Уникальное имя (snake_case). Используется как:
    # - имя папки в accounts/{id}/modules/{module_name}/
    # - имя в конфиге аккаунта
    # - идентификатор в API
    # - имя папки frontend/src/modules/{module_name}/
    
    def __init__(self, account_id: str, storage: ModuleStorage) -> None:
        super().__init__(account_id, storage)
        # self.account_id — ID аккаунта (str)
        # self.storage     — ModuleStorage (доступ к файлам)
        # self.config      — shortcut для self.storage.config (dict)
    
    async def handle_event(self, event: OpiumEvent) -> list[Command]:
        """АБСТРАКТНЫЙ — обязательно реализовать."""
        return []
```

### 3.2. Опциональные методы

```python
    def get_subscriptions(self) -> list[Subscription]:
        """
        Фильтр событий. По умолчанию — ВСЕ события.
        Для экономии ресурсов указывайте только нужные типы.
        """
        return [
            Subscription(event_types=["new_order", "new_message"]),
        ]
    
    async def on_start(self) -> None:
        """Вызывается при запуске аккаунта. Инициализация, фоновые задачи."""
        pass
    
    async def on_stop(self) -> None:
        """Вызывается при остановке. Очистка, сохранение состояния."""
        pass
    
    async def get_order_tags(
        self, orders: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Тегирование заказов для фронтенда (фильтрация на странице Orders).
        Подробнее → раздел 11.
        """
        return {}
```

### 3.3. Доступные property и shortcuts

```python
self.name            # str — module_name (read-only property)
self.account_id      # str — ID аккаунта
self.storage         # ModuleStorage — файловое хранилище
self.config          # dict — shortcut для self.storage.config
self.get_config(key, default)  # get(key, default) из config.json
```

### 3.4. Жизненный цикл

```
1. Core → import modules/ → @register_module_class  (класс зарегистрирован)
2. Core.load_accounts() → для каждого аккаунта с module_name в конфиге:
      module = MyModule(account_id, storage)        (инстанс создан)
3. Core.start() → module.on_start()                 (запуск)
4. FunPay event → module.handle_event(event)         (обработка, 0+ раз)
5. Core.stop() → module.on_stop()                    (остановка)
```

**ВАЖНО**: Один инстанс модуля = один аккаунт. Если 3 аккаунта используют `my_module`, будет 3 инстанса.

---

## 4. Backend: Storage (хранилище данных)

Файл: `core/storage.py` → класс `ModuleStorage`

Каждый инстанс модуля получает свой `ModuleStorage` с путём:
```
accounts/{account_id}/modules/{module_name}/
```

### 4.1. Полный API (ModuleStorage)

```python
# ═══ Конфигурация (config.json) ═══
storage.config                          # dict — конфиг (lazy load + cache)
storage.load_config()                   # Перезагрузить конфиг с диска
storage.save_config({"key": "value"})   # Полная перезапись config.json
storage.update_config(key="value")      # Merge в существующий конфиг
storage.get("key", "default")           # Получить значение из конфига

# ═══ Произвольные JSON файлы ═══
storage.read_json("games.json")         # dict | list | None
storage.write_json("games.json", data)  # Записать (indent=2, utf-8)
storage.file_exists("games.json")       # bool

# ═══ Пути ═══
storage.path                            # Path — папка модуля
storage.get_file_path("data.txt")       # Path — путь к файлу
storage.get_db_path("mydata")           # Path — путь к SQLite DB (mydata.db)
```

### 4.2. Рекомендуемый паттерн: типизированная обёртка

Для сложных модулей создайте обёртку над `ModuleStorage` (как `SteamRentStorage`):

```python
# modules/my_module/storage.py
from __future__ import annotations
from typing import TYPE_CHECKING
from .models import Game, game_from_dict, to_dict

if TYPE_CHECKING:
    from core.storage import ModuleStorage

GAMES_FILE = "games.json"

class MyModuleStorage:
    def __init__(self, module_storage: ModuleStorage) -> None:
        self._storage = module_storage
        self._cache_games: list[Game] | None = None
    
    def get_config(self) -> dict:
        return self._storage.config
    
    def get_games(self) -> list[Game]:
        if self._cache_games is None:
            data = self._storage.read_json(GAMES_FILE)
            self._cache_games = [game_from_dict(d) for d in (data or {}).get("games", [])]
        return self._cache_games
    
    def save_games(self, games: list[Game]) -> None:
        self._cache_games = games
        self._storage.write_json(GAMES_FILE, {"games": [to_dict(g) for g in games]})
    
    def invalidate_cache(self) -> None:
        self._cache_games = None
```

**Зачем**: типы, кэширование, изоляция, удобный API для handlers и api_router.

### 4.3. Модели: dataclass + factory functions

```python
# modules/my_module/models.py
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

class GameStatus(Enum):
    ACTIVE = "active"
    DISABLED = "disabled"

@dataclass
class Game:
    game_id: str
    name: str
    status: GameStatus = GameStatus.ACTIVE
    aliases: list[str] = field(default_factory=list)

def game_from_dict(d: dict[str, Any]) -> Game:
    return Game(
        game_id=d["game_id"],
        name=d.get("name", d["game_id"]),
        status=GameStatus(d.get("status", "active")),
        aliases=d.get("aliases", []),
    )

def to_dict(obj: Any) -> dict[str, Any]:
    """Dataclass → dict с Enum → str."""
    d = asdict(obj)
    _convert_enums(d)
    return d

def _convert_enums(obj: Any) -> Any:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, Enum):
                obj[k] = v.value
            elif isinstance(v, (dict, list)):
                _convert_enums(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, Enum):
                obj[i] = v.value
            elif isinstance(v, (dict, list)):
                _convert_enums(v)
```

---

## 5. Backend: Events (входящие события)

### 5.1. OpiumEvent

```python
@dataclass
class OpiumEvent:
    account_id: str          # ID аккаунта
    event_type: str          # Тип события (see table below)
    payload: dict[str, Any]  # Данные (зависит от типа)
    timestamp: float         # UNIX timestamp
    raw: Any = None          # Оригинальный FunPayAPI event
```

### 5.2. Типы событий

| event_type | Триггер | Payload |
|-----------|---------|---------|
| `new_message` | Новое сообщение в чат | `MessagePayload` |
| `new_order` | Новый заказ | `OrderPayload` |
| `order_status_changed` | Изменение статуса заказа | `OrderPayload` |
| `orders_list_changed` | Обновление списка заказов | `OrdersListPayload` |
| `initial_chat` | Чат загружен впервые | `ChatPayload` |
| `last_message_changed` | Последнее сообщение в чате обновилось | `ChatPayload` |
| `chats_list_changed` | Обновление списка чатов | `EmptyPayload` |
| `initial_order` | Заказ загружен впервые | `OrderPayload` |

### 5.3. Payload структуры

**MessagePayload** (event_type: `new_message`):
```python
{
    "message": {
        "id": 12345,           # int — ID сообщения
        "text": "Привет!",     # str | None — текст
        "chat_id": 67890,      # int — ID чата
        "chat_name": "Иван",   # str | None — имя чата
        "author": "Иван",      # str | None — автор
        "author_id": 1111,     # int — ID автора (0 = система)
        "type": 0,             # int — MessageTypes enum
        "image_link": None,    # str | None — URL картинки
        "by_bot": False,       # bool — наше сообщение?
        "badge": None,         # str | None
    },
    "chat_id": 67890,          # int — ID чата
    "stack": [...]             # list[MessageDict] — стэк сообщений
}
```

**OrderPayload** (event_type: `new_order`):
```python
{
    "order": {
        "id": "ABC12345",           # str — ID заказа
        "description": "CS2 аренда Steam аккаунта 12 часов",  # str
        "price": 150.0,             # float — цена
        "currency": "RUB",          # str | None
        "amount": 1,                # int — количество
        "buyer_username": "Иван",   # str
        "buyer_id": 1111,           # int
        "status": 0,                # int — OrderStatuses enum
        "date": "2024-01-15 12:00", # str | None
        "subcategory_name": None,   # str | None
    },
    "order_id": "ABC12345",         # str
}
```

**Типы MessageTypes (int)**:
- `0` — обычное текстовое
- `1` — изображение
- `3` — NEW_FEEDBACK (новый отзыв)
- `4` — FEEDBACK_CHANGED
- `5` — FEEDBACK_DELETED

### 5.4. Паттерн обработки

```python
async def handle_event(self, event: OpiumEvent) -> list[Command]:
    if event.event_type == "new_order":
        return self._handle_order(event)
    elif event.event_type == "new_message":
        return self._handle_message(event)
    return []

def _handle_order(self, event: OpiumEvent) -> list[Command]:
    order = event.payload.get("order", {})
    order_id = order.get("id", "")
    description = order.get("description", "")
    buyer_id = order.get("buyer_id", 0)
    buyer_name = order.get("buyer_username", "")
    
    # Бизнес-логика...
    
    return [
        Command("send_message", {
            "chat_id": buyer_id,
            "text": f"Спасибо за заказ #{order_id}!",
            "chat_name": buyer_name,  # имя чата для логов
        })
    ]
```

---

## 6. Backend: Commands (исходящие команды)

Модуль **не выполняет** действия сам. Он возвращает список `Command`, которые выполняет ядро.

### 6.1. Создание команд

```python
from core.commands import Command, CommandType

# Строкой (рекомендуется для простоты):
cmd = Command("send_message", {"chat_id": 12345, "text": "Hello!"})

# Через Enum (для IDE autocomplete):
cmd = Command(CommandType.SEND_MESSAGE, {"chat_id": 12345, "text": "Hello!"})
```

### 6.2. Доступные типы команд

| CommandType | Параметры | Описание |
|------------|-----------|----------|
| **Сообщения** | | |
| `send_message` | `chat_id: int, text: str, chat_name: str` | Отправить сообщение |
| `send_image` | `chat_id: int, image: bytes/path` | Отправить картинку |
| `upload_image` | `image: bytes/path` | Загрузить картинку (получить URL) |
| `get_chat_history` | `chat_id: int` | Получить историю чата |
| `get_chat` | `chat_id: int` | Получить объект чата |
| **Заказы** | | |
| `get_order` | `order_id: str` | Детали заказа |
| `get_sells` | `include_paid, include_closed, include_refunded` (все bool) | Получить продажи |
| `refund` | `order_id: str` | Возврат средств |
| **Отзывы** | | |
| `send_review` | `order_id: str, text: str, rating: int` | Оставить отзыв |
| `delete_review` | `order_id: str` | Удалить отзыв |
| **Лоты** | | |
| `get_lot_fields` | `offer_id: str` | Получить поля лота |
| `save_lot` | `offer_id: str, fields: dict` | Сохранить лот |
| `delete_lot` | `offer_id: str` | Удалить лот |
| `raise_lots` | `category_ids: list[int], wait: bool` | Поднять лоты |
| `get_subcategory_public_lots` | `subcategory_id: int` | Публичные лоты подкатегории |
| `get_trade_page_lots` | `trade_page_url: str` | Лоты со страницы торговли |
| **Аккаунт** | | |
| `get_balance` | (нет) | Получить баланс |
| `get_user` | `user_id: int` | Получить данные пользователя |
| `calculate` | `...` | Калькулятор цены |

### 6.3. Команды из on_start/on_stop

`handle_event` возвращает команды. Но `on_start`/`on_stop` — `void`. Для выполнения команд из них нужен callback:

```python
class MyModule(Module):
    def set_execute_command(self, fn):
        """Вызывается ядром после создания модуля (duck typing — достаточно наличия метода)."""
        self._execute = fn
    
    async def on_start(self):
        if self._execute:
            result = await self._execute(Command("get_balance", {}))
            if result.success:
                balance = result.data
```

Ядро проверяет `hasattr(module, 'set_execute_command')` и вызывает его автоматически. Метод не нужно объявлять в ABC — это opt-in duck typing.

### 6.4. CommandResult

```python
@dataclass
class CommandResult:
    success: bool
    data: Any = None
    error: str | None = None
    
    @classmethod
    def ok(cls, data=None): ...
    
    @classmethod
    def fail(cls, error: str): ...
```

---

## 7. Backend: API Router (REST API модуля)

Файл: `modules/my_module/api_router.py`
Объект: `router` (тип `APIRouter`)

### 7.1. Auto-discovery роутера

`api/main.py` при старте сканирует `modules/*/api_router.py` и включает каждый найденный `router` объект:

```python
# api/main.py (упрощённо)
for finder, modname, ispkg in pkgutil.iter_modules([modules_path]):
    if not ispkg:
        continue
    api_mod = importlib.import_module(f"modules.{modname}.api_router")
    if hasattr(api_mod, "router"):
        app.include_router(api_mod.router)
```

### 7.2. Шаблон api_router.py

> **ВАЖНО**: `prefix` на `APIRouter` задаёт базовый путь. В декораторах `@router.get(...)` используйте **относительные** пути (`"/items"`, а не полный URL). Иначе путь продублируется.

```python
"""My Module - REST API Router."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.deps import get_module

router = APIRouter(
    prefix="/api/accounts/{account_id}/modules/my_module",
    tags=["my_module"],
)


def _get_storage(account_id: str):
    """Получить типизированное хранилище модуля."""
    module = get_module(account_id, "my_module")  # → 404 если не найден
    return module._my_storage  # типизированная обёртка


# ─── Pydantic Models ──────────────────────────────

class ItemCreate(BaseModel):
    name: str
    value: int = 0

class ItemUpdate(BaseModel):
    name: str | None = None
    value: int | None = None


# ─── Endpoints (пути ОТНОСИТЕЛЬНЫЕ к prefix!) ────

@router.get("/items")
async def list_items(account_id: str):
    storage = _get_storage(account_id)
    items = storage.read_json("items.json") or {"items": []}
    return items

@router.post("/items")
async def create_item(account_id: str, body: ItemCreate):
    storage = _get_storage(account_id)
    items = storage.read_json("items.json") or {"items": []}
    items["items"].append(body.model_dump())
    storage.write_json("items.json", items)
    return {"status": "ok"}

@router.get("/config")
async def get_config(account_id: str):
    storage = _get_storage(account_id)
    return storage.get_config()

@router.put("/config")
async def update_config(account_id: str, body: dict[str, Any]):
    storage = _get_storage(account_id)
    storage.save_config(body)
    return {"status": "ok"}
```

### 7.3. DI (Dependency Injection)

```python
from api.deps import get_core, get_module

# Получить ядро
core = get_core()  # → OpiumCore (raises 503 if not ready)

# Получить модуль
module = get_module(account_id, "my_module")  # → Module (raises 404 if not found)
```

### 7.4. Правила

| Правило | Пояснение |
|---------|----------|
| `router` — обязательное имя объекта | `api/main.py` ищет именно `router` |
| `prefix` начинается с `/api/accounts/{account_id}/modules/{module_name}` | Соглашение для консистентности |
| Декораторы используют **относительные** пути | `"/items"`, НЕ полный URL (prefix уже задаёт базу) |
| `tags=["module_name"]` | Для группировки в Swagger UI |
| Pydantic models для body | FastAPI auto-validation + docs |
| `get_module()` для доступа к модулю | DI, не хардкодить ссылки |

---

## 8. Frontend: ModuleManifest (навигация и роуты)

Файл: `frontend/src/modules/my_module/index.tsx`

### 8.1. Auto-discovery фронтенда

`frontend/src/modules/index.ts` использует Vite glob import:
```typescript
const moduleFiles = import.meta.glob<Record<string, unknown>>(
  './*/index.tsx', { eager: true }
);
```

Каждый экспортированный объект, проходящий проверку `isManifest()` (есть `name`, `routes`, `navigation`), подхватывается автоматически.

### 8.2. Интерфейс ModuleManifest

```typescript
// frontend/src/modules/index.ts

export interface ModuleNavItem {
  label: string;         // Текст в sidebar (lowercase)
  path: string;          // Относительный путь (без /)
  icon: ReactElement;    // MUI Icon
}

export interface ModuleRoute {
  path: string;          // Должен совпадать с ModuleNavItem.path
  component: React.ComponentType;  // React-компонент страницы
}

export interface ModuleManifest {
  name: string;          // Совпадает с module_name в Python!
  displayName: string;   // Человекочитаемое имя (lowercase)
  description: string;   // Описание модуля
  navigation: ModuleNavItem[];  // Пункты sidebar
  routes: ModuleRoute[];        // Роуты
}
```

### 8.3. Шаблон index.tsx

```tsx
import {
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import type { ModuleManifest } from '../index';
import DashboardPage from './Dashboard';
import SettingsPage from './Settings';

export const myModuleManifest: ModuleManifest = {
  name: 'my_module',          // === module_name в Python
  displayName: 'my module',   // lowercase
  description: 'automatic delivery of digital goods',
  navigation: [
    { label: 'dashboard', path: 'dashboard', icon: <DashboardIcon fontSize="small" /> },
    { label: 'settings', path: 'settings', icon: <SettingsIcon fontSize="small" /> },
  ],
  routes: [
    { path: 'dashboard', component: DashboardPage },
    { path: 'settings', component: SettingsPage },
  ],
};
```

### 8.4. Как это работает в UI

**Роуты** (`App.tsx`) автоматически маунтятся:
```
/accounts/:accountId/modules/{manifest.name}/{route.path}
```
Пример: `/accounts/{account_id}/modules/my_module/dashboard`

**Sidebar** (`Layout.tsx`) автоматически рендерит секцию навигации для каждого модуля:
- Показывает только модули, включённые для текущего аккаунта (`account.modules`)
- Отображает `displayName` как заголовок секции (uppercase caption)
- Каждый `navigation` item → ссылка `/accounts/{accountId}/modules/{name}/{nav.path}`

**Переключение аккаунта** — при выборе нового аккаунта в sidebar:
- Находит первый доступный модуль и переходит на его первую страницу
- Если модулей нет → `/accounts/{id}/chats`

**Страница Orders** (`/accounts/:accountId/orders`) — общая для всех модулей:
- Загружает `GET /api/accounts/{id}/order-tags` → получает теги от всех модулей
- Показывает табы: "All", "steam_rent" (69), "my_module" (12), "Untagged" (5)
- Каждый модуль реализует `get_order_tags()` для тегирования своих заказов (раздел 11)

---

## 9. Frontend: Страницы и компоненты

### 9.1. Структура файлов модуля

```
frontend/src/modules/my_module/
├── index.tsx        # ModuleManifest (обязательно)
├── api.ts           # API клиент модуля (типы + вызовы)
├── Dashboard.tsx    # Страница дашборда
├── Settings.tsx     # Страница настроек
└── ...              # Любые другие страницы
```

### 9.2. Доступные общие компоненты

```tsx
// Заголовок страницы с кнопкой refresh
import { PageHeader } from '../../components/PageHeader';
<PageHeader title="my module" onRefresh={reload} loading={loading} />

// Обёртка для таблиц (тёмный фон, скроллируемый)
import { TablePaper } from '../../components/TablePaper';
<TablePaper>
  <Table>...</Table>
</TablePaper>

// Layout (sidebar + notify)
import { useLayout } from '../../components/Layout';
const { notify } = useLayout();
notify('saved successfully', 'success');  // snackbar

// Карточки со статистикой
import { StatCard, StatusDot } from '../../components/GlowCard';
<StatCard title="Active" value={42} icon={<Icon />} />

// Countdown hook
import { useCountdown } from '../../hooks/useCountdown';
const { formatRemaining, isExpiringSoon } = useCountdown();
```

### 9.3. URL параметры

В каждой странице модуля доступен `accountId`:
```tsx
import { useParams } from 'react-router-dom';

export default function DashboardPage() {
  const { accountId } = useParams<{ accountId: string }>();
  // accountId = "{account_id}" (из URL)
}
```

### 9.4. Паттерн страницы

```tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import { PageHeader } from '../../components/PageHeader';
import { useLayout } from '../../components/Layout';
import { myModuleApi } from './api';

export default function DashboardPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await myModuleApi.getOverview(accountId);
      setData(res.data);
    } catch {
      notify('failed to load', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [accountId]);

  return (
    <Box>
      <PageHeader title="my module" onRefresh={load} loading={loading} />
      {data && (
        <Typography>{JSON.stringify(data)}</Typography>
      )}
    </Box>
  );
}
```

---

## 10. Frontend: API клиент модуля

Файл: `frontend/src/modules/my_module/api.ts`

### 10.1. Шаблон

```typescript
import api from '../../api/client';

const base = (accountId: string) =>
  `/accounts/${accountId}/modules/my_module`;

// ─── Types ───────────────────────────────────────

export interface Item {
  name: string;
  value: number;
}

export interface MyModuleConfig {
  enabled: boolean;
  max_items: number;
}

// ─── API ─────────────────────────────────────────

export const myModuleApi = {
  getItems: (accountId: string) =>
    api.get<{ items: Item[] }>(`${base(accountId)}/items`),

  createItem: (accountId: string, data: Partial<Item>) =>
    api.post<Item>(`${base(accountId)}/items`, data),

  deleteItem: (accountId: string, itemId: string) =>
    api.delete(`${base(accountId)}/items/${itemId}`),

  getConfig: (accountId: string) =>
    api.get<MyModuleConfig>(`${base(accountId)}/config`),

  updateConfig: (accountId: string, config: Partial<MyModuleConfig>) =>
    api.put(`${base(accountId)}/config`, config),
};
```

### 10.2. Axios инстанс

`api/client.ts` — готовый axios инстанс с:
- `baseURL: '/api'` (Vite проксирует на `localhost:8000`)
- JWT Bearer token из localStorage (`opium_token`) — автоматически
- 401 → redirect на login (автоматически)
- timeout: 30 сек

**Импорт**: `import api from '../../api/client'`

---

## 11. Order Tags — интеграция в страницу заказов

Модуль может тегировать заказы для фильтрации на странице Orders (`/accounts/:accountId/orders`).

### 11.1. Backend: реализовать `get_order_tags()`

```python
async def get_order_tags(
    self, orders: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Args:
        orders: Список заказов [{order_id, description, price, buyer_username, ...}, ...]
                Передаётся из API для матчинга по описанию.
    
    Returns:
        {order_id: {"module": "my_module", "game_id": "cs2", "game_name": "CS2"}, ...}
    """
    tags = {}
    
    if orders:
        for order in orders:
            desc = order.get("description", "").lower()
            if "мой товар" in desc:
                tags[order["order_id"]] = {
                    "module": self.module_name,
                    "category": "digital_goods",
                }
    
    return tags
```

### 11.2. Как это работает

1. Frontend вызывает `GET /api/accounts/{id}/order-tags`
2. `api/main.py` получает все заказы через `get_sells` (один раз)
3. Для каждого модуля аккаунта вызывает `module.get_order_tags(orders=serialized_orders)`
4. Если модуль не принимает `orders=` (старая сигнатура) — ловит `TypeError`, вызывает без аргумента
5. Собирает все теги в один dict
6. Frontend показывает табы: "All", "steam_rent" (69), "my_module" (12), "Untagged" (5)

### 11.3. Формат ответа API

```json
{
  "tags": {
    "ABC123": {"module": "my_module", "category": "digital_goods"},
    "DEF456": {"module": "steam_rent", "game_id": "cs2", "game_name": "CS2"}
  },
  "modules": ["my_module", "steam_rent"],
  "games": {
    "steam_rent": [
      {"game_id": "cs2", "game_name": "CS2"},
      {"game_id": "dayz", "game_name": "dayz"}
    ]
  }
}
```

### 11.4. Backward compatibility

- `orders` параметр опциональный (default `None`)
- Если модуль не реализует `get_order_tags` — возвращается `{}`
- API оборачивает вызов в `try/except TypeError` для старых сигнатур без `orders=`

---

## 12. Данные на диске

### 12.1. Файловая структура

```
accounts/{account_id}/modules/{module_name}/
├── config.json       # Настройки модуля (обязательно)
├── *.json            # Любые JSON файлы
├── *.db              # SQLite базы
└── ...               # Любые файлы
```

Модуль считается установленным если его **директория существует** в `accounts/{id}/modules/`.

### 12.2. config.json — соглашение

```json
{
  "enabled": true,
  "check_interval_sec": 60,
  "custom_setting": "value"
}
```

Конфиг читается через:
- `self.storage.config` (cached dict)
- `self.get_config("key", default)` (shortcut)
- PUT `/api/accounts/{id}/modules/{module_name}/config` (из frontend)

### 12.3. Важные правила

| Правило | Почему |
|---------|--------|
| Каждая категория данных — отдельный JSON файл | Атомарность записи, нет race conditions |
| Не хранить секреты в открытом виде | Безопасность |
| Использовать кэш в Storage-обёртке | Производительность |
| `to_dict()` с обработкой Enum → str | JSON serialization |
| `*_from_dict()` factory functions | Парсинг с дефолтами + миграция |

---

## 13. Паттерн: модуль обработки заказов (lot mapping)

Все модули Opium работают по одной схеме — слушают событие оплаты, матчат заказ по описанию лота и выполняют свою логику. Это основной паттерн.

### 13.1. Общая схема

```
FunPay оплата → new_order event
  → handle_event() → матчинг описания заказа по lot_mapping
    → совпало? → бизнес-логика модуля (выдача, аренда, ...)
    → не совпало? → return [] (пропуск)
```

### 13.2. Lot Mapping

Lot mapping — таблица соответствий между описанием лота FunPay и внутренним идентификатором (game_id, product_id и т.д.):

```json
{
  "mappings": [
    {
      "lot_pattern": "CS2 аренда Steam аккаунта",
      "game_id": "cs2",
      "duration_hours": 24
    },
    {
      "lot_pattern": "DOTA2 аренда",
      "game_id": "dota2",
      "duration_hours": 12
    }
  ]
}
```

Матчинг: `lot_pattern.lower() in order_description.lower()`.

### 13.3. Типичный handle_event

```python
async def handle_event(self, event: OpiumEvent) -> list[Command]:
    if event.event_type == "new_order":
        return self._handle_new_order(event)
    elif event.event_type == "new_message":
        return self._handle_new_message(event)
    return []

def _handle_new_order(self, event: OpiumEvent) -> list[Command]:
    order = event.payload.get("order", {})
    order_id = order.get("id", "")
    description = order.get("description", "")
    buyer_id = order.get("buyer_id", 0)
    buyer_name = order.get("buyer_username", "")
    
    # 1. Матчинг по lot_mapping
    mapping = self._storage.find_mapping_for_description(description)
    if not mapping:
        return []  # Не наш заказ
    
    # 2. Бизнес-логика
    result = self._process_order(order_id, mapping, buyer_id, buyer_name)
    
    # 3. Ответ покупателю
    return [
        Command("send_message", {
            "chat_id": buyer_id,
            "text": result.message,
            "chat_name": buyer_name,
        })
    ]
```

### 13.4. Как steam_rent реализует паттерн

| Компонент | Реализация в steam_rent |
|-----------|------------------------|
| Lot mapping | `lot_mappings.json` → `{lot_pattern, game_id, duration_hours}` |
| Матчинг | `description.lower().startswith(pattern.lower())` |
| Бизнес-логика | Выдача Steam-аккаунта → пароль + Steam Guard → запуск таймера аренды |
| Послеоплата | Команды `!данные`, `!код`, `!продлить` через `new_message` |
| Фоновая задача | `RentalScheduler` — проверка истечений, предупреждения, отзывы |
| Order Tags | `get_order_tags()` — тегирует по активным арендам + lot_pattern |

Другой модуль (например, `auto_delivery`) может использовать тот же паттерн:
- Lot mapping: `lot_pattern → product_id`
- Бизнес-логика: выдача цифрового товара (ключ, аккаунт, ссылка)
- Фоновая задача: не нужна (мгновенная выдача)

### 13.5. Существующие модули (справка)

| Модуль | Описание | Подписки | Тип |
|--------|----------|----------|-----|
| `steam_rent` | Аренда Steam-аккаунтов | `new_order`, `new_message` | lot mapping + scheduler |
| `telegram_bot` | Уведомления + удалённое управление через Telegram | все события (настраиваемо) | notification + control |
| `auto_raise` | Автоподнятие лотов по cooldown | все (no-op) | background scheduler |

**`telegram_bot`** — не генерирует команды (`handle_event → []`), используется для пересылки событий в Telegram и удалённого управления через inline-кнопки.

**`auto_raise`** — не обрабатывает события FunPay, вся логика в фоновом `_raise_loop` (каждые 30 секунд проверяет cooldowns категорий).

---

## 14. Логирование в модулях

### 14.1. Соглашение

```python
import logging
logger = logging.getLogger("opium.{module_name}")
# или для подмодулей:
logger = logging.getLogger("opium.{module_name}.handlers")
```

Все логи автоматически попадают в файл и консоль через иерархию `opium.*`.

### 14.2. Что логировать (обязательно)

| Точка | Уровень | Пример |
|-------|---------|--------|
| `handle_event()` вход | DEBUG | `Event new_order received` |
| Команды, возвращённые из handle_event | INFO | `Produced 2 commands: send_message, send_message` |
| `on_start()` / `on_stop()` | INFO | `Module started`, `Module stopped` |
| Ошибки | ERROR | `Failed to process order: {e}` |
| Пропуск события (не наш заказ) | DEBUG | `Order ABC123 does not match any lot mapping` |
| Выполнение execute_command | INFO | `Executing raise for category CS2` |

### 14.3. Что НЕ логировать

- Секреты (пароли, golden_key, shared_secret, bot token)
- Полный текст сообщений (используйте `text[:60]` preview)
- Тела HTTP-ответов (используйте статус + длину)

### 14.4. Формат

Используйте `[{self.name}]` prefix для идентификации инстанса:
```python
logger.info(f"[{self.name}] Started for account {self.account_id}")
# → opium.steam_rent | [steam_rent] Started for account {account_id}
```

---

## 15. Чеклист: готов ли модуль?

### Backend (обязательно):
- [ ] `modules/my_module/__init__.py` — импортирует класс модуля
- [ ] `modules/my_module/module.py` — `@register_module_class`, `module_name: ClassVar[str]`, `handle_event()`
- [ ] `module_name` уникален (snake_case, без пробелов)
- [ ] `handle_event()` ВСЕГДА возвращает `list[Command]` (не None!)
- [ ] `on_start()`/`on_stop()` не бросают исключения (логируют ошибки)

### Backend (рекомендовано):
- [ ] `get_subscriptions()` — фильтрует только нужные события (не подписываться на всё)
- [ ] `get_order_tags()` — если модуль создаёт/обрабатывает заказы
- [ ] Lot mapping — файл `lot_mappings.json` для матчинга заказов по описанию
- [ ] Типизированная Storage-обёртка (storage.py)
- [ ] Модели в models.py (dataclass)
- [ ] Handlers отделены от module.py (handlers.py)
- [ ] Логирование: `logger = logging.getLogger("opium.{module_name}")`, все ключевые действия залогированы (см. раздел 14)

### REST API (если есть UI):
- [ ] `modules/my_module/api_router.py` с объектом `router`
- [ ] `prefix="/api/accounts/{account_id}/modules/{module_name}"` на APIRouter
- [ ] Пути в декораторах — **относительные** (`"/items"`, не полный URL)
- [ ] Pydantic models для request body
- [ ] `get_module()` для DI

### Frontend (если есть UI):
- [ ] `frontend/src/modules/my_module/index.tsx` с `ModuleManifest` export
- [ ] `manifest.name` === `module_name` в Python
- [ ] api.ts — типы и вызовы
- [ ] Страницы используют `useParams().accountId`
- [ ] Стиль: MUI v6, тёмная тема, lowercase labels

### Данные:
- [ ] Папка `accounts/{id}/modules/{module_name}/` создаётся автоматически через ModuleStorage
- [ ] `config.json` — конфигурация модуля
- [ ] Отдельные JSON файлы для разных категорий данных

---

## 16. Полный пример: auto_delivery

Минимальный реальный модуль — автовыдача цифровых товаров при заказе.

### 15.1. Структура

```
modules/auto_delivery/
├── __init__.py
├── module.py
├── storage.py
├── models.py
└── api_router.py

frontend/src/modules/auto_delivery/
├── index.tsx
├── api.ts
├── Dashboard.tsx
└── Products.tsx
```

### 15.2. `modules/auto_delivery/__init__.py`

```python
"""Auto Delivery — автовыдача цифровых товаров."""
from .module import AutoDeliveryModule  # noqa: F401
```

### 15.3. `modules/auto_delivery/models.py`

```python
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class ProductStatus(Enum):
    AVAILABLE = "available"
    SOLD = "sold"


@dataclass
class Product:
    product_id: str
    lot_pattern: str   # подстрока из описания заказа FunPay
    content: str       # что выдать (ключ, ссылка, etc.)
    status: ProductStatus = ProductStatus.AVAILABLE


@dataclass
class Delivery:
    delivery_id: str
    order_id: str
    product_id: str
    buyer_id: int
    buyer_name: str
    delivered_at: str


def product_from_dict(d: dict[str, Any]) -> Product:
    return Product(
        product_id=d["product_id"],
        lot_pattern=d["lot_pattern"],
        content=d.get("content", ""),
        status=ProductStatus(d.get("status", "available")),
    )


def delivery_from_dict(d: dict[str, Any]) -> Delivery:
    return Delivery(
        delivery_id=d["delivery_id"],
        order_id=d["order_id"],
        product_id=d["product_id"],
        buyer_id=d.get("buyer_id", 0),
        buyer_name=d.get("buyer_name", ""),
        delivered_at=d.get("delivered_at", ""),
    )


def to_dict(obj: Any) -> dict[str, Any]:
    d = asdict(obj)
    _convert_enums(d)
    return d


def _convert_enums(obj: Any) -> Any:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, Enum):
                obj[k] = v.value
            elif isinstance(v, (dict, list)):
                _convert_enums(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, Enum):
                obj[i] = v.value
            elif isinstance(v, (dict, list)):
                _convert_enums(v)
```

### 15.4. `modules/auto_delivery/storage.py`

```python
from __future__ import annotations
from typing import TYPE_CHECKING
from .models import Product, Delivery, product_from_dict, delivery_from_dict, to_dict, ProductStatus

if TYPE_CHECKING:
    from core.storage import ModuleStorage

PRODUCTS_FILE = "products.json"
DELIVERIES_FILE = "deliveries.json"


class AutoDeliveryStorage:
    def __init__(self, module_storage: ModuleStorage) -> None:
        self._storage = module_storage
        self._cache_products: list[Product] | None = None

    def get_config(self) -> dict:
        return self._storage.config

    # ─── Products ─────────────────────────────────

    def get_products(self) -> list[Product]:
        if self._cache_products is None:
            data = self._storage.read_json(PRODUCTS_FILE)
            self._cache_products = [
                product_from_dict(d) for d in (data or {}).get("products", [])
            ]
        return self._cache_products

    def save_products(self, products: list[Product]) -> None:
        self._cache_products = products
        self._storage.write_json(PRODUCTS_FILE, {
            "products": [to_dict(p) for p in products]
        })

    def find_product_for_lot(self, lot_description: str) -> Product | None:
        """Найти доступный товар по описанию заказа."""
        desc_lower = lot_description.lower()
        for p in self.get_products():
            if p.status == ProductStatus.AVAILABLE and p.lot_pattern.lower() in desc_lower:
                return p
        return None

    def mark_sold(self, product_id: str) -> None:
        products = self.get_products()
        for p in products:
            if p.product_id == product_id:
                p.status = ProductStatus.SOLD
                break
        self.save_products(products)

    # ─── Deliveries ───────────────────────────────

    def get_deliveries(self) -> list[Delivery]:
        data = self._storage.read_json(DELIVERIES_FILE)
        return [delivery_from_dict(d) for d in (data or {}).get("deliveries", [])]

    def add_delivery(self, delivery: Delivery) -> None:
        deliveries = self.get_deliveries()
        deliveries.append(delivery)
        self._storage.write_json(DELIVERIES_FILE, {
            "deliveries": [to_dict(d) for d in deliveries]
        })
```

### 15.5. `modules/auto_delivery/module.py`

```python
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import Any, ClassVar

from core.module import Module, register_module_class, Subscription
from core.commands import Command
from core.event_bus import OpiumEvent
from core.storage import ModuleStorage

from .storage import AutoDeliveryStorage
from .models import Delivery

logger = logging.getLogger("opium.auto_delivery")


@register_module_class
class AutoDeliveryModule(Module):
    module_name: ClassVar[str] = "auto_delivery"

    def __init__(self, account_id: str, storage: ModuleStorage) -> None:
        super().__init__(account_id, storage)
        self._delivery_storage = AutoDeliveryStorage(storage)
        logger.info(f"[{self.name}] Initialized for {account_id}")

    @property
    def delivery_storage(self) -> AutoDeliveryStorage:
        return self._delivery_storage

    def get_subscriptions(self) -> list[Subscription]:
        return [Subscription(event_types=["new_order"])]

    async def handle_event(self, event: OpiumEvent) -> list[Command]:
        if event.event_type != "new_order":
            return []

        order = event.payload.get("order", {})
        order_id = order.get("id", "")
        description = order.get("description", "")
        buyer_id = order.get("buyer_id", 0)
        buyer_name = order.get("buyer_username", "")

        if not order_id or not description:
            return []

        # Проверить, не выдавали ли уже
        for d in self._delivery_storage.get_deliveries():
            if d.order_id == order_id:
                logger.debug(f"Order {order_id} already delivered")
                return []

        # Найти подходящий товар по lot_pattern
        product = self._delivery_storage.find_product_for_lot(description)
        if not product:
            return []  # Не наш заказ

        # Выдать
        self._delivery_storage.mark_sold(product.product_id)
        self._delivery_storage.add_delivery(Delivery(
            delivery_id=str(uuid.uuid4()),
            order_id=order_id,
            product_id=product.product_id,
            buyer_id=buyer_id,
            buyer_name=buyer_name,
            delivered_at=datetime.now().isoformat(),
        ))

        logger.info(f"Delivered {product.product_id} for order {order_id}")

        return [
            Command("send_message", {
                "chat_id": buyer_id,
                "text": f"Спасибо за покупку!\n\nВаш товар:\n{product.content}",
                "chat_name": buyer_name,
            })
        ]

    async def get_order_tags(
        self, orders: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        tags = {}
        # Помечаем выданные заказы
        for delivery in self._delivery_storage.get_deliveries():
            tags[delivery.order_id] = {
                "module": self.module_name,
                "product_id": delivery.product_id,
            }
        # Матчим оставшиеся заказы по описанию
        if orders:
            for order in orders:
                oid = order.get("order_id", "")
                if oid in tags:
                    continue
                desc = order.get("description", "")
                product = self._delivery_storage.find_product_for_lot(desc)
                if product:
                    tags[oid] = {"module": self.module_name}
        return tags

    async def on_start(self) -> None:
        products = self._delivery_storage.get_products()
        available = sum(1 for p in products if p.status.value == "available")
        logger.info(f"[{self.name}] Started. Products: {len(products)}, available: {available}")

    async def on_stop(self) -> None:
        logger.info(f"[{self.name}] Stopped")
```

### 15.6. `modules/auto_delivery/api_router.py`

```python
"""Auto Delivery - REST API Router."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.deps import get_module

router = APIRouter(
    prefix="/api/accounts/{account_id}/modules/auto_delivery",
    tags=["auto_delivery"],
)


def _get_storage(account_id: str):
    module = get_module(account_id, "auto_delivery")
    return module._delivery_storage


# ─── Pydantic Models ──────────────────────────────

class ProductCreate(BaseModel):
    product_id: str
    lot_pattern: str
    content: str

class ProductUpdate(BaseModel):
    lot_pattern: str | None = None
    content: str | None = None


# ─── Products ─────────────────────────────────────

@router.get("/products")
async def list_products(account_id: str):
    storage = _get_storage(account_id)
    products = storage.get_products()
    from .models import to_dict
    return {"products": [to_dict(p) for p in products]}


@router.post("/products")
async def create_product(account_id: str, body: ProductCreate):
    storage = _get_storage(account_id)
    from .models import Product, ProductStatus
    product = Product(
        product_id=body.product_id,
        lot_pattern=body.lot_pattern,
        content=body.content,
        status=ProductStatus.AVAILABLE,
    )
    products = storage.get_products()
    products.append(product)
    storage.save_products(products)
    return {"status": "ok", "product_id": product.product_id}


@router.delete("/products/{product_id}")
async def delete_product(account_id: str, product_id: str):
    storage = _get_storage(account_id)
    products = storage.get_products()
    products = [p for p in products if p.product_id != product_id]
    storage.save_products(products)
    return {"status": "ok"}


# ─── Deliveries ───────────────────────────────────

@router.get("/deliveries")
async def list_deliveries(account_id: str):
    storage = _get_storage(account_id)
    deliveries = storage.get_deliveries()
    from .models import to_dict
    return {"deliveries": [to_dict(d) for d in deliveries]}


# ─── Overview ─────────────────────────────────────

@router.get("/overview")
async def get_overview(account_id: str):
    storage = _get_storage(account_id)
    products = storage.get_products()
    deliveries = storage.get_deliveries()
    from .models import ProductStatus
    return {
        "total_products": len(products),
        "available_products": sum(1 for p in products if p.status == ProductStatus.AVAILABLE),
        "sold_products": sum(1 for p in products if p.status == ProductStatus.SOLD),
        "total_deliveries": len(deliveries),
    }
```

### 15.7. `frontend/src/modules/auto_delivery/index.tsx`

```tsx
import {
  Dashboard as DashboardIcon,
  Inventory as InventoryIcon,
} from '@mui/icons-material';
import type { ModuleManifest } from '../index';
import DashboardPage from './Dashboard';
import ProductsPage from './Products';

export const autoDeliveryManifest: ModuleManifest = {
  name: 'auto_delivery',
  displayName: 'auto delivery',
  description: 'automatic delivery of digital goods on purchase',
  navigation: [
    { label: 'dashboard', path: 'dashboard', icon: <DashboardIcon fontSize="small" /> },
    { label: 'products', path: 'products', icon: <InventoryIcon fontSize="small" /> },
  ],
  routes: [
    { path: 'dashboard', component: DashboardPage },
    { path: 'products', component: ProductsPage },
  ],
};
```

### 15.8. `frontend/src/modules/auto_delivery/api.ts`

```typescript
import api from '../../api/client';

const base = (accountId: string) =>
  `/accounts/${accountId}/modules/auto_delivery`;

export interface Product {
  product_id: string;
  lot_pattern: string;
  content: string;
  status: 'available' | 'sold';
}

export interface Delivery {
  delivery_id: string;
  order_id: string;
  product_id: string;
  buyer_id: number;
  buyer_name: string;
  delivered_at: string;
}

export interface Overview {
  total_products: number;
  available_products: number;
  sold_products: number;
  total_deliveries: number;
}

export const autoDeliveryApi = {
  getOverview: (accountId: string) =>
    api.get<Overview>(`${base(accountId)}/overview`),

  getProducts: (accountId: string) =>
    api.get<{ products: Product[] }>(`${base(accountId)}/products`),

  createProduct: (accountId: string, data: Partial<Product>) =>
    api.post(`${base(accountId)}/products`, data),

  deleteProduct: (accountId: string, productId: string) =>
    api.delete(`${base(accountId)}/products/${productId}`),

  getDeliveries: (accountId: string) =>
    api.get<{ deliveries: Delivery[] }>(`${base(accountId)}/deliveries`),
};
```

### 15.9. `frontend/src/modules/auto_delivery/Dashboard.tsx`

```tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Skeleton } from '@mui/material';
import Grid from '@mui/material/Grid2';
import {
  Inventory as ProductsIcon,
  CheckCircle as SoldIcon,
  LocalShipping as DeliveredIcon,
  HourglassEmpty as AvailableIcon,
} from '@mui/icons-material';
import { StatCard } from '../../components/GlowCard';
import { PageHeader } from '../../components/PageHeader';
import { useLayout } from '../../components/Layout';
import { autoDeliveryApi, Overview } from './api';

export default function DashboardPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await autoDeliveryApi.getOverview(accountId);
      setOverview(res.data);
    } catch {
      notify('failed to load overview', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [accountId]);

  if (loading) {
    return (
      <Box>
        <PageHeader title="auto delivery" />
        <Grid container spacing={2}>
          {[...Array(4)].map((_, i) => (
            <Grid key={i} size={{ xs: 6, md: 3 }}>
              <Skeleton variant="rounded" height={100} sx={{ borderRadius: 4, bgcolor: 'rgba(255,255,255,0.04)' }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="auto delivery" onRefresh={load} loading={loading} />
      {overview && (
        <Grid container spacing={2}>
          <Grid size={{ xs: 6, md: 3 }}>
            <StatCard title="total" value={overview.total_products} icon={<ProductsIcon />} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <StatCard title="available" value={overview.available_products} icon={<AvailableIcon />} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <StatCard title="sold" value={overview.sold_products} icon={<SoldIcon />} />
          </Grid>
          <Grid size={{ xs: 6, md: 3 }}>
            <StatCard title="deliveries" value={overview.total_deliveries} icon={<DeliveredIcon />} />
          </Grid>
        </Grid>
      )}
    </Box>
  );
}
```

### 15.10. `frontend/src/modules/auto_delivery/Products.tsx`

```tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Box, Table, TableHead, TableBody, TableRow, TableCell,
  Chip, IconButton, TextField, Button, Dialog, DialogTitle,
  DialogContent, DialogActions,
} from '@mui/material';
import { Delete as DeleteIcon, Add as AddIcon } from '@mui/icons-material';
import { PageHeader } from '../../components/PageHeader';
import { TablePaper } from '../../components/TablePaper';
import { useLayout } from '../../components/Layout';
import { autoDeliveryApi, Product } from './api';

export default function ProductsPage() {
  const { accountId } = useParams<{ accountId: string }>();
  const { notify } = useLayout();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newProduct, setNewProduct] = useState({ product_id: '', lot_pattern: '', content: '' });

  const load = async () => {
    if (!accountId) return;
    setLoading(true);
    try {
      const res = await autoDeliveryApi.getProducts(accountId);
      setProducts(res.data.products);
    } catch {
      notify('failed to load products', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [accountId]);

  const handleCreate = async () => {
    if (!accountId) return;
    try {
      await autoDeliveryApi.createProduct(accountId, newProduct);
      setDialogOpen(false);
      setNewProduct({ product_id: '', lot_pattern: '', content: '' });
      notify('product created', 'success');
      load();
    } catch {
      notify('failed to create product', 'error');
    }
  };

  const handleDelete = async (productId: string) => {
    if (!accountId) return;
    try {
      await autoDeliveryApi.deleteProduct(accountId, productId);
      notify('product deleted', 'success');
      load();
    } catch {
      notify('failed to delete', 'error');
    }
  };

  return (
    <Box>
      <PageHeader
        title="products"
        onRefresh={load}
        loading={loading}
        actions={
          <Button startIcon={<AddIcon />} variant="outlined" size="small" onClick={() => setDialogOpen(true)}>
            add product
          </Button>
        }
      />

      <TablePaper>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>ID</TableCell>
              <TableCell>Lot Pattern</TableCell>
              <TableCell>Content</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {products.map((p) => (
              <TableRow key={p.product_id}>
                <TableCell>{p.product_id}</TableCell>
                <TableCell>{p.lot_pattern}</TableCell>
                <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {p.content}
                </TableCell>
                <TableCell>
                  <Chip
                    label={p.status}
                    size="small"
                    color={p.status === 'available' ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell align="right">
                  <IconButton size="small" onClick={() => handleDelete(p.product_id)}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TablePaper>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)}>
        <DialogTitle>add product</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1, minWidth: 400 }}>
          <TextField
            label="Product ID" size="small" value={newProduct.product_id}
            onChange={(e) => setNewProduct({ ...newProduct, product_id: e.target.value })}
          />
          <TextField
            label="Lot Pattern" size="small" value={newProduct.lot_pattern}
            onChange={(e) => setNewProduct({ ...newProduct, lot_pattern: e.target.value })}
            helperText="Подстрока из описания заказа FunPay"
          />
          <TextField
            label="Content" size="small" multiline rows={3} value={newProduct.content}
            onChange={(e) => setNewProduct({ ...newProduct, content: e.target.value })}
            helperText="Что выдать покупателю"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>cancel</Button>
          <Button variant="contained" onClick={handleCreate}>create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

---

## Итого

| Что нужно | Минимум | С UI |
|-----------|---------|------|
| `modules/X/__init__.py` | YES | YES |
| `modules/X/module.py` | YES | YES |
| `modules/X/api_router.py` | — | YES |
| `frontend/src/modules/X/index.tsx` | — | YES |
| `frontend/src/modules/X/api.ts` | — | YES |
| `frontend/src/modules/X/*.tsx` | — | YES |

**Положил файлы → перезапустил → работает.**

Дашборд модуля доступен по адресу:
```
/accounts/{accountId}/modules/{module_name}/dashboard
```
Страница заказов общая для всех модулей:
```
/accounts/{accountId}/orders
```
