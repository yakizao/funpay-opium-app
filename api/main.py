"""Opium API - REST API для управления системой."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

# Load .env file if exists
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from core import OpiumCore, Command
from api.serializers import serialize_messages, serialize_order_shortcut, serialize_order
from security.setup import setup_security
from security.config import security_config

# Load security config EARLY - before CORS reads cors_origins
security_config.load()

logger = logging.getLogger("opium.api")

# ─── Request Logging Middleware ─────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with method, path, status, and response time."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} "
            f"({elapsed_ms:.0f}ms)"
        )
        return response

# Глобальный инстанс Core
core: OpiumCore | None = None


# ========== Pydantic Models ==========

class AccountCreate(BaseModel):
    account_id: str
    golden_key: str
    user_agent: str
    proxy: dict[str, str] | None = None
    anti_detect: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None
    reconnect: dict[str, Any] | None = None
    disable_messages: bool = False
    disable_orders: bool = False


class AccountInfo(BaseModel):
    account_id: str
    username: str | None
    fp_id: int | None
    state: str
    is_running: bool
    last_error: str | None
    modules: list[str]


class ModuleAdd(BaseModel):
    module_name: str
    config: dict[str, Any] | None = None


class ModuleConfigUpdate(BaseModel):
    config: dict[str, Any]


class SendMessageBody(BaseModel):
    text: str


# ========== Lifespan ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    global core
    
    # Startup - всё non-blocking, API доступен за <1с
    logger.info("Starting Opium Core...")
    core = OpiumCore(".")
    await core.start()  # Запускает EventBus (мгновенно)
    await core.load_accounts(auto_start=True)  # Регистрирует аккаунты, init в фоне
    
    # Share core with module API routers
    from api.deps import set_core
    set_core(core)
    
    logger.info(f"Opium Core started: {core}")
    
    yield
    
    # Shutdown
    logger.info("Stopping Opium Core...")
    if core:
        await core.stop()
    logger.info("Opium Core stopped")


# ========== FastAPI App ==========

app = FastAPI(
    title="opium api",
    description="rest api for funpay account management",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow Vite dev server + configured origins
_cors_origins = security_config.cors_origins if security_config.cors_origins else [
    "http://localhost:3000", "http://127.0.0.1:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# Security middleware (auth, rate limit, IP whitelist, secure headers)
setup_security(app)

# Request logging (added after security so it captures auth-filtered requests too)
app.add_middleware(RequestLoggingMiddleware)

# Auto-discover module API routers (modules/*/api_router.py)
import importlib
import pkgutil

_modules_dir = str(Path(__file__).parent.parent / "modules")
for _finder, _modname, _ispkg in pkgutil.iter_modules([_modules_dir]):
    if not _ispkg:
        continue
    try:
        _mod = importlib.import_module(f"modules.{_modname}.api_router")
        if hasattr(_mod, "router"):
            app.include_router(_mod.router)
            logger.info(f"Auto-mounted API router: modules.{_modname}")
    except ImportError:
        pass  # Module has no api_router — that's OK
    except Exception as _e:
        logger.error(f"Failed to mount router for '{_modname}': {_e}")

# ========== Routes ==========

@app.get("/")
async def root():
    """API root."""
    return {"name": "Opium API", "status": "ok"}


@app.get("/api/status")
async def get_status():
    """Статус системы."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    return {
        "running": core.is_running,
        "accounts": core.account_count,
        "modules": core.get_total_module_count(),
    }


# ========== Accounts ==========

@app.get("/api/accounts")
async def list_accounts() -> list[AccountInfo]:
    """Список всех аккаунтов."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    accounts = []
    for account_id, runtime in core.get_all_runtimes().items():
        modules = list(core.get_account_modules(account_id).keys())
        accounts.append(AccountInfo(
            account_id=account_id,
            username=runtime.username,
            fp_id=runtime.fp_account_id,
            state=runtime.state.value,
            is_running=runtime.is_running,
            last_error=runtime.last_error,
            modules=modules,
        ))
    
    return accounts


@app.post("/api/accounts")
async def create_account(data: AccountCreate) -> JSONResponse:
    """Создать новый аккаунт. Инициализация в фоне."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    try:
        runtime = await core.add_account(
            account_id=data.account_id,
            golden_key=data.golden_key,
            user_agent=data.user_agent,
            proxy=data.proxy,
            anti_detect=data.anti_detect,
            rate_limit=data.rate_limit,
            reconnect=data.reconnect,
            disable_messages=data.disable_messages,
            disable_orders=data.disable_orders,
            auto_start=core.is_running,
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "status": "initializing",
                "account_id": data.account_id,
                "state": runtime.state.value,
                "message": "Account registered. Initializing in background. Poll GET /api/accounts/{id} for status.",
            },
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Failed to create account: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/accounts/{account_id}")
async def get_account(account_id: str) -> AccountInfo:
    """Получить информацию об аккаунте."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    runtime = core.get_runtime(account_id)
    if not runtime:
        raise HTTPException(404, f"Account {account_id} not found")
    
    modules = list(core.get_account_modules(account_id).keys())
    return AccountInfo(
        account_id=account_id,
        username=runtime.username,
        fp_id=runtime.fp_account_id,
        state=runtime.state.value,
        is_running=runtime.is_running,
        last_error=runtime.last_error,
        modules=modules,
    )


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str):
    """Удалить аккаунт."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    success = await core.remove_account(account_id)
    if not success:
        raise HTTPException(404, f"Account {account_id} not found")
    
    return {"status": "deleted", "account_id": account_id}


