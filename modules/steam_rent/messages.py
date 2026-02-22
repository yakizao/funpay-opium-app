# -*- coding: utf-8 -*-
"""
Steam Rent - Configurable Message Templates.

All user-facing messages are stored here as defaults.
Per-account overrides are saved in messages.json via SteamRentStorage.

Single source of truth: DEFAULT_MESSAGES + MESSAGE_META.
Placeholders are auto-extracted from templates (no manual MESSAGE_SCHEMA).

Usage:
    from .messages import get_msg, DEFAULT_MESSAGES

    text = get_msg(storage, "rent_success", game_id="CS2", login="acc1", ...)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .storage import SteamRentStorage


# ═══════════════════════════════════════════════════════════════
# DEFAULT MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════

DEFAULT_MESSAGES: dict[str, str] = {
    # ── cmd_status ────────────────────────────────────────
    "status_no_game_arg":       "❌ Укажите игру: !статус CS2",
    "game_not_found":           "❌ Игра {game_query} не найдена. Возможно, вы ввели название игры неправильно.",
    "status_no_accounts":       "❌ Нет аккаунтов для игры {game_id}",
    "status_free":              "✅ {game_id}: {free_count} из {total_count} свободно",
    "status_all_busy":          "❌ {game_id}: все заняты\n\n{soonest_remaining}",

    # ── cmd_account / cmd_code ────────────────────────────
    "no_rentals":               "У вас нет активных аренд",
    "account_info":             "🎮 {game_id} (#{order_id})\nЛогин: {login}\nПароль: {password}\nSteam Guard: {guard_code}\nОсталось: {remaining}\nДо: {end_date}",
    "code_no_guard":            "Нет аккаунтов с Guard",
    "code_success":             "🔐 {login}: {guard_code}",
    "code_error":               "❌ {login}: ошибка генерации",

    # ── cmd_extend ────────────────────────────────────────
    "extend_no_login_arg":      "❌ Укажите логин аккаунта: !продлить Ваш_логин",
    "extend_no_pending":        "❌ Нет оплаченных заказов для продления.\n\nСначала оплатите лот на FunPay.",
    "extend_no_rental":         "❌ У вас нет активной аренды с логином '{login}'",
    "extend_success":           "✅ Аренда продлена!\n\n🎮 Логин: {login}\n⏱ Добавлено: {duration}\n📅 Осталось: {remaining}",

    # ── cmd_rent ──────────────────────────────────────────
    "rent_no_game_arg":         "❌ Укажите игру: !аренда CS2",
    "rent_no_pending":          "❌ Нет оплаченных заказов для {game_id}.\n\nСначала оплатите лот на FunPay.",
    "rent_no_free_accounts":    "❌ Нет свободных аккаунтов для {game_id}\n\n{soonest_remaining}\n\nИспользуйте !возврат для возврата средств",
    "rent_success":             "🎮 Аренда оформлена!\n\nИгра: {game_id}\nЛогин: {login}\nПароль: {password}\nSteam Guard: {guard_code}\nОсталось: {remaining}\nДо: {end_date}\n\nКоманды:\n!данные - данные аккаунта\n!код - Steam Guard код",

    # ── cmd_refund ────────────────────────────────────────
    "refund_no_pending":        "ℹ️ У вас нет заказов, по которым можно оформить возврат.\n\nВозврат доступен только для необработанных заказов.",
    "refund_success":           "✅ Возврат средств оформлен по заказам: {order_ids}\n\nСредства вернутся на ваш баланс FunPay.",

    # ── автодоставка ──────────────────────────────────────
    "delivery_existing_rental": "⚠️ У вас уже есть аренда {game_id}!\n\nЛогин: {login}\nОсталось: {remaining}\n\nВыберите действие:\n!аренда {game_id} - получить НОВЫЙ аккаунт\n!продлить {login} - продлить текущий",
    "delivery_no_accounts":     "❌ Все аккаунты для {game_id} сейчас заняты.\n\n{soonest_remaining}\n\nВы можете:\n!аренда {game_id} - попробовать позже\n!возврат - оформить возврат средств",

    # ── предупреждение об истечении ──────────────────
    "expiry_warning":           "⏰ До конца аренды {game_id} осталось {remaining}!\n\nЛогин: {login}\n\nДля продления оплатите лот на FunPay и напишите:\n!продлить {login}",

    # ── уведомление об окончании аренды ────────────────
    "rental_expired":           "⏰ Ваша аренда {game_id} завершена!\n\nЛогин: {login}\n\nСпасибо за использование нашего сервиса.",
    "rental_expired_confirm":   "📦 Заказ выполнен!\nПожалуйста, зайдите в раздел \u00abПокупки\u00bb, выберите его в списке (#{order_id}) и нажмите кнопку \u00abПодтвердить выполнение заказа\u00bb.",
    "rental_expired_review":    "⭐ Будем благодарны за отзыв к заказу #{order_id}! Положительный отзыв = бонусные часы к следующей аренде.",

    # ── составные плейсхолдеры ─────────────────────────
    "soonest_info":             "⏳ Ближайший освободится через: {soonest_time}",

}


# ═══════════════════════════════════════════════════════════════
# MESSAGE METADATA (single source of truth for UI)
# ═══════════════════════════════════════════════════════════════
# Each key: (group_id, label)
# Groups and labels used by frontend — defined here, sent via API.

_GROUPS: dict[str, tuple[str, str]] = {
    "status":       ("!статус / !status",       "сообщения при проверке доступности аккаунтов"),
    "account":      ("!данные / !account / !код", "выдача данных и кодов активных аренд"),
    "extend":       ("!продлить / !extend",      "продление аренды"),
    "rent":         ("!аренда / !rent",           "оформление новой аренды по команде"),
    "refund":       ("!возврат / !refund",        "возврат средств"),
    "delivery":     ("автодоставка",              "автоматическая отправка данных покупателю при первом сообщении"),
    "expiry":       ("истечение аренды",         "предупреждение и уведомление об окончании аренды"),
}

# key → (group_id, human label)
MESSAGE_META: dict[str, tuple[str, str]] = {
    "status_no_game_arg":       ("status",       "не указана игра"),
    "game_not_found":           ("status",       "игра не найдена"),
    "status_no_accounts":       ("status",       "нет аккаунтов для игры"),
    "status_free":              ("status",       "есть свободные"),
    "status_all_busy":          ("status",       "все заняты"),
    "soonest_info":             ("status",       "шаблон 'ближайший освободится'"),

    "no_rentals":               ("account",      "нет активных аренд"),
    "account_info":             ("account",      "информация об аккаунте"),
    "code_no_guard":            ("account",      "нет аккаунтов с Guard"),
    "code_success":             ("account",      "код успешно сгенерирован"),
    "code_error":               ("account",      "ошибка генерации кода"),

    "extend_no_login_arg":      ("extend",       "не указан логин"),
    "extend_no_pending":        ("extend",       "нет оплаченных заказов"),
    "extend_no_rental":         ("extend",       "нет аренды с таким логином"),
    "extend_success":           ("extend",       "аренда продлена"),

    "rent_no_game_arg":         ("rent",         "не указана игра"),
    "rent_no_pending":          ("rent",         "нет оплаченных заказов"),
    "rent_no_free_accounts":    ("rent",         "нет свободных аккаунтов"),
    "rent_success":             ("rent",         "аренда оформлена"),

    "refund_no_pending":        ("refund",       "нет заказов для возврата"),
    "refund_success":           ("refund",       "возврат оформлен"),

    "delivery_existing_rental": ("delivery",     "уже есть аренда (выбор)"),
    "delivery_no_accounts":     ("delivery",     "нет свободных (ожидание)"),

    "expiry_warning":           ("expiry",       "предупреждение об истечении"),

    "rental_expired":           ("expiry",       "аренда завершена (основное)"),
    "rental_expired_confirm":   ("expiry",       "блок: подтвердите заказ"),
    "rental_expired_review":    ("expiry",       "блок: оставьте отзыв"),

}

# Example values for placeholder preview
PLACEHOLDER_EXAMPLES: dict[str, str] = {
    "game_id": "CS2", "game_query": "кс2",
    "login": "steam_user42", "password": "p@ssw0rd!",
    "guard_code": "7K3M9",
    "remaining": "2ч 15мин", "duration": "24ч",
    "end_date": "12.02.2026 18:30",
    "order_id": "ABCD1234", "order_ids": "ABCD1234, EFGH5678",
    "free_count": "3", "total_count": "5",
    "soonest_remaining": "⏳ Ближайший освободится через: 1ч 30мин",
    "soonest_time": "1ч 30мин",
}

# Human-readable docs for each placeholder (shown in UI help)
PLACEHOLDER_DOCS: dict[str, str] = {
    "game_id":           "идентификатор игры (CS2, DOTA2 и т.д.)",
    "game_query":        "текст, который ввёл покупатель в команде (может быть с опечаткой)",
    "login":             "логин Steam-аккаунта",
    "password":          "текущий пароль Steam-аккаунта",
    "guard_code":        "5-значный код Steam Guard (пусто если Guard не настроен — строка исчезнет)",
    "remaining":         "остаток времени аренды (2ч 15мин)",
    "duration":          "добавленное время при продлении (24ч)",
    "end_date":          "дата и время окончания аренды (12.02.2026 18:30)",
    "order_id":          "номер заказа FunPay",
    "order_ids":         "список номеров заказов через запятую",
    "free_count":        "количество свободных аккаунтов",
    "total_count":       "общее количество аккаунтов для игры",
    "soonest_remaining": "готовая строка из шаблона soonest_info (пусто если нет аренд — строка исчезнет). Ставить ТОЛЬКО на отдельную строку!",
    "soonest_time":      "время до ближайшего освобождения (1ч 30мин), используется внутри шаблона soonest_info",
}


# ═══════════════════════════════════════════════════════════════
# AUTO-EXTRACTED SCHEMA (replaces old manual MESSAGE_SCHEMA)
# ═══════════════════════════════════════════════════════════════

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _extract_placeholders(template: str) -> list[str]:
    """Extract unique {placeholder} names from a template string, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(template):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


