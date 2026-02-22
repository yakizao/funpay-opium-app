# -*- coding: utf-8 -*-
"""
Steam Rent - Event Handlers.

Обработчики событий:
- NewOrderEvent → автовыдача аккаунта
- NewMessageEvent → команды пользователя (!status, !account) и события отзывов
- Отзывы (через message.type): бонусные часы / отзыв при изменении/удалении

ВАЖНО: События отзывов в FunPayAPI приходят как системные сообщения:
- message.type = 3 (NEW_FEEDBACK)
- message.type = 4 (FEEDBACK_CHANGED)  
- message.type = 5 (FEEDBACK_DELETED)
- message.author_id = 0
- Текст: "Покупатель Username написал/изменил/удалил отзыв к заказу #ABCD1234."
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from core import Command, OpiumEvent

from .models import (
    Rental, RentalStatus, AccountStatus, SteamAccount,
    PendingOrder, PendingReview,
    extract_order_id, format_remaining_time,
)
from . import steam
from .messages import get_msg

if TYPE_CHECKING:
    from .storage import SteamRentStorage


logger = logging.getLogger("opium.steam_rent.handlers")

# Невидимые юникодные символы, которые копируются из чата FunPay
import re
_INVISIBLE_RE = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064"
    r"\ufeff\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5"
    r"\u180e\u2000-\u200a\u202a-\u202e\u2066-\u2069\ufff9-\ufffb]"
)

def _sanitize_arg(text: str) -> str:
    """Убирает невидимые юникодные символы и лишние пробелы."""
    return _INVISIBLE_RE.sub("", text).strip()


# Message types from FunPayAPI
MESSAGE_TYPE_NEW_FEEDBACK = 3
MESSAGE_TYPE_FEEDBACK_CHANGED = 4
MESSAGE_TYPE_FEEDBACK_DELETED = 5


# =============================================================================
# NEW ORDER HANDLER
# =============================================================================

def handle_new_order(
    event: OpiumEvent,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    Обрабатывает NewOrderEvent - автовыдача аккаунта.
    
    КРИТИЧНО:
    - Игра определяется через LotMapping.lot_pattern (поиск по подстроке)
    - Запрещено парсить текст заказа
    - Запрещено угадывать игру
    
    Flow:
    1. Найти LotMapping по order.description (lot_pattern содержится в названии)
    2. Найти свободный SteamAccount для game_id
    3. Опционально: сменить пароль, кикнуть сессии
    4. Создать Rental
    5. Отправить данные покупателю
    """
    order = event.payload.get("order", {})
    order_id = order.get("id", "")
    lot_name = order.get("description", "")
    buyer_id = order.get("buyer_id", 0)
    buyer_username = order.get("buyer_username", "")
    
    if not order_id or not lot_name:
        logger.warning(f"Invalid order data: {order}")
        return []
    
    # Проверяем что заказ ещё не обработан
    existing = storage.find_rental_by_order(order_id)
    if existing:
        logger.debug(f"Order {order_id} already processed")
        return []
    
    # 1. Найти LotMapping по названию лота
    mapping = storage.find_lot_mapping(lot_name)
    if not mapping:
        logger.debug(f"No LotMapping for lot: {lot_name} — skipping (not a rental)")
        return []
    
    game = storage.get_game(mapping.game_id)
    if not game:
        logger.warning(f"Game not found: {mapping.game_id} — skipping")
        return []
    
    # ПРОВЕРКА: есть ли уже активная аренда на эту игру у покупателя?
    active_rentals = storage.get_active_rentals_for_buyer(buyer_id)
    existing_for_game = [r for r in active_rentals if r.game_id == mapping.game_id]
    
    if existing_for_game:
        # Есть активная аренда → создаём pending и спрашиваем
        pending = PendingOrder(
            order_id=order_id,
            buyer_id=buyer_id,
            buyer_username=buyer_username,
            game_id=mapping.game_id,
            rent_minutes=mapping.rent_minutes,
            bonus_minutes=mapping.bonus_minutes,
            min_rating_for_bonus=mapping.min_rating_for_bonus,
            chat_id=0,  # chat_id неизвестен из new_order (buyer_id ≠ chat_id)
            chat_name=buyer_username,
            created_at=datetime.now().isoformat(),
        )
        storage.add_pending_order(pending)
        
        logger.info(f"[PENDING] Order {order_id} for {buyer_username}: existing rental, asking for choice")
        
        # Сообщение будет отправлено при первом сообщении покупателя
        # (handle_new_message → _deliver_pending_rentals), т.к. buyer_id ≠ chat_id
        return []
    
    # 2. Найти свободный аккаунт
    account = storage.find_free_account(mapping.game_id)
    if not account:
        logger.warning(f"No free accounts for game: {mapping.game_id}, order {order_id}")
        # Создаём pending чтобы покупатель мог получить аккаунт позже или возврат
        pending = PendingOrder(
            order_id=order_id,
            buyer_id=buyer_id,
            buyer_username=buyer_username,
            game_id=mapping.game_id,
            rent_minutes=mapping.rent_minutes,
            bonus_minutes=mapping.bonus_minutes,
            min_rating_for_bonus=mapping.min_rating_for_bonus,
            chat_id=0,  # chat_id неизвестен из new_order (buyer_id ≠ chat_id)
            chat_name=buyer_username,
            created_at=datetime.now().isoformat(),
        )
        storage.add_pending_order(pending)
        
        # Сообщение будет отправлено при первом сообщении покупателя
        return []
    
    # Смена пароля / кик устройств - ТОЛЬКО после окончания аренды (handle_rental_expired)
    
    # 3. Создать Rental
    now = datetime.now()
    end_time = now + timedelta(minutes=mapping.rent_minutes)
    
    rental = Rental(
        rental_id=str(uuid.uuid4()),
        order_id=order_id,
        buyer_id=buyer_id,
        buyer_username=buyer_username,
        game_id=mapping.game_id,
        steam_account_id=account.steam_account_id,
        start_time=now.isoformat(),
        end_time=end_time.isoformat(),
        entitled_bonus_minutes=mapping.bonus_minutes,
        min_rating_for_bonus=mapping.min_rating_for_bonus,
        delivered_login=account.login,
        delivered_password=account.password,
        delivery_pending=True,  # Данные будут отправлены при первом сообщении покупателя
    )
    
    # Обновляем статус аккаунта
    account.status = AccountStatus.RENTED
    storage.update_steam_account(account)
    storage.add_rental(rental)
    
    logger.info(
        f"[RENTAL] Created: order={order_id}, game={game.game_id}, "
        f"account={account.login}, buyer={buyer_username}, duration={mapping.rent_minutes}min "
        f"(delivery pending - waiting for buyer message)"
    )
    
    # НЕ отправляем сообщение здесь!
    # В new_order нет chat_id (только buyer_id, который != chat_id в FunPay).
    # Данные будут отправлены автоматически при первом сообщении покупателя
    # (handle_new_message → _deliver_pending_rentals), когда мы получим
    # настоящий chat_id из NewMessageEvent.
    
    return []


