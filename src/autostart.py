from __future__ import annotations

import os
import sys
import winreg
from typing import Optional

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Tandem"
LEGACY_VALUE_NAME = "WinMirror"


def command() -> str:
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pythonw):
        exe = pythonw
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    return f'"{exe}" "{script}" --autostart'


def _current(name: str = VALUE_NAME) -> Optional[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _delete(key, name: str) -> None:
    try:
        winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def migrate_legacy() -> None:
    if _current(LEGACY_VALUE_NAME) is None:
        return
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        _delete(key, LEGACY_VALUE_NAME)
    set_enabled(True)


def is_enabled() -> bool:
    return _current() is not None


def ensure_current_path() -> None:
    value = _current()
    if value is not None and value != command():
        set_enabled(True)


def set_enabled(enabled: bool) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            _delete(key, VALUE_NAME)
            _delete(key, LEGACY_VALUE_NAME)