# Pre-computed schema (auto-generated from DEFAULT_MESSAGES)
MESSAGE_SCHEMA: dict[str, list[str]] = {
    key: _extract_placeholders(tpl) for key, tpl in DEFAULT_MESSAGES.items()
}


def build_api_response(overrides: dict[str, str]) -> dict[str, Any]:
    """
    Build the full /messages API response.
    
    Single function so api_router doesn't assemble it manually.
    Returns: { messages, defaults, schema, meta, groups, examples }
    
    Overrides with unknown placeholders are marked stale in meta.
    """
    # Drop keys that don't exist in defaults (dead overrides)
    clean_overrides = {k: v for k, v in overrides.items() if k in DEFAULT_MESSAGES}
    merged = {key: clean_overrides.get(key, default) for key, default in DEFAULT_MESSAGES.items()}

    # Build groups list (ordered, with keys)
    seen_groups: list[str] = []
    groups: list[dict[str, Any]] = []
    for key in DEFAULT_MESSAGES:
        group_id = MESSAGE_META[key][0]
        if group_id not in seen_groups:
            seen_groups.append(group_id)
            label, desc = _GROUPS[group_id]
            groups.append({
                "id": group_id,
                "label": label,
                "description": desc,
                "keys": [k for k, (g, _) in MESSAGE_META.items() if g == group_id],
            })

    # Build meta: key → { label, placeholders, examples, stale? }
    meta: dict[str, dict[str, Any]] = {}
    for key, (_, label) in MESSAGE_META.items():
        phs = MESSAGE_SCHEMA.get(key, [])
        entry: dict[str, Any] = {
            "label": label,
            "placeholders": phs,
            "examples": {p: PLACEHOLDER_EXAMPLES.get(p, "...") for p in phs},
        }
        # Detect stale overrides: custom template uses unknown placeholders
        if key in clean_overrides:
            override_phs = set(_extract_placeholders(clean_overrides[key]))
            valid_phs = set(phs)
            unknown = override_phs - valid_phs
            if unknown:
                entry["stale"] = True
                entry["unknown_placeholders"] = sorted(unknown)
        meta[key] = entry

    return {
        "messages": merged,
        "defaults": DEFAULT_MESSAGES,
        "groups": groups,
        "meta": meta,
        "placeholder_docs": PLACEHOLDER_DOCS,
    }


