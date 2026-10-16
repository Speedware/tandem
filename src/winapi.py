from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes as wt

if sys.platform != "win32":
    raise RuntimeError("Tandem работает только в Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
winmm = ctypes.WinDLL("winmm")

LRESULT = ctypes.c_ssize_t
PTR_INT = ctypes.c_ssize_t


GW_OWNER = 4
GA_ROOT = 2
GWL_EXSTYLE = -20

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

LWA_ALPHA = 0x2

WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_CLOSE = 0x0010
WM_ERASEBKGND = 0x0014
WM_MOUSEACTIVATE = 0x0021
WM_NCHITTEST = 0x0084
MA_NOACTIVATE = 3
HTTRANSPARENT = -1

PM_REMOVE = 0x0001

PW_CLIENTONLY = 0x1
PW_RENDERFULLCONTENT = 0x2

MONITOR_DEFAULTTONEAREST = 2
MONITORINFOF_PRIMARY = 1

DWMWA_CLOAKED = 14

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

SRCCOPY = 0x00CC0020
HALFTONE = 4
COLORONCOLOR = 3
BLACK_BRUSH = 4
TRANSPARENT = 1
FW_NORMAL = 400
FW_SEMIBOLD = 600
DEFAULT_CHARSET = 1
CLEARTYPE_QUALITY = 5

DT_CENTER = 0x1
DT_VCENTER = 0x4
DT_SINGLELINE = 0x20
DT_NOPREFIX = 0x800
DT_END_ELLIPSIS = 0x8000

DI_NORMAL = 0x3
CURSOR_SHOWING = 0x1
IDC_ARROW = 32512

ERROR_ALREADY_EXISTS = 183
ERROR_CLASS_ALREADY_EXISTS = 1410

WM_NULL = 0x0000
WM_CONTEXTMENU = 0x007B
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_APP = 0x8000
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x1
NIF_ICON = 0x2
NIF_TIP = 0x4
NIF_INFO = 0x10
NIIF_INFO = 0x1
NIIF_WARNING = 0x2
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x10
SM_CXSMICON = 49
SM_CYSMICON = 50
MF_STRING = 0x0
MF_SEPARATOR = 0x800
MF_DEFAULT = 0x1000
TPM_RIGHTBUTTON = 0x2
TPM_NONOTIFY = 0x80
TPM_RETURNCMD = 0x100


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM
)


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork", wt.RECT),
        ("dwFlags", wt.DWORD),
        ("szDevice", wt.WCHAR * 32),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("DeviceName", wt.WCHAR * 32),
        ("DeviceString", wt.WCHAR * 128),
        ("StateFlags", wt.DWORD),
        ("DeviceID", wt.WCHAR * 128),
        ("DeviceKey", wt.WCHAR * 128),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("flags", wt.DWORD),
        ("hCursor", wt.HANDLE),
        ("ptScreenPos", wt.POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wt.BOOL),
        ("xHotspot", wt.DWORD),
        ("yHotspot", wt.DWORD),
        ("hbmMask", wt.HBITMAP),
        ("hbmColor", wt.HBITMAP),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", wt.DWORD * 4),
        ("hBalloonIcon", wt.HICON),
    ]


def _fn(dll, name, restype, *argtypes, optional=False):
    try:
        fn = getattr(dll, name)
    except AttributeError:
        if optional:
            return None
        raise
    fn.restype = restype
    fn.argtypes = argtypes
    return fn


P = ctypes.POINTER

EnumWindows = _fn(user32, "EnumWindows", wt.BOOL, WNDENUMPROC, wt.LPARAM)
GetWindowTextLengthW = _fn(user32, "GetWindowTextLengthW", ctypes.c_int, wt.HWND)
GetWindowTextW = _fn(user32, "GetWindowTextW", ctypes.c_int, wt.HWND, wt.LPWSTR, ctypes.c_int)
GetClassNameW = _fn(user32, "GetClassNameW", ctypes.c_int, wt.HWND, wt.LPWSTR, ctypes.c_int)
IsWindow = _fn(user32, "IsWindow", wt.BOOL, wt.HWND)
IsWindowVisible = _fn(user32, "IsWindowVisible", wt.BOOL, wt.HWND)
IsIconic = _fn(user32, "IsIconic", wt.BOOL, wt.HWND)
GetWindow = _fn(user32, "GetWindow", wt.HWND, wt.HWND, wt.UINT)
GetAncestor = _fn(user32, "GetAncestor", wt.HWND, wt.HWND, wt.UINT)
GetWindowLongW = _fn(user32, "GetWindowLongW", wt.LONG, wt.HWND, ctypes.c_int)
GetWindowThreadProcessId = _fn(user32, "GetWindowThreadProcessId", wt.DWORD, wt.HWND, P(wt.DWORD))
GetClientRect = _fn(user32, "GetClientRect", wt.BOOL, wt.HWND, P(wt.RECT))
ClientToScreen = _fn(user32, "ClientToScreen", wt.BOOL, wt.HWND, P(wt.POINT))
WindowFromPoint = _fn(user32, "WindowFromPoint", wt.HWND, wt.POINT)
PrintWindow = _fn(user32, "PrintWindow", wt.BOOL, wt.HWND, wt.HDC, wt.UINT)

