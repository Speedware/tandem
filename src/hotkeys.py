from __future__ import annotations

from typing import Dict, Optional, Tuple

import winapi as w

Hotkey = Tuple[int, int]

ACTIONS = {
    "toggle": "Запуск / остановка зеркала",
}

_MODIFIER_KEYS = {
    w.VK_SHIFT: w.MOD_SHIFT, w.VK_LSHIFT: w.MOD_SHIFT, w.VK_RSHIFT: w.MOD_SHIFT,
    w.VK_CONTROL: w.MOD_CONTROL, w.VK_LCONTROL: w.MOD_CONTROL, w.VK_RCONTROL: w.MOD_CONTROL,
    w.VK_MENU: w.MOD_ALT, w.VK_LMENU: w.MOD_ALT, w.VK_RMENU: w.MOD_ALT,
    w.VK_LWIN: w.MOD_WIN, w.VK_RWIN: w.MOD_WIN,
}

_STANDALONE_KEYS = set(range(0x70, 0x88)) | {0x13, 0x91}

_NAMES = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x13: "Pause", 0x14: "CapsLock",
    0x1B: "Esc", 0x20: "Space", 0x21: "PageUp", 0x22: "PageDown", 0x23: "End",
    0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2C: "PrintScreen", 0x2D: "Insert", 0x2E: "Delete",
    0x6A: "Num *", 0x6B: "Num +", 0x6D: "Num -", 0x6E: "Num .", 0x6F: "Num /",
    0x90: "NumLock", 0x91: "ScrollLock",
}


def is_modifier(vk: int) -> bool:
    return vk in _MODIFIER_KEYS


def pressed_modifiers() -> int:
    mods = 0
    for vk, mod in ((w.VK_CONTROL, w.MOD_CONTROL), (w.VK_MENU, w.MOD_ALT), (w.VK_SHIFT, w.MOD_SHIFT),
                    (w.VK_LWIN, w.MOD_WIN), (w.VK_RWIN, w.MOD_WIN)):
        if w.GetKeyState(vk) & 0x8000:
            mods |= mod
    return mods


def is_allowed(hotkey: Hotkey) -> bool:
    mods, vk = hotkey
    if not vk or is_modifier(vk):
        return False
    return bool(mods & ~w.MOD_SHIFT) or vk in _STANDALONE_KEYS


def key_name(vk: int) -> str:
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    if 0x60 <= vk <= 0x69:
        return f"Num {vk - 0x60}"
    if vk in _NAMES:
        return _NAMES[vk]
    char = w.MapVirtualKeyW(vk, w.MAPVK_VK_TO_CHAR) & 0x7FFF
    return chr(char).upper() if char else f"VK {vk:#04x}"


def modifiers_text(mods: int) -> str:
    parts = [name for mod, name in ((w.MOD_CONTROL, "Ctrl"), (w.MOD_ALT, "Alt"),
                                    (w.MOD_SHIFT, "Shift"), (w.MOD_WIN, "Win")) if mods & mod]
    return "".join(p + "+" for p in parts)


def format_hotkey(hotkey: Optional[Hotkey]) -> str:
    if not hotkey:
        return "не задано"
    mods, vk = hotkey
    return modifiers_text(mods) + key_name(vk)


def from_settings(raw) -> Dict[str, Optional[Hotkey]]:
    result: Dict[str, Optional[Hotkey]] = {action: None for action in ACTIONS}
    if not isinstance(raw, dict):
        return result
    for action in ACTIONS:
        value = raw.get(action)
        if isinstance(value, dict):
            mods, vk = value.get("mods"), value.get("vk")
            if isinstance(mods, int) and isinstance(vk, int) and is_allowed((mods, vk)):
                result[action] = (mods, vk)
    return result


def to_settings(hotkeys: Dict[str, Optional[Hotkey]]) -> dict:
    return {action: ({"mods": hk[0], "vk": hk[1]} if hk else None) for action, hk in hotkeys.items()}