@app.get("/api/accounts/{account_id}/config")
async def get_account_config(account_id: str):
    """Получить конфигурацию аккаунта."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    account_storage = core.storage.get_account_storage(account_id)
    data = account_storage.load_account_data()
    if not data:
        raise HTTPException(404, f"Account {account_id} not found")
    
    return {
        "golden_key": data.golden_key,
        "user_agent": data.user_agent,
        "proxy": data.proxy,
        "anti_detect": data.anti_detect,
        "rate_limit": data.rate_limit,
        "reconnect": data.reconnect,
        "disable_messages": data.disable_messages,
        "disable_orders": data.disable_orders,
    }


@app.patch("/api/accounts/{account_id}/config")
async def update_account_config(account_id: str, body: dict[str, Any]):
    """Обновить конфигурацию аккаунта (partial update)."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    account_storage = core.storage.get_account_storage(account_id)
    data = account_storage.load_account_data()
    if not data:
        raise HTTPException(404, f"Account {account_id} not found")
    
    allowed = {"golden_key", "user_agent", "proxy", "anti_detect", "rate_limit", "reconnect", "disable_messages", "disable_orders"}
    for key, value in body.items():
        if key in allowed:
            setattr(data, key, value)
    
    account_storage.save_account_data(data)
    
    # Apply config changes to running runtime via public API
    runtime = core.get_runtime(account_id)
    if runtime and runtime.is_running:
        new_config = data.to_config()
        runtime.update_config(anti_detect=new_config.anti_detect)
    
    return {
        "golden_key": data.golden_key,
        "user_agent": data.user_agent,
        "proxy": data.proxy,
        "anti_detect": data.anti_detect,
        "rate_limit": data.rate_limit,
        "reconnect": data.reconnect,
        "disable_messages": data.disable_messages,
        "disable_orders": data.disable_orders,
    }


@app.post("/api/accounts/{account_id}/start")
async def start_account(account_id: str):
    """Запустить аккаунт. Возвращает 202 мгновенно, запуск в фоне."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    runtime = core.get_runtime(account_id)
    if not runtime:
        raise HTTPException(404, f"Account {account_id} not found")
    
    if not runtime.is_initialized:
        state = runtime.state.value
        if state == "initializing":
            raise HTTPException(400, f"account is initializing, please wait")
        raise HTTPException(400, f"account not yet initialized (state: {state})")
    
    # start() теперь non-blocking (создаёт фоновую задачу внутри)
    await runtime.start()
    return JSONResponse(
        status_code=202,
        content={"status": "starting", "account_id": account_id, "state": runtime.state.value},
    )


@app.post("/api/accounts/{account_id}/stop")
async def stop_account(account_id: str):
    """Остановить аккаунт. Возвращает 202 мгновенно, остановка в фоне."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    runtime = core.get_runtime(account_id)
    if not runtime:
        raise HTTPException(404, f"Account {account_id} not found")
    
    # stop() теперь non-blocking (отменяет задачи, shutdown_delay в фоне)
    await runtime.stop()
    return JSONResponse(
        status_code=202,
        content={"status": "stopping", "account_id": account_id, "state": runtime.state.value},
    )


# ========== Modules ==========

@app.get("/api/accounts/{account_id}/modules")
async def list_account_modules(account_id: str):
    """Список модулей аккаунта."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    if not core.get_runtime(account_id):
        raise HTTPException(404, f"Account {account_id} not found")
    
    modules = []
    for name, module in core.get_account_modules(account_id).items():
        modules.append({
            "name": name,
            "config": module.config,
        })
    
    return modules


@app.post("/api/accounts/{account_id}/modules")
async def add_module(account_id: str, data: ModuleAdd):
    """Добавить модуль к аккаунту."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    module = await core.add_module_to_account(
        account_id=account_id,
        module_name=data.module_name,
        config=data.config,
    )
    
    if not module:
        raise HTTPException(400, f"Failed to add module {data.module_name}")
    
    return {
        "status": "added",
        "module": data.module_name,
        "account_id": account_id,
    }


