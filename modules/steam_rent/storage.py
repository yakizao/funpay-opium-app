# -*- coding: utf-8 -*-
"""
Steam Rent - Storage.

Обёртка над ModuleStorage для типизированного доступа к данным.

ФАЙЛЫ (изолированы друг от друга):
- config.json: только настройки модуля (change_password, kick_devices, etc)
- games.json: список игр
- lot_mappings.json: привязки лотов FunPay к играм
- steam_accounts.json: Steam аккаунты
- rentals.json: история и активные аренды
- pending.json: заказы, ожидающие выбора пользователя

Каждый файл сохраняется независимо - изменение одного не затрагивает другие.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from .models import (
    Game, LotMapping, SteamAccount, Rental, PendingOrder, PendingReview,
    AccountStatus, RentalStatus,
    game_from_dict, lot_mapping_from_dict, 
    steam_account_from_dict, rental_from_dict, pending_order_from_dict,
    pending_review_from_dict,
    to_dict,
)

if TYPE_CHECKING:
    from core.storage import ModuleStorage


logger = logging.getLogger("opium.steam_rent.storage")


# Имена файлов
CONFIG_FILE = "config.json"
GAMES_FILE = "games.json"
LOT_MAPPINGS_FILE = "lot_mappings.json"
STEAM_ACCOUNTS_FILE = "steam_accounts.json"
RENTALS_FILE = "rentals.json"
PENDING_FILE = "pending.json"
PENDING_REVIEWS_FILE = "pending_reviews.json"
MESSAGES_FILE = "messages.json"


class SteamRentStorage:
    """
    Типизированное хранилище данных модуля Steam Rent.
    
    Использует ModuleStorage (accounts/{account_id}/modules/steam_rent/).
    
    ВАЖНО: Каждая категория данных хранится в отдельном файле.
    Это предотвращает потерю данных при частичной записи.
    """
    
    def __init__(self, module_storage: "ModuleStorage") -> None:
        self._storage = module_storage
        self._cache_games: list[Game] | None = None
        self._cache_lot_mappings: list[LotMapping] | None = None
        self._cache_steam_accounts: list[SteamAccount] | None = None
        self._cache_rentals: list[Rental] | None = None
        self._cache_pending: list[PendingOrder] | None = None
        self._cache_pending_reviews: list[PendingReview] | None = None
        self._cache_messages: dict[str, str] | None = None
    
    def get_config(self) -> dict[str, object]:
        """Returns module config (config.json) - только настройки."""
        return self._storage.config
    
    # =========================================================================
    # GENERIC HELPERS (reduce CRUD boilerplate)
    # =========================================================================

    def _load_collection(
        self,
        filename: str,
        json_key: str,
        from_dict_fn: Callable[[dict[str, Any]], Any],
        *,
        migrate_key: str | None = None,
    ) -> list:
        """
        Load a list of dataclasses from a JSON file.
        
        If the file doesn't exist and migrate_key is set, attempts migration
        from config.json (backward compat with pre-split storage).
        """
        data = self._storage.read_json(filename)
        if data is None:
            if migrate_key:
                old_data = self._storage.config.get(migrate_key, [])
                if old_data:
                    logger.info(f"Migrating {len(old_data)} {json_key} from config.json to {filename}")
                    items = [from_dict_fn(d) for d in old_data]
                    self._save_collection(items, json_key, filename)
                    return items
            return []
        items = [from_dict_fn(d) for d in data.get(json_key, [])]
        logger.debug(f"Loaded {len(items)} {json_key} from {filename}")
        return items

    def _save_collection(self, items: list | None, json_key: str, filename: str) -> None:
        """Serialize a list of dataclasses and write to a JSON file."""
        data = {json_key: [to_dict(item) for item in (items or [])]}
        self._storage.write_json(filename, data)
        logger.debug(f"Saved {len(items or [])} {json_key} to {filename}")
    
    # =========================================================================
    # GAMES - games.json
    # =========================================================================
    
    def get_games(self) -> list[Game]:
        """Возвращает список игр из games.json."""
        if self._cache_games is None:
            self._cache_games = self._load_collection(
                GAMES_FILE, "games", game_from_dict, migrate_key="games"
            )
        return self._cache_games
    
    def get_game(self, game_id: str) -> Game | None:
        """Находит игру по ID."""
        for game in self.get_games():
            if game.game_id == game_id:
                return game
        return None
    
    def find_game_by_alias(self, query: str) -> Game | None:
        """Находит игру по алиасу (для команд пользователя)."""
        for game in self.get_games():
            if game.matches_alias(query):
                return game
        return None
    
    def add_game(self, game: Game) -> None:
        """Добавляет игру."""
        games = self.get_games()
        # Проверка на дубликат
        if any(g.game_id == game.game_id for g in games):
            logger.warning(f"Game {game.game_id} already exists")
            return
        games.append(game)
        self._cache_games = games
        self._save_games()
    
    def update_game(self, game: Game) -> None:
        """Обновляет игру."""
        games = self.get_games()
        for i, g in enumerate(games):
            if g.game_id == game.game_id:
                games[i] = game
                break
        self._cache_games = games
        self._save_games()
    
    def delete_game(self, game_id: str) -> bool:
        """Удаляет игру. Возвращает True если удалена."""
        games = self.get_games()
        new_games = [g for g in games if g.game_id != game_id]
        if len(new_games) == len(games):
            return False
        self._cache_games = new_games
        self._save_games()
        return True
    
    def save_games(self, games: list[Game]) -> None:
        """Сохраняет список игр."""
        self._cache_games = games
        self._save_games()
    
    def _save_games(self) -> None:
        """Записывает games.json."""
        self._save_collection(self._cache_games, "games", GAMES_FILE)
    
    # =========================================================================
    # LOT MAPPINGS - lot_mappings.json
    # =========================================================================
    
    def get_lot_mappings(self) -> list[LotMapping]:
        """Возвращает список маппингов лотов из lot_mappings.json."""
        if self._cache_lot_mappings is None:
            self._cache_lot_mappings = self._load_collection(
                LOT_MAPPINGS_FILE, "lot_mappings", lot_mapping_from_dict, migrate_key="lot_mappings"
            )
        return self._cache_lot_mappings
    
    def find_lot_mapping(self, lot_name: str) -> LotMapping | None:
        """
        Находит маппинг по названию лота.
        
        Поиск происходит по подстроке (lot_pattern содержится в lot_name).
        Возвращает ПЕРВЫЙ подходящий маппинг.
        """
        for mapping in self.get_lot_mappings():
            if mapping.matches(lot_name):
                return mapping
        return None
    
    def add_lot_mapping(self, mapping: LotMapping) -> None:
        """Добавляет маппинг лота."""
        mappings = self.get_lot_mappings()
        mappings.append(mapping)
        self._cache_lot_mappings = mappings
        self._save_lot_mappings()
    
    def update_lot_mapping(self, index: int, mapping: LotMapping) -> None:
        """Обновляет маппинг по индексу."""
        mappings = self.get_lot_mappings()
        if 0 <= index < len(mappings):
            mappings[index] = mapping
            self._cache_lot_mappings = mappings
            self._save_lot_mappings()
    
    def delete_lot_mapping(self, index: int) -> bool:
        """Удаляет маппинг по индексу."""
        mappings = self.get_lot_mappings()
        if 0 <= index < len(mappings):
            del mappings[index]
            self._cache_lot_mappings = mappings
            self._save_lot_mappings()
            return True
        return False
    
    def save_lot_mappings(self, mappings: list[LotMapping]) -> None:
        """Сохраняет маппинги лотов."""
        self._cache_lot_mappings = mappings
        self._save_lot_mappings()
    
    def _save_lot_mappings(self) -> None:
        """Записывает lot_mappings.json."""
        self._save_collection(self._cache_lot_mappings, "lot_mappings", LOT_MAPPINGS_FILE)
    
    # =========================================================================
    # STEAM ACCOUNTS - steam_accounts.json
    # =========================================================================
    
    def get_steam_accounts(self) -> list[SteamAccount]:
        """Возвращает список Steam аккаунтов из steam_accounts.json."""
        if self._cache_steam_accounts is None:
            self._cache_steam_accounts = self._load_collection(
                STEAM_ACCOUNTS_FILE, "steam_accounts", steam_account_from_dict, migrate_key="steam_accounts"
            )
        return self._cache_steam_accounts
    
    def get_steam_account(self, account_id: str) -> SteamAccount | None:
        """Находит Steam аккаунт по ID."""
        for acc in self.get_steam_accounts():
            if acc.steam_account_id == account_id:
                return acc
        return None
    
    def find_free_account(self, game_id: str) -> SteamAccount | None:
        """
        Находит свободный аккаунт для игры.
        
        Условия:
        - status == FREE
        - game_id совпадает
        - аккаунт не заморожен
        - игра не заморожена
        """
        # Проверяем что сама игра не заморожена
        game = self.get_game(game_id)
        if game and game.frozen:
            return None
        
        for acc in self.get_steam_accounts():
            if acc.status == AccountStatus.FREE and game_id in acc.game_ids and not acc.frozen:
                return acc
        return None
    
    def add_steam_account(self, account: SteamAccount) -> None:
        """Добавляет Steam аккаунт."""
        accounts = self.get_steam_accounts()
        # Проверка на дубликат
        if any(a.steam_account_id == account.steam_account_id for a in accounts):
            logger.warning(f"Steam account {account.steam_account_id} already exists")
            return
        accounts.append(account)
        self._cache_steam_accounts = accounts
        self._save_steam_accounts()
    
    def update_steam_account(self, account: SteamAccount) -> None:
        """Обновляет Steam аккаунт в списке."""
        accounts = self.get_steam_accounts()
        for i, acc in enumerate(accounts):
            if acc.steam_account_id == account.steam_account_id:
                accounts[i] = account
                break
        self._cache_steam_accounts = accounts
        self._save_steam_accounts()
    
    def delete_steam_account(self, account_id: str) -> bool:
        """Удаляет Steam аккаунт. Возвращает True если удалён."""
        accounts = self.get_steam_accounts()
        new_accounts = [a for a in accounts if a.steam_account_id != account_id]
        if len(new_accounts) == len(accounts):
            return False
        self._cache_steam_accounts = new_accounts
        self._save_steam_accounts()
        return True
    
    def save_steam_accounts(self, accounts: list[SteamAccount]) -> None:
        """Сохраняет список Steam аккаунтов."""
        self._cache_steam_accounts = accounts
        self._save_steam_accounts()
    
    def _save_steam_accounts(self) -> None:
        """Записывает steam_accounts.json."""
        self._save_collection(self._cache_steam_accounts, "steam_accounts", STEAM_ACCOUNTS_FILE)
    
    # =========================================================================
    # RENTALS - rentals.json
    # =========================================================================
    
    def get_rentals(self) -> list[Rental]:
        """Возвращает список всех аренд из rentals.json."""
        if self._cache_rentals is None:
            self._cache_rentals = self._load_collection(
                RENTALS_FILE, "rentals", rental_from_dict
            )
        return self._cache_rentals
    
    def get_rental(self, rental_id: str) -> Rental | None:
        """Находит аренду по ID."""
        for rental in self.get_rentals():
            if rental.rental_id == rental_id:
                return rental
        return None
    
    def find_rental_by_order(self, order_id: str) -> Rental | None:
        """Находит аренду по order_id FunPay."""
        for rental in self.get_rentals():
            if rental.order_id == order_id:
                return rental
        return None
    
    def get_active_rentals(self) -> list[Rental]:
        """Возвращает список активных аренд."""
        return [r for r in self.get_rentals() if r.status == RentalStatus.ACTIVE]
    
    def get_active_rentals_for_buyer(self, buyer_id: int) -> list[Rental]:
        """
        Возвращает ВСЕ активные аренды пользователя.
        
        КРИТИЧНО: Один пользователь может иметь НЕСКОЛЬКО активных аренд!
        """
        return [
            r for r in self.get_rentals()
            if r.buyer_id == buyer_id and r.status == RentalStatus.ACTIVE
        ]
    
    def get_expired_rentals(self) -> list[Rental]:
        """Возвращает аренды, которые истекли по времени, но ещё активны."""
        return [
            r for r in self.get_rentals()
            if r.status == RentalStatus.ACTIVE and r.is_expired
        ]
    
    def add_rental(self, rental: Rental) -> None:
        """
        Добавляет новую аренду.
        
        КРИТИЧНО: НЕ перезаписывает существующие аренды!
        """
        rentals = self.get_rentals()
        # Проверяем что такой rental_id не существует
        if any(r.rental_id == rental.rental_id for r in rentals):
            logger.warning(f"Rental {rental.rental_id} already exists, skipping")
            return
        
        rentals.append(rental)
        self._cache_rentals = rentals
        self._save_rentals()
    
    def update_rental(self, rental: Rental) -> None:
        """Обновляет существующую аренду."""
        rentals = self.get_rentals()
        for i, r in enumerate(rentals):
            if r.rental_id == rental.rental_id:
                rentals[i] = rental
                break
        self._cache_rentals = rentals
        self._save_rentals()
    
    def save_rentals(self, rentals: list[Rental]) -> None:
        """Сохраняет список аренд."""
        self._cache_rentals = rentals
        self._save_rentals()
    
    # =========================================================================
    # PENDING ORDERS - pending.json
    # =========================================================================
    
    def get_pending_orders(self) -> list[PendingOrder]:
        """Возвращает список ожидающих заказов из pending.json."""
        if self._cache_pending is None:
            self._cache_pending = self._load_collection(
                PENDING_FILE, "pending", pending_order_from_dict
            )
        return self._cache_pending
    
    def find_pending_for_buyer(self, buyer_id: int, game_id: str | None = None) -> PendingOrder | None:
        """Находит pending order для покупателя (опционально по игре)."""
        for p in self.get_pending_orders():
            if p.buyer_id == buyer_id:
                if game_id is None or p.game_id == game_id:
                    return p
        return None
    
    def add_pending_order(self, pending: PendingOrder) -> None:
        """Добавляет ожидающий заказ."""
        orders = self.get_pending_orders()
        # Удаляем старый pending для этого же заказа если есть
        orders = [p for p in orders if p.order_id != pending.order_id]
        orders.append(pending)
        self._cache_pending = orders
        self._save_pending()
    
    def remove_pending_order(self, order_id: str) -> None:
        """Удаляет ожидающий заказ."""
        orders = [p for p in self.get_pending_orders() if p.order_id != order_id]
        self._cache_pending = orders
        self._save_pending()
    
    def _save_pending(self) -> None:
        """Записывает pending.json."""
        self._save_collection(self._cache_pending, "pending", PENDING_FILE)
    
    # =========================================================================
    # PENDING REVIEWS — pending_reviews.json
    # =========================================================================

    def get_pending_reviews(self) -> list[PendingReview]:
        """Возвращает список отложенных проверок отзывов."""
        if self._cache_pending_reviews is None:
            self._cache_pending_reviews = self._load_collection(
                PENDING_REVIEWS_FILE, "pending_reviews", pending_review_from_dict
            )
        return self._cache_pending_reviews

    def add_pending_review(self, review: PendingReview) -> None:
        """Добавляет отложенную проверку отзыва (upsert по order_id)."""
        reviews = self.get_pending_reviews()
        # Заменяем если уже есть для этого заказа (changed после new)
        reviews = [r for r in reviews if r.order_id != review.order_id]
        reviews.append(review)
        self._cache_pending_reviews = reviews
        self._save_pending_reviews()

    def remove_pending_review(self, order_id: str) -> None:
        """Удаляет отложенную проверку отзыва."""
        reviews = [r for r in self.get_pending_reviews() if r.order_id != order_id]
        self._cache_pending_reviews = reviews
        self._save_pending_reviews()

    def _save_pending_reviews(self) -> None:
        """Записывает pending_reviews.json."""
        self._save_collection(self._cache_pending_reviews, "pending_reviews", PENDING_REVIEWS_FILE)

    def _save_rentals(self) -> None:
        """Записывает rentals.json."""
        self._save_collection(self._cache_rentals, "rentals", RENTALS_FILE)
    
    # =========================================================================
    # MESSAGES - messages.json (user-facing text templates)
    # =========================================================================

    def get_messages(self) -> dict[str, str]:
        """Returns per-account message overrides from messages.json."""
        if self._cache_messages is None:
            data = self._storage.read_json(MESSAGES_FILE)
            self._cache_messages = data if isinstance(data, dict) else {}
            logger.debug(f"Loaded {len(self._cache_messages)} message overrides from {MESSAGES_FILE}")
        return self._cache_messages

    def save_messages(self, messages: dict[str, str]) -> None:
        """Save message overrides to messages.json."""
        self._cache_messages = messages
        self._storage.write_json(MESSAGES_FILE, messages)
        logger.debug(f"Saved {len(messages)} message overrides to {MESSAGES_FILE}")

    def invalidate_cache(self) -> None:
        """Сбрасывает кэш (для перезагрузки данных при следующем доступе)."""
        self._cache_games = None
        self._cache_lot_mappings = None
        self._cache_steam_accounts = None
        self._cache_rentals = None
        self._cache_pending = None
        self._cache_pending_reviews = None
        self._cache_messages = None
        # Сбрасываем кэш конфига в ModuleStorage
        self._storage._config_cache = None