# =============================================================================
# MESSAGE HANDLER (Commands + Reviews)
# =============================================================================

def handle_new_message(
    event: OpiumEvent,
    storage: "SteamRentStorage",
    account_id: str,
) -> list[Command]:
    """
    Обрабатывает NewMessageEvent:
    1. Системные сообщения об отзывах (message.type 3/4/5)
    2. Команды пользователя (!status, !account)
    
    КРИТИЧНО: Один пользователь может иметь НЕСКОЛЬКО активных аренд!
    """
    message = event.payload.get("message", {})
    
    if not message:
        return []
    
    # Извлекаем все поля сообщения ДО любых проверок
    author_id = message.get("author_id", 0)
    fp_user_id = event.payload.get("fp_user_id")
    msg_type = message.get("type", 0)
    text = message.get("text", "") or ""
    chat_id = message.get("chat_id")
    chat_name = message.get("chat_name", "")
    
    logger.debug(
        f"Processing message: chat={chat_id}, author_id={author_id}, "
        f"type={msg_type}, text=\"{text[:60]}{'...' if len(text) > 60 else ''}\""
    )
    
    # Авто-доставка: при ЛЮБОМ сообщении в чате (включая собственные!)
    # Это критично: NewOrderEvent и NewMessageEvent (от бота) часто приходят
    # в одном батче — delivery_pending должен сработать даже на своём сообщении.
    delivery_commands = _deliver_pending_rentals(author_id, chat_id, chat_name, storage)
    
    # Игнорируем собственные сообщения для дальнейшей обработки
    # (команды, отзывы), но delivery уже выполнен выше
    if message.get("by_bot") or (fp_user_id and author_id == fp_user_id):
        logger.debug(f"Ignoring own message in chat {chat_id} (author_id={author_id}), delivery_commands={len(delivery_commands)}")
        return delivery_commands
    
    # Системные сообщения (отзывы)
    if author_id == 0:
        logger.debug(f"System message (type={msg_type}): routing to review handler")
        return delivery_commands + handle_review_message(msg_type, text, storage)
    
    # Команды пользователя
    if text.startswith("!"):
        logger.info(
            f"User command from {chat_name} (id={author_id}): \"{text[:80]}\""
        )
        return delivery_commands + handle_user_command(text, author_id, chat_id, chat_name, storage)
    
    return delivery_commands


