from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes as wt
from dataclasses import dataclass
from typing import List, Optional

import winapi as w

_SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    cls: str
    pid: int
    exe_path: str

    @property
    def exe(self) -> str:
        return os.path.basename(self.exe_path).lower()

    @property
    def label(self) -> str:
        return f"{self.title}   [{self.exe or '?'}]"

    @property
    def spec(self) -> dict:
        return {"exe": self.exe, "cls": self.cls, "title": self.title}


def _window_text(hwnd) -> str:
    n = w.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    w.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    w.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _is_cloaked(hwnd) -> bool:
    val = wt.DWORD(0)
    hr = w.DwmGetWindowAttribute(hwnd, w.DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val))
    return hr == 0 and val.value != 0


def process_path(pid: int) -> str:
    h = w.OpenProcess(w.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if w.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        w.CloseHandle(h)


def _toplevel_windows() -> list:
    hwnds = []

    @w.WNDENUMPROC
    def callback(hwnd, _lparam):
        hwnds.append(hwnd)
        return True

    w.EnumWindows(callback, 0)
    return hwnds


def list_windows() -> List[WindowInfo]:
    own_pid = os.getpid()
    result = []
    for hwnd in _toplevel_windows():
        if not hwnd or not w.IsWindowVisible(hwnd):
            continue
        if w.GetWindow(hwnd, w.GW_OWNER):
            continue
        if w.GetWindowLongW(hwnd, w.GWL_EXSTYLE) & w.WS_EX_TOOLWINDOW:
            continue
        title = _window_text(hwnd).strip()
        if not title:
            continue
        cls = _class_name(hwnd)
        if cls in _SKIP_CLASSES or _is_cloaked(hwnd):
            continue
        pid = wt.DWORD(0)
        w.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            continue
        result.append(WindowInfo(hwnd, title, cls, pid.value, process_path(pid.value)))
    return result


def _title_suffix(title: str) -> str:
    idx = title.rfind(" - ")
    return title[idx:] if idx >= 0 else ""


def find_window(spec: Optional[dict], windows: Optional[List[WindowInfo]] = None) -> Optional[WindowInfo]:
    if not spec:
        return None
    exe = (spec.get("exe") or "").lower()
    cls = spec.get("cls") or ""
    title = spec.get("title") or ""
    windows = list_windows() if windows is None else windows

    if exe:
        cands = [x for x in windows if x.exe == exe and (not cls or x.cls == cls)]
    else:
        cands = [x for x in windows if x.cls == cls and x.title == title]
    if not cands:
        return None
    for x in cands:
        if x.title == title:
            return x
    suffix = _title_suffix(title)
    if suffix:
        for x in cands:
            if x.title.endswith(suffix):
                return x
    return cands[0]


@dataclass
class MonitorInfo:
    device: str
    name: str
    device_id: str
    left: int
    top: int
    right: int
    bottom: int
    primary: bool

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def number(self) -> str:
        m = re.search(r"(\d+)$", self.device)
        return m.group(1) if m else "?"

    @property
    def label(self) -> str:
        text = f"Монитор {self.number}: {self.name} — {self.width}×{self.height}"
        return text + (" (основной)" if self.primary else "")

    @property
    def spec(self) -> dict:
        return {"device": self.device, "device_id": self.device_id, "name": self.name,
                "width": self.width, "height": self.height}


def _monitor_info(hmon) -> Optional[w.MONITORINFOEXW]:
    if not hmon:
        return None
    mi = w.MONITORINFOEXW()
    mi.cbSize = ctypes.sizeof(mi)
    if not w.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        return None
    return mi


def list_monitors() -> List[MonitorInfo]:
    handles = []

    @w.MONITORENUMPROC
    def callback(hmon, _hdc, _rect, _lparam):
        handles.append(hmon)
        return True

    w.EnumDisplayMonitors(None, None, callback, 0)

    monitors = []
    for hmon in handles:
        mi = _monitor_info(hmon)
        if mi is None:
            continue
        name, device_id = "Монитор", ""
        dd = w.DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if w.EnumDisplayDevicesW(mi.szDevice, 0, ctypes.byref(dd), 0):
            name = dd.DeviceString or name
            device_id = dd.DeviceID
        r = mi.rcMonitor
        monitors.append(MonitorInfo(
            mi.szDevice, name, device_id, r.left, r.top, r.right, r.bottom,
            bool(mi.dwFlags & w.MONITORINFOF_PRIMARY),
        ))
    monitors.sort(key=lambda m: (m.left, m.top))
    return monitors


def monitor_device_of_window(hwnd) -> str:
    mi = _monitor_info(w.MonitorFromWindow(hwnd, w.MONITOR_DEFAULTTONEAREST))
    return mi.szDevice if mi else ""


def find_monitor(spec: Optional[dict], monitors: Optional[List[MonitorInfo]] = None) -> Optional[MonitorInfo]:
    if not spec:
        return None
    monitors = list_monitors() if monitors is None else monitors
    device = spec.get("device")
    device_id = spec.get("device_id")
    for m in monitors:
        if m.device == device and (not device_id or m.device_id == device_id):
            return m
    if device_id:
        same = [m for m in monitors if m.device_id == device_id]
        if len(same) == 1:
            return same[0]
    for m in monitors:
        if m.device == device:
            return m
    return None