def _strip_empty_placeholder_lines(rendered: str, template: str, kwargs: dict[str, Any]) -> str:
    """Strip lines where ALL placeholders resolved to empty strings.

    Compares rendered output against the original template line-by-line.
    If a template line contains only placeholders that mapped to '',
    the corresponding rendered line is removed.
    """
    empty_keys = {k for k, v in kwargs.items() if str(v) == ""}
    if not empty_keys:
        return rendered

    tpl_lines = template.split("\n")
    rnd_lines = rendered.split("\n")
    if len(tpl_lines) != len(rnd_lines):
        return rendered

    result: list[str] = []
    for tpl_line, rnd_line in zip(tpl_lines, rnd_lines):
        phs = set(_PLACEHOLDER_RE.findall(tpl_line))
        if phs and phs.issubset(empty_keys):
            continue  # all placeholders on this line are empty → skip
        result.append(rnd_line)

    text = "\n".join(result)
    # collapse triple+ newlines left after stripping
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def get_msg(storage: "SteamRentStorage", key: str, **kwargs: Any) -> str:
    """
    Get a formatted message template.

    Loads per-account overrides from messages.json via storage.
    Falls back to DEFAULT_MESSAGES if key is missing or template is empty.

    Lines where ALL placeholders resolved to '' are auto-stripped,
    allowing conditional display (e.g. Steam Guard line disappears
    when guard_code is empty).

    Args:
        storage: SteamRentStorage instance (for per-account overrides)
        key: message template key (e.g. "rent_success")
        **kwargs: placeholder values for .format()

    Returns:
        Formatted message string
    """
    overrides = storage.get_messages()
    template = overrides.get(key) or DEFAULT_MESSAGES.get(key, "")

    if not template:
        return ""

    try:
        rendered = template.format(**kwargs)
        return _strip_empty_placeholder_lines(rendered, template, kwargs)
    except (KeyError, IndexError, ValueError):
        # Fallback to default if user template has broken placeholders
        default = DEFAULT_MESSAGES.get(key, "")
        if default and default != template:
            try:
                rendered = default.format(**kwargs)
                return _strip_empty_placeholder_lines(rendered, default, kwargs)
            except Exception:
                pass
        return template