def handle_review_message(
    msg_type: int,
    text: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    Обрабатывает системные сообщения об отзывах.
    
    - NEW_FEEDBACK (3): сохранить PendingReview → планировщик проверит рейтинг
    - FEEDBACK_CHANGED (4): сохранить PendingReview → планировщик пересчитает бонус
    - FEEDBACK_DELETED (5): убрать бонусные часы немедленно
    
    FunPay НЕ передаёт кол-во звёзд в системном сообщении.
    Рейтинг можно узнать только через get_order() → order.review.stars.
    Поэтому для NEW/CHANGED создаём PendingReview, а планировщик
    вызывает get_order и сверяет stars с min_rating_for_bonus.
    """
    # Только события отзывов
    if msg_type not in (MESSAGE_TYPE_NEW_FEEDBACK, MESSAGE_TYPE_FEEDBACK_CHANGED, MESSAGE_TYPE_FEEDBACK_DELETED):
        return []
    
    order_id = extract_order_id(text)
    if not order_id:
        logger.debug(f"Could not extract order_id from: {text}")
        return []
    
    rental = storage.find_rental_by_order(order_id)
    if not rental or rental.status != RentalStatus.ACTIVE:
        logger.debug(f"No active rental for order {order_id}")
        return []
    
    if msg_type in (MESSAGE_TYPE_NEW_FEEDBACK, MESSAGE_TYPE_FEEDBACK_CHANGED):
        # Создаём PendingReview — планировщик проверит рейтинг через get_order
        pending = PendingReview(
            order_id=order_id,
            rental_id=rental.rental_id,
            review_type=msg_type,
            created_at=datetime.now().isoformat(),
        )
        storage.add_pending_review(pending)
        action = "new" if msg_type == MESSAGE_TYPE_NEW_FEEDBACK else "changed"
        logger.info(f"[REVIEW] {action} for order {order_id} → pending rating check")
    
    elif msg_type == MESSAGE_TYPE_FEEDBACK_DELETED:
        # Отзыв удалён — убираем бонус немедленно (не нужен get_order)
        storage.remove_pending_review(order_id)  # на случай если ещё в очереди
        if rental.bonus_minutes > 0:
            actual_bonus = rental.bonus_minutes
            rental.remove_bonus_minutes(actual_bonus)
            storage.update_rental(rental)
            logger.info(f"[BONUS] -{actual_bonus}min for rental {rental.rental_id} (order {order_id})")
    
    return []


def resolve_pending_review(
    order_id: str,
    review_stars: int | None,
    review_type: int,
    storage: "SteamRentStorage",
) -> None:
    """
    Обрабатывает отложенный отзыв после получения данных от get_order.
    
    Вызывается планировщиком, когда get_order вернул order с review.stars.
    
    Логика:
    - NEW_FEEDBACK (3): если stars >= min_rating_for_bonus → добавить бонус
    - FEEDBACK_CHANGED (4): пересчитать бонус (добавить/убрать в зависимости от рейтинга)
    
    Args:
        order_id: ID заказа FunPay
        review_stars: Кол-во звёзд (None если отзыв удалён/не найден)
        review_type: Тип отзыва (3=new, 4=changed)
        storage: Хранилище
    """
    rental = storage.find_rental_by_order(order_id)
    if not rental or rental.status != RentalStatus.ACTIVE:
        logger.debug(f"[REVIEW] No active rental for order {order_id}, skipping")
        storage.remove_pending_review(order_id)
        return
    
    # Бонус и min_rating хранятся на самой аренде (из LotMapping при создании)
    bonus_minutes = rental.entitled_bonus_minutes
    min_rating = rental.min_rating_for_bonus
    
    if bonus_minutes <= 0:
        logger.debug(f"[REVIEW] No bonus configured for game {rental.game_id}")
        storage.remove_pending_review(order_id)
        return
    
    if review_stars is None:
        # Отзыв не найден (удалён между event и get_order) — убираем бонус
        if rental.bonus_minutes > 0:
            actual_bonus = rental.bonus_minutes
            rental.remove_bonus_minutes(actual_bonus)
            storage.update_rental(rental)
            logger.info(f"[BONUS] -{actual_bonus}min for rental {rental.rental_id} (no review found)")
        storage.remove_pending_review(order_id)
        return
    
    rating_ok = review_stars >= min_rating
    
    if review_type == MESSAGE_TYPE_NEW_FEEDBACK:
        # Новый отзыв
        if rating_ok and rental.bonus_minutes == 0:
            rental.add_bonus_minutes(bonus_minutes)
            storage.update_rental(rental)
            logger.info(
                f"[BONUS] +{bonus_minutes}min for rental {rental.rental_id} "
                f"(order {order_id}, stars={review_stars}, min={min_rating})"
            )
        elif not rating_ok:
            logger.info(
                f"[REVIEW] No bonus for order {order_id}: "
                f"stars={review_stars} < min_rating={min_rating}"
            )
    
    elif review_type == MESSAGE_TYPE_FEEDBACK_CHANGED:
        # Отзыв изменён — пересчитываем
        if rating_ok and rental.bonus_minutes == 0:
            # Рейтинг поднялся до порога — добавляем бонус
            rental.add_bonus_minutes(bonus_minutes)
            storage.update_rental(rental)
            logger.info(
                f"[BONUS] +{bonus_minutes}min for rental {rental.rental_id} "
                f"(order {order_id}, rating raised to {review_stars})"
            )
        elif not rating_ok and rental.bonus_minutes > 0:
            # Рейтинг упал ниже порога — убираем бонус
            actual_bonus = rental.bonus_minutes
            rental.remove_bonus_minutes(actual_bonus)
            storage.update_rental(rental)
            logger.info(
                f"[BONUS] -{actual_bonus}min for rental {rental.rental_id} "
                f"(order {order_id}, rating dropped to {review_stars})"
            )
        else:
            logger.info(
                f"[REVIEW] Changed for order {order_id}, stars={review_stars}, "
                f"bonus unchanged ({rental.bonus_minutes}min)"
            )
    
    storage.remove_pending_review(order_id)


def handle_user_command(
    text: str,
    buyer_id: int,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    Обрабатывает команды пользователя.
    
    Команды:
    - !статус игра - свободность аккаунтов для игры
    - !аренда игра - выдача нового аккаунта (после оплаты)
    - !продлить логин - продление существующей аренды (после оплаты)
    - !данные - данные всех активных аккаунтов
    - !код - только Steam Guard коды
    - !возврат - инструкция по возврату
    """
    # Сбрасываем кэш чтобы подхватить изменения конфига
    storage.invalidate_cache()
    
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = _sanitize_arg(parts[1]) if len(parts) > 1 else ""
    
    logger.info(f"Parsed user command: cmd={cmd}, arg=\"{arg}\"")
    
    if cmd in ("!status", "!статус"):
        return cmd_status(buyer_id, arg, chat_id, chat_name, storage)
    
    elif cmd in ("!account", "!аккаунт", "!данные"):
        return cmd_account(buyer_id, chat_id, chat_name, storage)
    
    elif cmd in ("!code", "!код", "!guard"):
        return cmd_code(buyer_id, chat_id, chat_name, storage)
    
    elif cmd in ("!аренда", "!rent"):
        return cmd_rent(buyer_id, arg, chat_id, chat_name, storage)
    
    elif cmd in ("!продлить", "!extend"):
        return cmd_extend(buyer_id, arg, chat_id, chat_name, storage)
    
    elif cmd in ("!возврат", "!refund"):
        return cmd_refund(buyer_id, chat_id, chat_name, storage)
    
    return []


def cmd_status(
    buyer_id: int,
    game_query: str,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    !статус [игра] - показывает свободность аккаунтов для игры.
    
    Если игра указана - показывает сколько свободных аккаунтов.
    Если нет свободных - когда освободится ближайший.
    """
    if not game_query:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "status_no_game_arg"),
            "chat_name": chat_name
        })]
    
    # Ищем игру по алиасу
    game = storage.find_game_by_alias(game_query)
    
    # Резервный поиск по game_id напрямую (на случай проблем с алиасами)
    if not game:
        game = storage.get_game(game_query.lower())
    
    if not game:
        # Отладка: показываем какие игры есть
        all_games = storage.get_games()
        if all_games:
            game_list = ", ".join(g.game_id for g in all_games)
            logger.warning(f"Game '{game_query}' not found. Available: {game_list}")
        else:
            logger.warning(f"No games configured!")
        
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "game_not_found", game_query=game_query),
            "chat_name": chat_name
        })]
    
    # Считаем свободные аккаунты
    all_accounts = storage.get_steam_accounts()
    game_accounts = [a for a in all_accounts if game.game_id in a.game_ids]
    free_accounts = [a for a in game_accounts if a.status == AccountStatus.FREE]
    
    if not game_accounts:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "status_no_accounts", game_id=game.game_id),
            "chat_name": chat_name
        })]
    
    if free_accounts:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "status_free", game_id=game.game_id, free_count=len(free_accounts), total_count=len(game_accounts)),
            "chat_name": chat_name
        })]
    
    # Нет свободных - когда освободится ближайший
    soonest_remaining = _get_soonest_remaining(game.game_id, storage)
    return [Command("send_message", {
        "chat_id": chat_id,
        "text": get_msg(storage, "status_all_busy", game_id=game.game_id, soonest_remaining=soonest_remaining),
        "chat_name": chat_name
    })]


def cmd_account(
    buyer_id: int,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    !account - показывает данные ВСЕХ активных аккаунтов пользователя.
    
    ВАЖНО: Выдаёт данные для КАЖДОЙ аренды отдельно!
    """
    rentals = storage.get_active_rentals_for_buyer(buyer_id)
    
    if not rentals:
        return [Command("send_message", {"chat_id": chat_id, "text": get_msg(storage, "no_rentals"), "chat_name": chat_name})]
    
    lines: list[str] = []
    for rental in rentals:
        account = storage.get_steam_account(rental.steam_account_id)
        
        if not account:
            continue
        
        guard_code = _generate_guard_code(account)
        remaining = format_remaining_time(rental.remaining_time)
        
        text = get_msg(
            storage, "account_info",
            game_id=rental.game_id, order_id=rental.order_id,
            login=rental.delivered_login, password=rental.delivered_password,
            guard_code=guard_code, remaining=remaining,
            end_date=rental.end_datetime.strftime('%d.%m.%Y %H:%M'),
        )
        
        lines.append(text)
    
    if not lines:
        return [Command("send_message", {"chat_id": chat_id, "text": "Нет данных", "chat_name": chat_name})]
    
    return [Command("send_message", {"chat_id": chat_id, "text": "\n\n".join(lines), "chat_name": chat_name})]


def cmd_code(
    buyer_id: int,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    !код - выводит ТОЛЬКО Steam Guard коды для всех активных аренд.
    
    Быстрый доступ к кодам без лишней информации.
    """
    rentals = storage.get_active_rentals_for_buyer(buyer_id)
    
    if not rentals:
        return [Command("send_message", {"chat_id": chat_id, "text": get_msg(storage, "no_rentals"), "chat_name": chat_name})]
    
    lines: list[str] = []
    for rental in rentals:
        account = storage.get_steam_account(rental.steam_account_id)
        if not account or not account.shared_secret:
            continue
        
        guard_code = _generate_guard_code(account)
        if guard_code:
            lines.append(get_msg(storage, "code_success", login=rental.delivered_login, guard_code=guard_code))
        else:
            lines.append(get_msg(storage, "code_error", login=rental.delivered_login))
    
    if not lines:
        return [Command("send_message", {"chat_id": chat_id, "text": get_msg(storage, "code_no_guard"), "chat_name": chat_name})]
    
    return [Command("send_message", {"chat_id": chat_id, "text": "\n".join(lines), "chat_name": chat_name})]


def cmd_extend(
    buyer_id: int,
    login_arg: str,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    !продлить логин - продление существующей аренды после оплаты.
    
    Требует оплаченный pending order!
    Берёт время из pending.rent_minutes и добавляет к аренде.
    """
    if not login_arg:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "extend_no_login_arg"),
            "chat_name": chat_name
        })]
    
    login = login_arg.strip()
    
    # Ищем активную аренду с этим логином
    rentals = storage.get_active_rentals_for_buyer(buyer_id)
    target_rental = None
    for rental in rentals:
        if rental.delivered_login.lower() == login.lower():
            target_rental = rental
            break
    
    if not target_rental:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "extend_no_rental", login=login),
            "chat_name": chat_name
        })]
    
    # Ищем pending order для той же игры что и аренда
    pending = storage.find_pending_for_buyer(buyer_id, target_rental.game_id)
    if not pending:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "extend_no_pending"),
            "chat_name": chat_name
        })]
    
    # Продлеваем аренду на оплаченное время
    extend_minutes = pending.rent_minutes
    target_rental.extend_time_minutes(extend_minutes)
    storage.update_rental(target_rental)
    
    # Удаляем pending
    storage.remove_pending_order(pending.order_id)
    
    remaining = format_remaining_time(target_rental.remaining_time)
    
    logger.info(f"[EXTEND] {login} extended by {extend_minutes} min for buyer {buyer_id} (order {pending.order_id})")
    
    return [Command("send_message", {
        "chat_id": chat_id,
        "text": get_msg(storage, "extend_success", login=login, duration=_format_duration(extend_minutes), remaining=remaining),
        "chat_name": chat_name
    })]


