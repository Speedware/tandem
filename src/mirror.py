from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from ctypes import wintypes as wt
from typing import Optional

import system
import winapi as w

log = logging.getLogger(__name__)

CLASS_NAME = "TandemView"

_class_lock = threading.Lock()
_class_registered = False


@w.WNDPROC
def _wndproc(hwnd, msg, wparam, lparam):
    if msg == w.WM_MOUSEACTIVATE:
        return w.MA_NOACTIVATE
    if msg == w.WM_NCHITTEST:
        return w.HTTRANSPARENT
    if msg == w.WM_ERASEBKGND:
        return 1
    if msg == w.WM_PAINT:
        w.ValidateRect(hwnd, None)
        return 0
    if msg == w.WM_CLOSE:
        return 0
    return w.DefWindowProcW(hwnd, msg, wparam, lparam)


def _register_class(hinst) -> None:
    global _class_registered
    with _class_lock:
        if _class_registered:
            return
        wc = w.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(wc)
        wc.lpfnWndProc = _wndproc
        wc.hInstance = hinst
        wc.hCursor = w.LoadCursorW(None, w.IDC_ARROW)
        wc.hbrBackground = w.GetStockObject(w.BLACK_BRUSH)
        wc.lpszClassName = CLASS_NAME
        if not w.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != w.ERROR_CLASS_ALREADY_EXISTS:
                raise MirrorError(f"Не удалось зарегистрировать окно зеркала (код ошибки {err}).")
        _class_registered = True


class MirrorError(Exception):
    pass


