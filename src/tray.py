from __future__ import annotations

import ctypes
import logging
import threading
from ctypes import wintypes as wt
from typing import Callable

import winapi as w

log = logging.getLogger(__name__)

CLASS_NAME = "TandemTray"
WM_TRAY = w.WM_APP + 1
WM_SHOW_REQUEST = w.WM_APP + 2
WM_QUIT_REQUEST = w.WM_APP + 3

CMD_OPEN, CMD_TOGGLE, CMD_EXIT = 1, 2, 3


def request_show_existing() -> bool:
    hwnd = w.FindWindowW(CLASS_NAME, None)
    return bool(hwnd and w.PostMessageW(hwnd, WM_SHOW_REQUEST, 0, 0))


def request_quit_existing(timeout: float = 10.0) -> None:
    hwnd = w.FindWindowW(CLASS_NAME, None)
    if not hwnd:
        return
    pid = wt.DWORD(0)
    w.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process = w.OpenProcess(w.SYNCHRONIZE, False, pid.value)
    w.PostMessageW(hwnd, WM_QUIT_REQUEST, 0, 0)
    if process:
        w.WaitForSingleObject(process, int(timeout * 1000))
        w.CloseHandle(process)


class TrayIcon(threading.Thread):
    def __init__(self, icon_path: str, tooltip: str, on_event: Callable[[str], None]):
        super().__init__(name="tray", daemon=True)
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.on_event = on_event
        self.mirror_running = False
        self.hwnd = None
        self.hicon = None
        self._proc = w.WNDPROC(self._wndproc)
        self._taskbar_created = w.RegisterWindowMessageW("TaskbarCreated")
        self._ready = threading.Event()


    def set_tooltip(self, text: str) -> None:
        self.tooltip = text
        if self.hwnd:
            nid = self._nid(w.NIF_TIP)
            w.Shell_NotifyIconW(w.NIM_MODIFY, ctypes.byref(nid))

    def notify(self, title: str, text: str, warning: bool = False) -> None:
        if not self.hwnd:
            return
        nid = self._nid(w.NIF_INFO)
        nid.szInfoTitle = title[:63]
        nid.szInfo = text[:255]
        nid.dwInfoFlags = w.NIIF_WARNING if warning else w.NIIF_INFO
        w.Shell_NotifyIconW(w.NIM_MODIFY, ctypes.byref(nid))

    def stop(self) -> None:
        if self.hwnd:
            w.PostMessageW(self.hwnd, w.WM_CLOSE, 0, 0)

    def wait_ready(self, timeout: float = 3.0) -> None:
        self._ready.wait(timeout)


    def run(self) -> None:
        try:
            hinst = w.GetModuleHandleW(None)
            wc = w.WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(wc)
            wc.lpfnWndProc = self._proc
            wc.hInstance = hinst
            wc.lpszClassName = CLASS_NAME
            if not w.RegisterClassExW(ctypes.byref(wc)):
                err = ctypes.get_last_error()
                if err != w.ERROR_CLASS_ALREADY_EXISTS:
                    raise OSError(f"RegisterClassExW: код ошибки {err}")
            self.hwnd = w.CreateWindowExW(0, CLASS_NAME, "Tandem", 0, 0, 0, 0, 0,
                                          None, None, hinst, None)
            if not self.hwnd:
                raise OSError(f"CreateWindowExW: код ошибки {ctypes.get_last_error()}")
            cx = w.GetSystemMetrics(w.SM_CXSMICON)
            cy = w.GetSystemMetrics(w.SM_CYSMICON)
            self.hicon = w.LoadImageW(None, self.icon_path, w.IMAGE_ICON, cx, cy, w.LR_LOADFROMFILE)
            self._add()
        except Exception:
            log.exception("Не удалось создать значок в трее")
            self._ready.set()
            return
        self._ready.set()

        msg = wt.MSG()
        while w.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            w.TranslateMessage(ctypes.byref(msg))
            w.DispatchMessageW(ctypes.byref(msg))

        if self.hicon:
            w.DestroyIcon(self.hicon)

    def _nid(self, flags: int) -> w.NOTIFYICONDATAW:
        nid = w.NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(nid)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = flags
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self.hicon
        nid.szTip = self.tooltip[:127]
        return nid

    def _add(self) -> None:
        nid = self._nid(w.NIF_MESSAGE | w.NIF_ICON | w.NIF_TIP)
        w.Shell_NotifyIconW(w.NIM_ADD, ctypes.byref(nid))

    def _show_menu(self) -> None:
        menu = w.CreatePopupMenu()
        w.AppendMenuW(menu, w.MF_STRING | w.MF_DEFAULT, CMD_OPEN, "Открыть Tandem")
        w.AppendMenuW(menu, w.MF_STRING, CMD_TOGGLE,
                      "Остановить зеркало" if self.mirror_running else "Запустить зеркало")
        w.AppendMenuW(menu, w.MF_SEPARATOR, 0, None)
        w.AppendMenuW(menu, w.MF_STRING, CMD_EXIT, "Выход")
        pt = wt.POINT()
        w.GetCursorPos(ctypes.byref(pt))
        w.SetForegroundWindow(self.hwnd)
        cmd = w.TrackPopupMenu(menu, w.TPM_RIGHTBUTTON | w.TPM_RETURNCMD | w.TPM_NONOTIFY,
                               pt.x, pt.y, 0, self.hwnd, None)
        w.PostMessageW(self.hwnd, w.WM_NULL, 0, 0)
        w.DestroyMenu(menu)
        if cmd == CMD_OPEN:
            self.on_event("show")
        elif cmd == CMD_TOGGLE:
            self.on_event("toggle")
        elif cmd == CMD_EXIT:
            self.on_event("exit")

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                event = lparam & 0xFFFF
                if event == w.WM_LBUTTONUP:
                    self.on_event("show")
                elif event in (w.WM_RBUTTONUP, w.WM_CONTEXTMENU):
                    self._show_menu()
                return 0
            if msg == WM_SHOW_REQUEST:
                self.on_event("show")
                return 0
            if msg == WM_QUIT_REQUEST:
                self.on_event("exit")
                return 0
            if msg == self._taskbar_created and self._taskbar_created:
                self._add()
                return 0
            if msg == w.WM_CLOSE:
                nid = self._nid(0)
                w.Shell_NotifyIconW(w.NIM_DELETE, ctypes.byref(nid))
                w.DestroyWindow(hwnd)
                return 0
            if msg == w.WM_DESTROY:
                w.PostQuitMessage(0)
                return 0
        except Exception:
            log.exception("Ошибка обработки сообщения трея")
        return w.DefWindowProcW(hwnd, msg, wparam, lparam)