EnumDisplayMonitors = _fn(user32, "EnumDisplayMonitors", wt.BOOL, wt.HDC, P(wt.RECT), MONITORENUMPROC, wt.LPARAM)
GetMonitorInfoW = _fn(user32, "GetMonitorInfoW", wt.BOOL, wt.HMONITOR, P(MONITORINFOEXW))
MonitorFromWindow = _fn(user32, "MonitorFromWindow", wt.HMONITOR, wt.HWND, wt.DWORD)
EnumDisplayDevicesW = _fn(user32, "EnumDisplayDevicesW", wt.BOOL, wt.LPCWSTR, wt.DWORD, P(DISPLAY_DEVICEW), wt.DWORD)

RegisterClassExW = _fn(user32, "RegisterClassExW", wt.ATOM, P(WNDCLASSEXW))
CreateWindowExW = _fn(
    user32, "CreateWindowExW", wt.HWND,
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
)
DefWindowProcW = _fn(user32, "DefWindowProcW", LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
DestroyWindow = _fn(user32, "DestroyWindow", wt.BOOL, wt.HWND)
ShowWindow = _fn(user32, "ShowWindow", wt.BOOL, wt.HWND, ctypes.c_int)
SetWindowPos = _fn(
    user32, "SetWindowPos", wt.BOOL,
    wt.HWND, PTR_INT, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT,
)
SetLayeredWindowAttributes = _fn(user32, "SetLayeredWindowAttributes", wt.BOOL, wt.HWND, wt.DWORD, wt.BYTE, wt.DWORD)
ValidateRect = _fn(user32, "ValidateRect", wt.BOOL, wt.HWND, P(wt.RECT))
PeekMessageW = _fn(user32, "PeekMessageW", wt.BOOL, P(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT)
TranslateMessage = _fn(user32, "TranslateMessage", wt.BOOL, P(wt.MSG))
DispatchMessageW = _fn(user32, "DispatchMessageW", LRESULT, P(wt.MSG))
LoadCursorW = _fn(user32, "LoadCursorW", wt.HANDLE, wt.HINSTANCE, wt.LPVOID)
GetDC = _fn(user32, "GetDC", wt.HDC, wt.HWND)
ReleaseDC = _fn(user32, "ReleaseDC", ctypes.c_int, wt.HWND, wt.HDC)
FillRect = _fn(user32, "FillRect", ctypes.c_int, wt.HDC, P(wt.RECT), wt.HBRUSH)
DrawTextW = _fn(user32, "DrawTextW", ctypes.c_int, wt.HDC, wt.LPCWSTR, ctypes.c_int, P(wt.RECT), wt.UINT)

GetCursorInfo = _fn(user32, "GetCursorInfo", wt.BOOL, P(CURSORINFO))
GetIconInfo = _fn(user32, "GetIconInfo", wt.BOOL, wt.HANDLE, P(ICONINFO))
DrawIconEx = _fn(
    user32, "DrawIconEx", wt.BOOL,
    wt.HDC, ctypes.c_int, ctypes.c_int, wt.HANDLE, ctypes.c_int, ctypes.c_int,
    wt.UINT, wt.HBRUSH, wt.UINT,
)

GetMessageW = _fn(user32, "GetMessageW", wt.BOOL, P(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
PostMessageW = _fn(user32, "PostMessageW", wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
PostQuitMessage = _fn(user32, "PostQuitMessage", None, ctypes.c_int)
RegisterWindowMessageW = _fn(user32, "RegisterWindowMessageW", wt.UINT, wt.LPCWSTR)
FindWindowW = _fn(user32, "FindWindowW", wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
LoadImageW = _fn(user32, "LoadImageW", wt.HANDLE, wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                 ctypes.c_int, ctypes.c_int, wt.UINT)
DestroyIcon = _fn(user32, "DestroyIcon", wt.BOOL, wt.HICON)
GetSystemMetrics = _fn(user32, "GetSystemMetrics", ctypes.c_int, ctypes.c_int)
CreatePopupMenu = _fn(user32, "CreatePopupMenu", wt.HMENU)
AppendMenuW = _fn(user32, "AppendMenuW", wt.BOOL, wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR)
TrackPopupMenu = _fn(user32, "TrackPopupMenu", wt.BOOL, wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int,
                     ctypes.c_int, wt.HWND, P(wt.RECT))
DestroyMenu = _fn(user32, "DestroyMenu", wt.BOOL, wt.HMENU)
SetForegroundWindow = _fn(user32, "SetForegroundWindow", wt.BOOL, wt.HWND)
GetCursorPos = _fn(user32, "GetCursorPos", wt.BOOL, P(wt.POINT))

Shell_NotifyIconW = _fn(shell32, "Shell_NotifyIconW", wt.BOOL, wt.DWORD, P(NOTIFYICONDATAW))

SetProcessDpiAwarenessContext = _fn(user32, "SetProcessDpiAwarenessContext", wt.BOOL, PTR_INT, optional=True)
SetProcessDPIAware = _fn(user32, "SetProcessDPIAware", wt.BOOL, optional=True)

CreateCompatibleDC = _fn(gdi32, "CreateCompatibleDC", wt.HDC, wt.HDC)
CreateCompatibleBitmap = _fn(gdi32, "CreateCompatibleBitmap", wt.HBITMAP, wt.HDC, ctypes.c_int, ctypes.c_int)
SelectObject = _fn(gdi32, "SelectObject", wt.HGDIOBJ, wt.HDC, wt.HGDIOBJ)
DeleteObject = _fn(gdi32, "DeleteObject", wt.BOOL, wt.HGDIOBJ)
DeleteDC = _fn(gdi32, "DeleteDC", wt.BOOL, wt.HDC)
BitBlt = _fn(
    gdi32, "BitBlt", wt.BOOL,
    wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD,
)
StretchBlt = _fn(
    gdi32, "StretchBlt", wt.BOOL,
    wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.DWORD,
)
SetStretchBltMode = _fn(gdi32, "SetStretchBltMode", ctypes.c_int, wt.HDC, ctypes.c_int)
SetBrushOrgEx = _fn(gdi32, "SetBrushOrgEx", wt.BOOL, wt.HDC, ctypes.c_int, ctypes.c_int, P(wt.POINT))
GetStockObject = _fn(gdi32, "GetStockObject", wt.HGDIOBJ, ctypes.c_int)
CreateSolidBrush = _fn(gdi32, "CreateSolidBrush", wt.HBRUSH, wt.DWORD)
CreateFontW = _fn(
    gdi32, "CreateFontW", wt.HFONT,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD,
    wt.LPCWSTR,
)
SetTextColor = _fn(gdi32, "SetTextColor", wt.DWORD, wt.HDC, wt.DWORD)
SetBkMode = _fn(gdi32, "SetBkMode", ctypes.c_int, wt.HDC, ctypes.c_int)

GetModuleHandleW = _fn(kernel32, "GetModuleHandleW", wt.HMODULE, wt.LPCWSTR)
OpenProcess = _fn(kernel32, "OpenProcess", wt.HANDLE, wt.DWORD, wt.BOOL, wt.DWORD)
CloseHandle = _fn(kernel32, "CloseHandle", wt.BOOL, wt.HANDLE)
QueryFullProcessImageNameW = _fn(
    kernel32, "QueryFullProcessImageNameW", wt.BOOL, wt.HANDLE, wt.DWORD, wt.LPWSTR, P(wt.DWORD)
)
CreateMutexW = _fn(kernel32, "CreateMutexW", wt.HANDLE, wt.LPVOID, wt.BOOL, wt.LPCWSTR)
WaitForSingleObject = _fn(kernel32, "WaitForSingleObject", wt.DWORD, wt.HANDLE, wt.DWORD)

DwmGetWindowAttribute = _fn(dwmapi, "DwmGetWindowAttribute", ctypes.c_long, wt.HWND, wt.DWORD, wt.LPVOID, wt.DWORD)

timeBeginPeriod = _fn(winmm, "timeBeginPeriod", wt.UINT, wt.UINT)
timeEndPeriod = _fn(winmm, "timeEndPeriod", wt.UINT, wt.UINT)


def rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)


def enable_dpi_awareness() -> None:
    if SetProcessDpiAwarenessContext is not None:
        try:
            if SetProcessDpiAwarenessContext(-4):
                return
        except OSError:
            pass
    try:
        if ctypes.WinDLL("shcore").SetProcessDpiAwareness(2) == 0:
            return
    except (OSError, AttributeError):
        pass
    if SetProcessDPIAware is not None:
        SetProcessDPIAware()