@app.get("/api/accounts/{account_id}/modules/{module_name}")
async def get_module_config(account_id: str, module_name: str):
    """Получить конфиг модуля."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    module = core.get_account_module(account_id, module_name)
    if not module:
        raise HTTPException(404, f"Module {module_name} not found")
    
    return {
        "name": module_name,
        "config": module.config,
        "storage_path": str(module.storage.path),
    }


@app.put("/api/accounts/{account_id}/modules/{module_name}")
async def update_module_config(account_id: str, module_name: str, data: ModuleConfigUpdate):
    """Обновить конфиг модуля."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    module = core.get_account_module(account_id, module_name)
    if not module:
        raise HTTPException(404, f"Module {module_name} not found")
    
    module.storage.save_config(data.config)
    
    return {
        "status": "updated",
        "module": module_name,
        "config": data.config,
    }


@app.get("/api/modules/available")
async def list_available_modules():
    """Список доступных классов модулей."""
    from core.module import list_module_classes
    
    return {
        "modules": list(list_module_classes().keys())
    }


# ========== Account Data (Chats, Orders, Balance) ==========

@app.get("/api/accounts/{account_id}/chats")
async def get_account_chats(account_id: str, update: bool = True):
    """
    Получить список чатов аккаунта.
    
    Args:
        update: Запросить актуальные данные с FunPay (по умолчанию True)
    """
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    runtime = core.get_runtime(account_id)
    if not runtime:
        raise HTTPException(404, f"Account {account_id} not found")
    
    if not runtime.is_initialized:
        raise HTTPException(400, "Account not initialized")
    
    try:
        chats_dict = await runtime.get_chats(update=update)
        
        chats = [
            {
                "chat_id": chat_id,
                "name": getattr(chat, "name", str(chat_id)),
                "last_message": getattr(chat, "last_message_text", ""),
                "unread": getattr(chat, "unread", False),
                "media_url": getattr(chat, "media_url", None),
            }
            for chat_id, chat in chats_dict.items()
        ]
        
        return {"chats": chats, "total": len(chats)}
    except Exception as e:
        logger.error(f"Failed to get chats for {account_id}: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/accounts/{account_id}/chats/{chat_id}")
async def get_chat_details(account_id: str, chat_id: int):
    """Получить детали чата и историю сообщений."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    result = await core.execute(
        account_id,
        Command(command_type="get_chat", params={"chat_id": chat_id})
    )
    
    if not result.success:
        raise HTTPException(500, result.error or "Failed to get chat")
    
    chat = result.data
    return {
        "id": chat_id,
        "name": getattr(chat, "name", str(chat_id)),
        "messages": serialize_messages(getattr(chat, "messages", [])),
    }


@app.get("/api/accounts/{account_id}/chats/{chat_id}/history")
async def get_chat_history(account_id: str, chat_id: int, last_message_id: int = 99999999999999):
    """Получить историю сообщений чата."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    result = await core.execute(
        account_id,
        Command(command_type="get_chat_history", params={
            "chat_id": chat_id,
            "last_message_id": last_message_id,
        })
    )
    
    if not result.success:
        raise HTTPException(500, result.error or "Failed to get chat history")
    
    messages = result.data or []
    return {
        "chat_id": chat_id,
        "messages": serialize_messages(messages),
        "count": len(messages),
    }


