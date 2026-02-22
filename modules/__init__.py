# -*- coding: utf-8 -*-
"""
Opium Modules - авто-обнаружение пользовательских модулей.

Все подпапки modules/*/ импортируются автоматически при старте.
Это активирует @register_module_class декораторы.

Добавление нового модуля:
    1. Создать папку modules/my_module/
    2. В __init__.py импортировать класс модуля (с @register_module_class)
    3. Готово — Core подхватит автоматически.
"""

import importlib
import logging
import pkgutil
from pathlib import Path

logger = logging.getLogger("opium.modules")

# Auto-discover: import every sub-package in modules/
# This triggers @register_module_class decorators in each module's __init__.py
_pkg_path = str(Path(__file__).parent)

for _finder, _modname, _ispkg in pkgutil.iter_modules([_pkg_path]):
    if not _ispkg:
        continue
    try:
        importlib.import_module(f"modules.{_modname}")
        logger.debug(f"Auto-discovered module: {_modname}")
    except Exception as _e:
        logger.error(f"Failed to load module '{_modname}': {_e}")