class MirrorThread(threading.Thread):
    def __init__(self, hwnd: Optional[int], window_spec: dict, monitor_device: str,
                 fps: int, hide_cursor: bool, events: "queue.Queue"):
        super().__init__(name="mirror", daemon=True)
        self.src = hwnd
        self.window_spec = window_spec
        self.device = monitor_device
        self.fps = fps
        self.hide_cursor = hide_cursor
        self._events = events
        self._stop_event = threading.Event()

        self._state = None
        self._visible = False
        self._last_find = 0.0
        self._fails = 0
        self._have_frame = False
        self._hotspots = {}

        self.hwnd = None
        self.win_dc = None
        self.back_dc = self.back_bmp = self.back_old = None
        self.cap_dc = self.cap_bmp = self.cap_old = None
        self.cap_size = (0, 0)
        self.font_big = self.font_small = None
        self.banner_brush = None
        self.stretch_mode = None


    def stop(self) -> None:
        self._stop_event.set()


    def run(self) -> None:
        w.timeBeginPeriod(1)
        try:
            self._setup()
            self._loop()
        except MirrorError as e:
            self._emit("error", str(e))
        except Exception as e:
            log.exception("Сбой зеркала")
            self._emit("error", f"Непредвиденная ошибка зеркала: {e}")
        finally:
            self._cleanup()
            w.timeEndPeriod(1)

    def _emit(self, kind: str, text: str) -> None:
        self._events.put((kind, text))

    def _set_state(self, kind: str, text: str) -> None:
        if kind != self._state:
            self._state = kind
            self._emit(kind, text)

    def _setup(self) -> None:
        mon = next((m for m in system.list_monitors() if m.device == self.device), None)
        if mon is None:
            raise MirrorError("Монитор для отображения не найден — возможно, он отключён.")
        self.x, self.y, self.W, self.H = mon.left, mon.top, mon.width, mon.height

        hinst = w.GetModuleHandleW(None)
        _register_class(hinst)
        ex_style = (w.WS_EX_TOPMOST | w.WS_EX_TOOLWINDOW | w.WS_EX_NOACTIVATE
                    | w.WS_EX_LAYERED | w.WS_EX_TRANSPARENT)
        self.hwnd = w.CreateWindowExW(ex_style, CLASS_NAME, "Tandem", w.WS_POPUP,
                                      self.x, self.y, self.W, self.H, None, None, hinst, None)
        if not self.hwnd:
            raise MirrorError(f"Не удалось создать окно зеркала (код ошибки {ctypes.get_last_error()}).")
        w.SetLayeredWindowAttributes(self.hwnd, 0, 255, w.LWA_ALPHA)

        self.win_dc = w.GetDC(self.hwnd)
        self.back_dc = w.CreateCompatibleDC(self.win_dc)
        self.back_bmp = w.CreateCompatibleBitmap(self.win_dc, self.W, self.H)
        if not self.back_dc or not self.back_bmp:
            raise MirrorError("Недостаточно графической памяти для окна зеркала.")
        self.back_old = w.SelectObject(self.back_dc, self.back_bmp)
        self.cap_dc = w.CreateCompatibleDC(self.win_dc)
        w.SetBkMode(self.back_dc, w.TRANSPARENT)

        self.font_big = w.CreateFontW(-max(28, self.H // 18), 0, 0, 0, w.FW_SEMIBOLD, 0, 0, 0,
                                      w.DEFAULT_CHARSET, 0, 0, w.CLEARTYPE_QUALITY, 0, "Segoe UI")
        self.font_small = w.CreateFontW(-max(16, self.H // 40), 0, 0, 0, w.FW_NORMAL, 0, 0, 0,
                                        w.DEFAULT_CHARSET, 0, 0, w.CLEARTYPE_QUALITY, 0, "Segoe UI")
        self.banner_brush = w.CreateSolidBrush(w.rgb(32, 32, 32))

        self._draw_message("Tandem", "Подготовка трансляции…")
        self._show(True)
        self._present()

    def _loop(self) -> None:
        next_t = time.perf_counter()
        last_topmost = next_t
        while not self._stop_event.is_set():
            self._pump()
            now = time.perf_counter()
            if self._visible and now - last_topmost > 2.0:
                self._place_topmost()
                last_topmost = now
            self._tick(now)

            next_t += 1.0 / max(1, min(120, int(self.fps)))
            delay = next_t - time.perf_counter()
            if delay > 0:
                self._stop_event.wait(delay)
            else:
                next_t = time.perf_counter()

    def _pump(self) -> None:
        msg = wt.MSG()
        while w.PeekMessageW(ctypes.byref(msg), None, 0, 0, w.PM_REMOVE):
            w.TranslateMessage(ctypes.byref(msg))
            w.DispatchMessageW(ctypes.byref(msg))


    def _tick(self, now: float) -> None:
        if not self.src or not w.IsWindow(self.src):
            self.src = None
            self._have_frame = False
            if now - self._last_find >= 1.0:
                self._last_find = now
                found = system.find_window(self.window_spec)
                if found and system.monitor_device_of_window(found.hwnd) != self.device:
                    self.src = found.hwnd
                    self._fails = 0
            if not self.src:
                self._show(True)
                self._set_state("no_window", "Отсутствует окно для отображения")
                self._draw_message("Отсутствует окно для отображения",
                                   "Зеркало включится автоматически, когда окно появится")
                self._present()
                return

        src = self.src
        if system.monitor_device_of_window(src) == self.device:
            self._show(False)
            self._set_state("same_monitor",
                            "Окно перемещено на монитор зеркала — зеркало скрыто. "
                            "Верните окно на свой монитор.")
            return
        self._show(True)

        if w.IsIconic(src):
            self._set_state("minimized", "Окно свёрнуто — в зеркале показан последний кадр.")
            if self._have_frame:
                self._compose()
                self._banner("Окно свёрнуто")
            else:
                self._draw_message("Окно свёрнуто", "Разверните окно, чтобы начать трансляцию")
            self._present()
            return

        if self._capture(src):
            self._fails = 0
            self._have_frame = True
            self._set_state("running", "Идёт трансляция")
        else:
            self._fails += 1
            if self._fails >= max(10, int(self.fps) * 2):
                self._have_frame = False
                self._set_state("capture_error",
                                "Не удалось захватить содержимое окна. Возможно, программа запущена "
                                "от имени администратора — запустите Tandem так же.")
                self._draw_message("Не удалось захватить окно",
                                   "Проверьте, что окно открыто и не запущено от имени администратора")
                self._present()
                return

        if self._have_frame:
            self._compose()
            self._present()

    def _capture(self, src) -> bool:
        rc = wt.RECT()
        if not w.GetClientRect(src, ctypes.byref(rc)):
            return False
        cw, ch = rc.right - rc.left, rc.bottom - rc.top
        if cw <= 0 or ch <= 0:
            return False
        if (cw, ch) != self.cap_size:
            bmp = w.CreateCompatibleBitmap(self.win_dc, cw, ch)
            if not bmp:
                return False
            prev = w.SelectObject(self.cap_dc, bmp)
            if self.cap_bmp:
                w.DeleteObject(self.cap_bmp)
            else:
                self.cap_old = prev
            self.cap_bmp = bmp
            self.cap_size = (cw, ch)

        if not w.PrintWindow(src, self.cap_dc, w.PW_CLIENTONLY | w.PW_RENDERFULLCONTENT):
            return False
        if not self.hide_cursor:
            self._draw_cursor(src, cw, ch)
        return True

    def _draw_cursor(self, src, cw: int, ch: int) -> None:
        ci = w.CURSORINFO()
        ci.cbSize = ctypes.sizeof(ci)
        if not w.GetCursorInfo(ctypes.byref(ci)) or not (ci.flags & w.CURSOR_SHOWING) or not ci.hCursor:
            return
        under = w.WindowFromPoint(ci.ptScreenPos)
        if not under or w.GetAncestor(under, w.GA_ROOT) != src:
            return
        origin = wt.POINT(0, 0)
        w.ClientToScreen(src, ctypes.byref(origin))
        x = ci.ptScreenPos.x - origin.x
        y = ci.ptScreenPos.y - origin.y
        if not (0 <= x < cw and 0 <= y < ch):
            return
        hx, hy = self._hotspot(ci.hCursor)
        w.DrawIconEx(self.cap_dc, x - hx, y - hy, ci.hCursor, 0, 0, 0, None, w.DI_NORMAL)

    def _hotspot(self, hcursor):
        if hcursor not in self._hotspots:
            ii = w.ICONINFO()
            if w.GetIconInfo(hcursor, ctypes.byref(ii)):
                self._hotspots[hcursor] = (ii.xHotspot, ii.yHotspot)
                if ii.hbmMask:
                    w.DeleteObject(ii.hbmMask)
                if ii.hbmColor:
                    w.DeleteObject(ii.hbmColor)
            else:
                self._hotspots[hcursor] = (0, 0)
        return self._hotspots[hcursor]


    def _clear(self) -> None:
        rc = wt.RECT(0, 0, self.W, self.H)
        w.FillRect(self.back_dc, ctypes.byref(rc), w.GetStockObject(w.BLACK_BRUSH))

    def _compose(self) -> None:
        cw, ch = self.cap_size
        scale = min(self.W / cw, self.H / ch)
        dw, dh = max(1, round(cw * scale)), max(1, round(ch * scale))
        x0, y0 = (self.W - dw) // 2, (self.H - dh) // 2
        if dw != self.W or dh != self.H:
            self._clear()
        if (dw, dh) == (cw, ch):
            w.BitBlt(self.back_dc, x0, y0, cw, ch, self.cap_dc, 0, 0, w.SRCCOPY)
            return
        mode = w.HALFTONE if scale < 1 else w.COLORONCOLOR
        if mode != self.stretch_mode:
            w.SetStretchBltMode(self.back_dc, mode)
            w.SetBrushOrgEx(self.back_dc, 0, 0, None)
            self.stretch_mode = mode
        w.StretchBlt(self.back_dc, x0, y0, dw, dh, self.cap_dc, 0, 0, cw, ch, w.SRCCOPY)

    def _text(self, rect: wt.RECT, text: str, font, color: int) -> None:
        old = w.SelectObject(self.back_dc, font)
        w.SetTextColor(self.back_dc, color)
        w.DrawTextW(self.back_dc, text, -1, ctypes.byref(rect),
                    w.DT_CENTER | w.DT_VCENTER | w.DT_SINGLELINE | w.DT_NOPREFIX | w.DT_END_ELLIPSIS)
        w.SelectObject(self.back_dc, old)

    def _draw_message(self, title: str, subtitle: str = "") -> None:
        self._clear()
        big = max(28, self.H // 18)
        mid = self.H // 2
        self._text(wt.RECT(0, mid - big * 2, self.W, mid), title, self.font_big, w.rgb(255, 255, 255))
        if subtitle:
            self._text(wt.RECT(0, mid + big // 4, self.W, mid + big * 2), subtitle,
                       self.font_small, w.rgb(170, 170, 170))

    def _banner(self, text: str) -> None:
        h = max(16, self.H // 40) * 3
        rc = wt.RECT(0, self.H - h, self.W, self.H)
        w.FillRect(self.back_dc, ctypes.byref(rc), self.banner_brush)
        self._text(rc, text, self.font_small, w.rgb(230, 230, 230))

    def _present(self) -> None:
        w.BitBlt(self.win_dc, 0, 0, self.W, self.H, self.back_dc, 0, 0, w.SRCCOPY)

    def _place_topmost(self) -> None:
        w.SetWindowPos(self.hwnd, w.HWND_TOPMOST, self.x, self.y, self.W, self.H,
                       w.SWP_NOACTIVATE | w.SWP_SHOWWINDOW)

    def _show(self, visible: bool) -> None:
        if visible == self._visible:
            return
        self._visible = visible
        if visible:
            w.ShowWindow(self.hwnd, w.SW_SHOWNOACTIVATE)
            self._place_topmost()
        else:
            w.ShowWindow(self.hwnd, w.SW_HIDE)

    def _cleanup(self) -> None:
        try:
            if self.cap_dc:
                if self.cap_old:
                    w.SelectObject(self.cap_dc, self.cap_old)
                w.DeleteDC(self.cap_dc)
            if self.cap_bmp:
                w.DeleteObject(self.cap_bmp)
            if self.back_dc:
                if self.back_old:
                    w.SelectObject(self.back_dc, self.back_old)
                w.DeleteDC(self.back_dc)
            if self.back_bmp:
                w.DeleteObject(self.back_bmp)
            for obj in (self.font_big, self.font_small, self.banner_brush):
                if obj:
                    w.DeleteObject(obj)
            if self.win_dc:
                w.ReleaseDC(self.hwnd, self.win_dc)
            if self.hwnd:
                w.DestroyWindow(self.hwnd)
        except Exception:
            log.exception("Ошибка при освобождении ресурсов зеркала")
