from __future__ import annotations

import json
import logging
import os
import shutil

log = logging.getLogger(__name__)

_BASE_DIR = os.environ.get("APPDATA") or os.path.expanduser("~")
APP_DIR = os.path.join(_BASE_DIR, "Tandem")
LEGACY_SETTINGS_PATH = os.path.join(_BASE_DIR, "WinMirror", "settings.json")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
LOG_PATH = os.path.join(APP_DIR, "tandem.log")

DEFAULTS = {
    "window": None,
    "monitor": None,
    "fps": 30,
    "hide_cursor": False,
    "autostart": False,
    "hotkeys": None,
}


def _migrate_legacy() -> None:
    if os.path.exists(SETTINGS_PATH) or not os.path.exists(LEGACY_SETTINGS_PATH):
        return
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        shutil.copy2(LEGACY_SETTINGS_PATH, SETTINGS_PATH)
        log.info("Настройки перенесены из %s", LEGACY_SETTINGS_PATH)
    except OSError:
        log.exception("Не удалось перенести старые настройки")


def load() -> dict:
    _migrate_legacy()
    data = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            stored = json.load(f)
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except FileNotFoundError:
        pass
    except (OSError, ValueError):
        log.exception("Не удалось прочитать настройки, используются значения по умолчанию")
    return data


def save(data: dict) -> None:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_PATH)
    except OSError:
        log.exception("Не удалось сохранить настройки")