@app.get("/api/accounts/{account_id}/orders")
async def get_account_orders(
    account_id: str,
    include_paid: bool = True,
    include_closed: bool = True,
    include_refunded: bool = True,
):
    """
    Получить список заказов (продаж) аккаунта.
    Запрашивает напрямую с FunPay через get_sells().
    """
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    runtime = core.get_runtime(account_id)
    if not runtime:
        raise HTTPException(404, f"Account {account_id} not found")
    
    if not runtime.is_initialized:
        raise HTTPException(400, "Account not initialized")
    
    try:
        # Запрашиваем заказы через команду GET_SELLS
        result = await core.execute(
            account_id,
            Command(command_type="get_sells", params={
                "include_paid": include_paid,
                "include_closed": include_closed,
                "include_refunded": include_refunded,
            })
        )
        
        if not result.success:
            raise HTTPException(500, result.error or "Failed to get orders")
        
        # get_sells возвращает tuple (next_order_id, list[OrderShortcut])
        next_order_id, orders_list = result.data
        
        orders = [serialize_order_shortcut(order) for order in orders_list]
        
        return {
            "orders": orders, 
            "total": len(orders),
            "next_order_id": next_order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get orders for {account_id}: {e}")
        raise HTTPException(500, str(e))


@app.get("/api/accounts/{account_id}/order-tags")
async def get_order_tags(account_id: str):
    """
    Собирает теги заказов со всех модулей аккаунта.

    Каждый модуль может пометить заказы своей мета-информацией
    (название модуля, игра, тип услуги и т.д.).

    Сначала загружает список заказов (get_sells) и передаёт его в модули,
    чтобы модули могли тегировать заказы по описанию (lot_pattern matching).
    """
    if not core:
        raise HTTPException(503, "Core not initialized")

    modules = core.get_account_modules(account_id)
    if not modules:
        return {"tags": {}, "modules": [], "games": {}}

    # Fetch orders once — pass to all modules for description-based matching
    orders_list: list[dict] | None = None
    runtime = core.get_runtime(account_id)
    if runtime and runtime.is_initialized:
        try:
            result = await core.execute(
                account_id,
                Command(command_type="get_sells", params={}),
            )
            if result.success and result.data:
                _, raw_orders = result.data
                orders_list = [serialize_order_shortcut(o) for o in raw_orders]
        except Exception as e:
            logger.debug(f"get_order_tags: orders fetch failed for {account_id}: {e}")

    all_tags: dict[str, dict] = {}
    module_names: list[str] = []
    games_by_module: dict[str, list[dict]] = {}

    for mod_name, mod_instance in modules.items():
        try:
            tags = await mod_instance.get_order_tags(orders=orders_list)
        except TypeError:
            # Module doesn't accept orders parameter (old signature)
            tags = await mod_instance.get_order_tags()
        except Exception as e:
            logger.warning(f"get_order_tags failed for {mod_name}: {e}")
            continue

        if not tags:
            continue

        module_names.append(mod_name)

        # Collect unique games per module
        seen_games: set[str] = set()
        for order_id, info in tags.items():
            all_tags[order_id] = info
            gid = info.get("game_id")
            if gid:
                seen_games.add(gid)

        if seen_games:
            games_by_module[mod_name] = sorted(seen_games)

    return {
        "tags": all_tags,
        "modules": module_names,
        "games": games_by_module,
    }


@app.get("/api/accounts/{account_id}/orders/{order_id}")
async def get_order_details(account_id: str, order_id: str):
    """Получить детали заказа."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    result = await core.execute(
        account_id,
        Command(command_type="get_order", params={"order_id": order_id})
    )
    
    if not result.success:
        raise HTTPException(500, result.error or "Failed to get order")
    
    order = result.data
    return serialize_order(order)


@app.get("/api/accounts/{account_id}/balance")
async def get_account_balance(account_id: str):
    """Получить баланс аккаунта."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    result = await core.execute(
        account_id,
        Command(command_type="get_balance", params={})
    )
    
    if not result.success:
        raise HTTPException(500, result.error or "Failed to get balance")
    
    balance = result.data
    return {
        "total_rub": getattr(balance, "total_rub", 0.0),
        "available_rub": getattr(balance, "available_rub", 0.0),
        "total_usd": getattr(balance, "total_usd", 0.0),
        "available_usd": getattr(balance, "available_usd", 0.0),
        "total_eur": getattr(balance, "total_eur", 0.0),
        "available_eur": getattr(balance, "available_eur", 0.0),
    }


@app.post("/api/accounts/{account_id}/chats/{chat_id}/send")
async def send_message(account_id: str, chat_id: int, body: SendMessageBody):
    """Отправить сообщение в чат."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    result = await core.execute(
        account_id,
        Command(command_type="send_message", params={
            "chat_id": chat_id,
            "text": body.text,
        })
    )
    
    if not result.success:
        raise HTTPException(500, result.error or "Failed to send message")
    
    return {"status": "sent", "chat_id": chat_id}


@app.post("/api/accounts/{account_id}/orders/{order_id}/refund")
async def refund_order(account_id: str, order_id: str):
    """Вернуть средства по заказу."""
    if not core:
        raise HTTPException(503, "Core not initialized")
    
    result = await core.execute(
        account_id,
        Command(command_type="refund", params={"order_id": order_id})
    )
    
    if not result.success:
        raise HTTPException(500, result.error or "Failed to refund order")
    
    return {"status": "refunded", "order_id": order_id}


# ========== Run ==========

if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
