# -*- coding: utf-8 -*-
"""Result types for Steam operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PasswordChangeResult:
    """Результат смены пароля."""

    success: bool
    new_password: str | None = None
    error: str | None = None


@dataclass
class KickSessionsResult:
    """Результат кика сессий."""

    success: bool
    error: str | None = None