def cmd_rent(
    buyer_id: int,
    game_arg: str,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    !аренда игра - выдача НОВОГО аккаунта после оплаты.
    
    Требует оплаченный pending order!
    Используется когда у покупателя уже есть аренда, но он хочет второй аккаунт.
    """
    if not game_arg:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "rent_no_game_arg"),
            "chat_name": chat_name
        })]
    
    # Ищем игру по алиасу
    game = storage.find_game_by_alias(game_arg)
    if not game:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "game_not_found", game_query=game_arg),
            "chat_name": chat_name
        })]
    
    # Проверяем есть ли pending order
    pending = storage.find_pending_for_buyer(buyer_id, game.game_id)
    if not pending:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "rent_no_pending", game_id=game.game_id),
            "chat_name": chat_name
        })]
    
    # Ищем свободный аккаунт
    account = storage.find_free_account(game.game_id)
    
    if not account:
        # Нет свободных - ищем когда освободится ближайший
        soonest_remaining = _get_soonest_remaining(game.game_id, storage)
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "rent_no_free_accounts", game_id=game.game_id, soonest_remaining=soonest_remaining),
            "chat_name": chat_name
        })]
    
    # Смена пароля / кик - ТОЛЬКО после окончания аренды (handle_rental_expired)
    now = datetime.now()
    end_time = now + timedelta(minutes=pending.rent_minutes)
    
    rental = Rental(
        rental_id=str(uuid.uuid4()),
        order_id=pending.order_id,
        buyer_id=buyer_id,
        buyer_username=pending.buyer_username,
        game_id=game.game_id,
        steam_account_id=account.steam_account_id,
        start_time=now.isoformat(),
        end_time=end_time.isoformat(),
        entitled_bonus_minutes=pending.bonus_minutes,
        min_rating_for_bonus=pending.min_rating_for_bonus,
        delivered_login=account.login,
        delivered_password=account.password,
        chat_id=chat_id,
        chat_name=chat_name,
    )
    
    # Обновляем статус аккаунта
    account.status = AccountStatus.RENTED
    storage.update_steam_account(account)
    storage.add_rental(rental)
    
    # Удаляем pending
    storage.remove_pending_order(pending.order_id)
    
    guard_code = _generate_guard_code(account)
    
    logger.info(f"[RENTAL] From cmd_rent: order={pending.order_id}, account={account.login}, buyer={pending.buyer_username}")
    
    message_text = get_msg(
        storage, "rent_success",
        game_id=game.game_id, login=account.login, password=account.password,
        guard_code=guard_code, remaining=format_remaining_time(rental.remaining_time),
        end_date=end_time.strftime('%d.%m.%Y %H:%M'),
    )
    
    return [Command("send_message", {
        "chat_id": chat_id,
        "text": message_text,
        "chat_name": chat_name
    })]


def cmd_refund(
    buyer_id: int,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    !возврат - возврат средств через FunPay API.
    
    Работает когда у покупателя есть pending-заказы (оплачены, но аккаунт не выдан).
    Активные аренды НЕ блокируют возврат pending-заказов.
    
    Вызывает Account.refund(order_id) через CommandType.REFUND.
    """
    # Ищем pending-заказы покупателя
    pending_orders = [p for p in storage.get_pending_orders() if p.buyer_id == buyer_id]
    
    if not pending_orders:
        return [Command("send_message", {
            "chat_id": chat_id,
            "text": get_msg(storage, "refund_no_pending"),
            "chat_name": chat_name
        })]
    
    # Оформляем возврат по каждому pending-заказу через API
    commands: list[Command] = []
    order_ids: list[str] = []
    
    for pending in pending_orders:
        order_ids.append(pending.order_id)
        commands.append(Command("refund", {"order_id": pending.order_id}))
        storage.remove_pending_order(pending.order_id)
    
    logger.info(
        f"[REFUND] User {buyer_id} requested refund for {len(order_ids)} order(s): {order_ids}"
    )
    
    orders_str = ", ".join(order_ids)
    commands.append(Command("send_message", {
        "chat_id": chat_id,
        "text": get_msg(storage, "refund_success", order_ids=orders_str),
        "chat_name": chat_name
    }))
    
    return commands


# =============================================================================
# PENDING DELIVERY (auto-send on first buyer message)
# =============================================================================

def _deliver_pending_rentals(
    buyer_id: int,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> list[Command]:
    """
    Доставляет данные аренд, ожидающих отправки, и обновляет pending orders.
    
    Вызывается из handle_new_message при получении ЛЮБОГО сообщения в чате.
    Orchestrator: resolves buyer's active rentals → delivers pending → updates pending orders.
    """
    # Resolve buyer's active rentals (buyer_id=0 → системное, ищем по chat_name)
    if buyer_id:
        rentals = storage.get_active_rentals_for_buyer(buyer_id)
    else:
        all_active = storage.get_active_rentals()
        rentals = [r for r in all_active if r.buyer_username == chat_name]
    
    commands: list[Command] = []
    
    # 1. Deliver rentals waiting for first buyer message
    for rental in rentals:
        if rental.delivery_pending:
            cmd = _deliver_single_rental(rental, chat_id, chat_name, storage)
            if cmd:
                commands.append(cmd)
    
    # 2. Update pending orders with real chat_id and notify buyer
    commands.extend(
        _notify_pending_orders(buyer_id, chat_id, chat_name, rentals, storage)
    )
    
    return commands


def _deliver_single_rental(
    rental: Rental,
    chat_id: int | str,
    chat_name: str,
    storage: "SteamRentStorage",
) -> Command | None:
    """Delivers credentials for a single rental and clears delivery_pending flag."""
    account = storage.get_steam_account(rental.steam_account_id)
    if not account:
        logger.warning(f"[DELIVERY] Account not found for rental {rental.rental_id}")
        return None
    
    guard_code = _generate_guard_code(account)
    remaining = format_remaining_time(rental.remaining_time)
    
    message_text = get_msg(
        storage, "rent_success",
        game_id=rental.game_id, login=rental.delivered_login,
        password=rental.delivered_password, guard_code=guard_code,
        remaining=remaining, end_date=rental.end_datetime.strftime('%d.%m.%Y %H:%M'),
    )
    
    # Clear flag + save chat info
    rental.delivery_pending = False
    rental.chat_id = chat_id
    rental.chat_name = chat_name
    storage.update_rental(rental)
    
    logger.info(
        f"[DELIVERY] Rental {rental.rental_id} delivered to {chat_name} "
        f"(chat_id={chat_id}, order={rental.order_id})"
    )
    
    return Command("send_message", {
        "chat_id": chat_id, "text": message_text, "chat_name": chat_name,
    })


def _notify_pending_orders(
    buyer_id: int,
    chat_id: int | str,
    chat_name: str,
    rentals: list[Rental],
    storage: "SteamRentStorage",
) -> list[Command]:
    """Updates chat_id in pending orders and sends choice notification to buyer."""
    commands: list[Command] = []
    
    for pending in storage.get_pending_orders():
        is_same_buyer = (
            (buyer_id and pending.buyer_id == buyer_id)
            or (not buyer_id and pending.buyer_username == chat_name)
        )
        if not is_same_buyer:
            continue
        if pending.chat_id != 0 and pending.chat_id != pending.buyer_id:
            continue
        
        # Update chat_id (upsert)
        pending.chat_id = chat_id
        pending.chat_name = chat_name
        storage.add_pending_order(pending)
        
        # Notify buyer about pending order
        existing_for_game = [r for r in rentals if r.game_id == pending.game_id and not r.delivery_pending]
        
        if existing_for_game:
            existing = existing_for_game[0]
            remaining = format_remaining_time(existing.remaining_time)
            commands.append(Command("send_message", {
                "chat_id": chat_id,
                "text": get_msg(
                    storage, "delivery_existing_rental",
                    game_id=pending.game_id, login=existing.delivered_login, remaining=remaining,
                ),
                "chat_name": chat_name,
            }))
        else:
            soonest_remaining = _get_soonest_remaining(pending.game_id, storage)
            commands.append(Command("send_message", {
                "chat_id": chat_id,
                "text": get_msg(
                    storage, "delivery_no_accounts",
                    game_id=pending.game_id, soonest_remaining=soonest_remaining,
                ),
                "chat_name": chat_name,
            }))
    
    return commands


def _get_soonest_remaining(game_id: str, storage: "SteamRentStorage") -> str:
    """Возвращает готовую строку о ближайшем освобождении через шаблон soonest_info.
    
    Пустая строка если нет активных аренд → строка с {soonest_remaining} исчезнет.
    """
    rentals = storage.get_active_rentals()
    game_rentals = [r for r in rentals if r.game_id == game_id]
    
    if not game_rentals:
        return ""
    
    soonest = min(game_rentals, key=lambda r: r.remaining_time)
    soonest_time = format_remaining_time(soonest.remaining_time)
    return get_msg(storage, "soonest_info", soonest_time=soonest_time)


def _format_duration(minutes: int) -> str:
    """Форматирует длительность в часы и минуты."""
    if minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        if mins > 0:
            return f"{hours}ч {mins}мин"
        return f"{hours}ч"
    return f"{minutes}мин"


def _generate_guard_code(account: SteamAccount) -> str:
    """Generates Steam Guard code for account, returns empty string on failure."""
    if not account.shared_secret:
        return ""
    try:
        return steam.generate_guard_code(account.shared_secret)
    except Exception:
        return ""


# =============================================================================
# ACCOUNT RELEASE (shared: expiry, admin terminate, etc.)
# =============================================================================

def release_account(
    account_id: str,
    storage: "SteamRentStorage",
    reason: str = "release",
) -> None:
    """
    Освобождает Steam аккаунт: смена пароля, кик сессий, статус FREE.
    
    Вызывается из:
    - handle_rental_expired (автоматическое истечение)
    - api_router.terminate_rental (ручное завершение админом)
    
    Args:
        account_id: ID Steam аккаунта в системе
        storage: хранилище
        reason: причина для логов ("expired", "terminated", etc.)
    """
    account = storage.get_steam_account(account_id)
    if not account:
        logger.warning(f"[{reason.upper()}] Account not found: {account_id}")
        return
    
    # Смена пароля (если настроено)
    if account.change_password_on_rent:
        try:
            result = steam.change_password(
                account.login,
                account.password,
                account.mafile,
                excluded_passwords=account.password_history,
            )
            if result.success and result.new_password:
                account.password_history.append(account.password)
                if len(account.password_history) > 5:
                    account.password_history = account.password_history[-5:]
                account.password = result.new_password
                logger.info(f"[{reason.upper()}] Password changed for {account.login}")
            else:
                logger.warning(f"[{reason.upper()}] Password change failed for {account.login}: {result.error}")
        except Exception as e:
            logger.error(f"[{reason.upper()}] Password change error for {account.login}: {e}")
    
    # Кик устройств (если настроено)
    if account.kick_devices_on_rent:
        try:
            kick_result = steam.kick_all_sessions(
                account.login,
                account.password,
                account.mafile,
            )
            if kick_result.success:
                logger.info(f"[{reason.upper()}] Sessions kicked for {account.login}")
            else:
                logger.warning(f"[{reason.upper()}] Session kick failed for {account.login}: {kick_result.error}")
        except Exception as e:
            logger.error(f"[{reason.upper()}] Session kick error for {account.login}: {e}")
    
    # Освобождаем
    account.status = AccountStatus.FREE
    storage.update_steam_account(account)
    logger.info(f"[{reason.upper()}] Account {account.login} freed (account_id={account_id})")


# =============================================================================
# RENTAL EXPIRY HANDLER
# =============================================================================

def handle_rental_expired(
    rental_id: str,
    storage: "SteamRentStorage",
) -> None:
    """
    Обрабатывает истечение аренды.
    
    1. Освобождает Steam аккаунт (смена пароля, кик, FREE)
    2. Обновляет статус аренды
    """
    rental = storage.get_rental(rental_id)
    if not rental:
        logger.warning(f"Rental not found: {rental_id}")
        return
    
    if rental.status != RentalStatus.ACTIVE:
        logger.debug(f"Rental {rental_id} already processed")
        return
    
    if rental.delivery_pending:
        logger.warning(
            f"[EXPIRED] Rental {rental_id} (order {rental.order_id}) expired "
            f"WITHOUT delivery to buyer {rental.buyer_username}!"
        )
    
    # Освобождаем аккаунт (смена пароля + кик + FREE)
    release_account(rental.steam_account_id, storage, reason="expired")
    
    # Обновляем статус аренды
    rental.status = RentalStatus.EXPIRED
    storage.update_rental(rental)
    
    logger.info(f"[EXPIRED] Rental {rental_id} (order {rental.order_id})")

