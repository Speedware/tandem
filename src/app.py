from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from tkinter import messagebox, ttk
from typing import List, Optional

import autostart
import hotkeys
import settings
import system
import winapi as w
from mirror import MirrorThread
from tray import TrayIcon

log = logging.getLogger(__name__)

TITLE = "Tandem"
AUTOSTART_WAIT_ATTEMPTS = 30


ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "tandem.ico")


class App:
    def __init__(self, autostart_mode: bool = False):
        self.autostart_mode = autostart_mode
        self.cfg = settings.load()
        self.events: "queue.Queue" = queue.Queue()
        self.tray_events: "queue.Queue" = queue.Queue()
        self._tray_hint_shown = False
        self._poll_count = 0
        self.mirror: Optional[MirrorThread] = None
        self.windows: List[system.WindowInfo] = []
        self.monitors: List[system.MonitorInfo] = []
        self._monitor_sig = None
        self.hotkeys = hotkeys.from_settings(self.cfg.get("hotkeys"))
        self._capturing: Optional[str] = None

        self.root = tk.Tk()
        self.root.title(TITLE)
        self.root.resizable(False, False)
        self.root.report_callback_exception = self._on_tk_error
        try:
            self.root.iconbitmap(default=ICON_PATH)
        except tk.TclError:
            log.warning("Не удалось загрузить иконку %s", ICON_PATH)
        self._build_ui()

        self.tray = TrayIcon(ICON_PATH, TITLE, self.tray_events.put)
        self.tray.start()
        self.tray.wait_ready()
        failed = self._apply_hotkeys()
        if failed:
            names = ", ".join(hotkeys.format_hotkey(self.hotkeys[a]) for a in failed)
            self.tray.notify(TITLE, f"Не удалось назначить сочетание {names}: "
                                    "оно занято другой программой.", warning=True)

        try:
            autostart.migrate_legacy()
        except OSError:
            log.exception("Не удалось перенести старую запись автозапуска")
        enabled = autostart.is_enabled()
        if enabled:
            try:
                autostart.ensure_current_path()
            except OSError:
                log.exception("Не удалось обновить запись автозапуска")
        self.var_autostart.set(enabled)
        self.cfg["autostart"] = enabled

        self.refresh_monitors()
        self.refresh_windows()

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.after(200, self._poll_events)
        self.root.after(2000, self._watch_monitors)
        if autostart_mode:
            self.root.withdraw()
            self.root.after(300, self._autostart_attempt)

    def run(self) -> None:
        self.root.mainloop()


    def _build_ui(self) -> None:
        frm = ttk.Frame(self.root, padding=14)
        frm.grid(sticky="nsew")
        frm.columnconfigure(0, weight=1)

        ttk.Label(frm, text="Окно для трансляции:").grid(row=0, column=0, columnspan=2, sticky="w")
        self.cb_window = ttk.Combobox(frm, state="readonly", width=72)
        self.cb_window.grid(row=1, column=0, sticky="ew", pady=(2, 10))
        self.cb_window.bind("<<ComboboxSelected>>", lambda _e: self._on_window_selected())
        self.btn_refresh = ttk.Button(frm, text="Обновить список", command=self.refresh_windows)
        self.btn_refresh.grid(row=1, column=1, sticky="e", padx=(8, 0), pady=(2, 10))

        ttk.Label(frm, text="Монитор для отображения:").grid(row=2, column=0, columnspan=2, sticky="w")
        self.cb_monitor = ttk.Combobox(frm, state="readonly", width=72)
        self.cb_monitor.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 10))
        self.cb_monitor.bind("<<ComboboxSelected>>", lambda _e: self._on_monitor_selected())

        opts = ttk.Frame(frm)
        opts.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(opts, text="FPS:").pack(side="left")
        self.var_fps = tk.StringVar(value=str(self.cfg.get("fps", 30)))
        ttk.Spinbox(opts, from_=1, to=60, width=5, textvariable=self.var_fps).pack(side="left", padx=(4, 18))
        self.var_fps.trace_add("write", lambda *_: self._on_fps_changed())
        self.var_hide_cursor = tk.BooleanVar(value=bool(self.cfg.get("hide_cursor")))
        ttk.Checkbutton(opts, text="Скрыть курсор в зеркале", variable=self.var_hide_cursor,
                        command=self._on_cursor_changed).pack(side="left")

        self.var_autostart = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Запускать при включении компьютера и сразу включать зеркало",
                        variable=self.var_autostart, command=self._on_autostart_changed
                        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 12))

        keys = ttk.LabelFrame(frm, text="Горячие клавиши", padding=(10, 6))
        keys.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        keys.columnconfigure(1, weight=1)
        self.hotkey_vars = {}
        self.hotkey_entries = {}
        for row, (action, title) in enumerate(hotkeys.ACTIONS.items()):
            ttk.Label(keys, text=f"{title}:").grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=hotkeys.format_hotkey(self.hotkeys[action]))
            entry = ttk.Entry(keys, textvariable=var, state="readonly", width=32)
            entry.grid(row=row, column=1, sticky="ew", padx=8, pady=2)
            ttk.Button(keys, text="Изменить", command=lambda a=action: self._capture_hotkey(a)
                       ).grid(row=row, column=2, pady=2)
            ttk.Button(keys, text="Очистить", command=lambda a=action: self._set_hotkey(a, None)
                       ).grid(row=row, column=3, padx=(4, 0), pady=2)
            self.hotkey_vars[action] = var
            self.hotkey_entries[action] = entry

        self.btn_toggle = ttk.Button(frm, text="Запустить зеркало", command=self.toggle_mirror)
        self.btn_toggle.grid(row=7, column=0, columnspan=2, sticky="ew", ipady=6)

        self.var_status = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.var_status, wraplength=560, foreground="#444"
                  ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _status(self, text: str) -> None:
        self.var_status.set(text)
        self.tray.set_tooltip(f"{TITLE}: {text}" if self.mirror else TITLE)

    def _set_running_ui(self, running: bool) -> None:
        self.btn_toggle.configure(text="Остановить зеркало" if running else "Запустить зеркало")
        state = "disabled" if running else "readonly"
        self.cb_window.configure(state=state)
        self.cb_monitor.configure(state=state)
        self.btn_refresh.configure(state="disabled" if running else "normal")
        self.tray.mirror_running = running
        if not running:
            self.tray.set_tooltip(TITLE)


    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.update_idletasks()
        self._keep_off_mirror()
        self.root.lift()
        self.root.focus_force()

    def hide_to_tray(self) -> None:
        self.root.withdraw()
        if not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.notify(TITLE, "Программа продолжает работать в трее. "
                                    "Нажмите на значок, чтобы открыть окно.")

    def _on_unmap(self, event) -> None:
        if event.widget is self.root and self.root.state() == "iconic":
            self.root.after(0, self.hide_to_tray)

    def _keep_off_mirror(self) -> None:
        if not self.mirror or self.root.state() != "normal":
            return
        try:
            gui_hwnd = int(self.root.wm_frame(), 16)
        except (tk.TclError, ValueError):
            return
        device = self.mirror.device
        if system.monitor_device_of_window(gui_hwnd) != device:
            return
        monitors = [m for m in system.list_monitors() if m.device != device]
        if not monitors:
            return
        src = self.mirror.src
        src_dev = system.monitor_device_of_window(src) if src and w.IsWindow(src) else ""
        target = (next((m for m in monitors if m.device == src_dev), None)
                  or next((m for m in monitors if m.primary), None) or monitors[0])
        width, height = self.root.winfo_width(), self.root.winfo_height()
        x = target.left + max(0, (target.width - width) // 2)
        y = target.top + max(0, (target.height - height) // 2)
        self.root.geometry(f"+{x}+{y}")

    def _handle_tray_event(self, event: str) -> None:
        if event == "show":
            self._show_window()
        elif event == "toggle":
            if self.mirror:
                self.toggle_mirror()
            else:
                self._show_window()
                self.start_mirror()
        elif event == "hotkey_toggle":
            if self.mirror:
                self.toggle_mirror()
            else:
                self.start_mirror()
                if not self.mirror:
                    self._show_window()
        elif event == "exit":
            self.quit()


    def _apply_hotkeys(self) -> List[str]:
        return self.tray.set_hotkeys(self.hotkeys)

    def _capture_hotkey(self, action: str) -> None:
        self._end_capture()
        self._capturing = action
        self.tray.set_hotkeys({})
        entry = self.hotkey_entries[action]
        self.hotkey_vars[action].set("Нажмите сочетание… (Esc — отмена)")
        entry.bind("<KeyPress>", self._on_capture_key)
        entry.bind("<FocusOut>", lambda _e: self._cancel_capture())
        entry.focus_set()

    def _on_capture_key(self, event) -> str:
        action = self._capturing
        if not action:
            return "break"
        vk = event.keycode
        mods = hotkeys.pressed_modifiers()
        if hotkeys.is_modifier(vk):
            self.hotkey_vars[action].set(hotkeys.modifiers_text(mods) + "…")
        elif vk == 0x1B and not mods:
            self._cancel_capture()
        elif not hotkeys.is_allowed((mods, vk)):
            self.hotkey_vars[action].set("Добавьте Ctrl, Alt или Win… (Esc — отмена)")
        else:
            self._set_hotkey(action, (mods, vk))
        return "break"

    def _end_capture(self) -> bool:
        action = self._capturing
        if not action:
            return False
        self._capturing = None
        entry = self.hotkey_entries[action]
        entry.unbind("<KeyPress>")
        entry.unbind("<FocusOut>")
        self.hotkey_vars[action].set(hotkeys.format_hotkey(self.hotkeys[action]))
        return True

    def _cancel_capture(self) -> None:
        if self._end_capture():
            self._apply_hotkeys()

    def _set_hotkey(self, action: str, hotkey: Optional[hotkeys.Hotkey]) -> None:
        self._end_capture()
        previous = self.hotkeys[action]
        self.hotkeys[action] = hotkey
        if action in self._apply_hotkeys():
            self.hotkeys[action] = previous
            self._apply_hotkeys()
            messagebox.showerror(TITLE, f"Сочетание {hotkeys.format_hotkey(hotkey)} уже занято "
                                        "другой программой или Windows.\n\nВыберите другое сочетание.")
        self.hotkey_vars[action].set(hotkeys.format_hotkey(self.hotkeys[action]))
        self._save()


    def refresh_windows(self) -> None:
        previous = self.current_window()
        self.windows = system.list_windows()
        self.cb_window["values"] = [x.label for x in self.windows]

        target = None
        if previous:
            target = next((x for x in self.windows if x.hwnd == previous.hwnd), None)
        if target is None:
            target = system.find_window(self.cfg.get("window"), self.windows)
        if target is not None:
            self.cb_window.current(self.windows.index(target))
        else:
            self.cb_window.set("")
        self._update_ready_status()

    def refresh_monitors(self) -> None:
        previous = self.current_monitor()
        self.monitors = system.list_monitors()
        self._monitor_sig = self._signature(self.monitors)
        self.cb_monitor["values"] = [m.label for m in self.monitors]

        spec = previous.spec if previous else self.cfg.get("monitor")
        target = system.find_monitor(spec, self.monitors)
        if target is not None:
            self.cb_monitor.current(self.monitors.index(target))
        else:
            self.cb_monitor.set("")
        self._update_ready_status()

    @staticmethod
    def _signature(monitors):
        return [(m.device, m.left, m.top, m.right, m.bottom) for m in monitors]

    def current_window(self) -> Optional[system.WindowInfo]:
        i = self.cb_window.current()
        return self.windows[i] if 0 <= i < len(self.windows) else None

    def current_monitor(self) -> Optional[system.MonitorInfo]:
        i = self.cb_monitor.current()
        return self.monitors[i] if 0 <= i < len(self.monitors) else None

    def _update_ready_status(self) -> None:
        if self.mirror:
            return
        if len(self.monitors) < 2:
            self._status("Подключён только один монитор. Для работы программы нужны два монитора.")
            self.btn_toggle.configure(state="disabled")
            return
        self.btn_toggle.configure(state="normal")
        self._status("Выберите окно и монитор, затем нажмите «Запустить зеркало».")


    def _on_window_selected(self) -> None:
        win = self.current_window()
        if not win:
            return
        win_dev = system.monitor_device_of_window(win.hwnd)
        mon = self.current_monitor()
        if mon is None or mon.device == win_dev:
            others = [m for m in self.monitors if m.device != win_dev]
            if others:
                self.cb_monitor.current(self.monitors.index(others[0]))
        self._save()

    def _on_monitor_selected(self) -> None:
        self._save()

    def _fps(self) -> int:
        try:
            return max(1, min(60, int(self.var_fps.get())))
        except ValueError:
            return 30

    def _on_fps_changed(self) -> None:
        if self.mirror:
            self.mirror.fps = self._fps()
        self._save()

    def _on_cursor_changed(self) -> None:
        if self.mirror:
            self.mirror.hide_cursor = self.var_hide_cursor.get()
        self._save()

    def _on_autostart_changed(self) -> None:
        enabled = self.var_autostart.get()
        try:
            autostart.set_enabled(enabled)
        except OSError as e:
            self.var_autostart.set(not enabled)
            messagebox.showerror(TITLE, f"Не удалось изменить автозапуск:\n{e}")
            return
        self._save()

    def _save(self) -> None:
        win = self.current_window()
        mon = self.current_monitor()
        if win:
            self.cfg["window"] = win.spec
        if mon:
            self.cfg["monitor"] = mon.spec
        self.cfg["fps"] = self._fps()
        self.cfg["hide_cursor"] = bool(self.var_hide_cursor.get())
        self.cfg["autostart"] = bool(self.var_autostart.get())
        self.cfg["hotkeys"] = hotkeys.to_settings(self.hotkeys)
        settings.save(self.cfg)


    def toggle_mirror(self) -> None:
        if self.mirror:
            self.stop_mirror()
            self._update_ready_status()
        else:
            self.start_mirror()

    def start_mirror(self) -> None:
        self.refresh_monitors()
        if len(self.monitors) < 2:
            messagebox.showerror(TITLE, "Подключён только один монитор.\n\n"
                                        "Программа работает только с двумя мониторами: на одном вы работаете, "
                                        "на другом клиент видит копию окна.")
            return
        win = self.current_window()
        if win is None:
            messagebox.showerror(TITLE, "Выберите окно для трансляции.")
            return
        if not w.IsWindow(win.hwnd):
            self.refresh_windows()
            messagebox.showerror(TITLE, "Выбранное окно уже закрыто. Список окон обновлён — выберите окно заново.")
            return
        mon = self.current_monitor()
        if mon is None:
            messagebox.showerror(TITLE, "Выберите монитор для отображения.")
            return
        if system.monitor_device_of_window(win.hwnd) == mon.device:
            messagebox.showerror(
                TITLE,
                f"Окно «{win.title}» находится на мониторе {mon.number} — том же, что выбран для зеркала.\n\n"
                "Зеркало нельзя показывать на экране, где вы работаете. "
                "Выберите другой монитор или перенесите окно на свой экран.")
            return
        self._save()
        self._launch(win.hwnd, win.spec, mon.device)

    def _launch(self, hwnd: Optional[int], spec: dict, device: str) -> None:
        self.events = queue.Queue()
        self.mirror = MirrorThread(hwnd, spec, device, self._fps(),
                                   bool(self.var_hide_cursor.get()), self.events)
        self.mirror.start()
        self._set_running_ui(True)
        self._status("Зеркало запускается…")
        self._keep_off_mirror()

    def stop_mirror(self) -> None:
        if not self.mirror:
            return
        self.mirror.stop()
        self.mirror.join(timeout=3)
        self.mirror = None
        self._set_running_ui(False)


    def _poll_events(self) -> None:
        try:
            while True:
                self._handle_tray_event(self.tray_events.get_nowait())
        except queue.Empty:
            pass
        self._poll_count += 1
        if self._poll_count % 5 == 0:
            self._keep_off_mirror()
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "error":
                    self.stop_mirror()
                    self._update_ready_status()
                    self._show_window()
                    messagebox.showerror(TITLE, text)
                else:
                    self._status(text)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_events)

    def _watch_monitors(self) -> None:
        self.root.after(2000, self._watch_monitors)
        monitors = system.list_monitors()
        if self._signature(monitors) == self._monitor_sig:
            return
        log.info("Конфигурация мониторов изменилась: %s", self._signature(monitors))

        if self.mirror:
            device = self.mirror.device
            target = next((m for m in monitors if m.device == device), None)
            if len(monitors) < 2 or target is None:
                self.stop_mirror()
                self.refresh_monitors()
                self._show_window()
                if len(monitors) < 2:
                    messagebox.showwarning(TITLE, "Второй монитор отключён — зеркало остановлено.\n\n"
                                                  "Подключите второй монитор и запустите зеркало снова.")
                else:
                    messagebox.showwarning(TITLE, "Монитор для отображения отключён — зеркало остановлено.\n\n"
                                                  "Выберите другой монитор и нажмите «Запустить зеркало».")
                return
            hwnd, spec = self.mirror.src, self.mirror.window_spec
            self.stop_mirror()
            self.refresh_monitors()
            self._launch(hwnd, spec, device)
        else:
            self.refresh_monitors()


    def _autostart_attempt(self, attempt: int = 0) -> None:
        if self.mirror:
            return
        self.refresh_monitors()
        spec_win = self.cfg.get("window")
        mon = system.find_monitor(self.cfg.get("monitor"), self.monitors)

        if not spec_win or not self.cfg.get("monitor"):
            self._show_window()
            self._status("Настройки ещё не сохранены: выберите окно и монитор и запустите зеркало.")
            return
        if len(self.monitors) < 2 or mon is None:
            if attempt < AUTOSTART_WAIT_ATTEMPTS:
                self._status("Ожидание второго монитора…")
                self.root.after(2000, lambda: self._autostart_attempt(attempt + 1))
                return
            self._show_window()
            if len(self.monitors) < 2:
                messagebox.showwarning(TITLE, "Второй монитор не найден.\n\n"
                                              "Подключите второй монитор и запустите зеркало вручную.")
            else:
                messagebox.showwarning(TITLE, "Сохранённый монитор для отображения не найден "
                                              "(возможно, он отключён).\n\nВыберите другой монитор "
                                              "и нажмите «Запустить зеркало».")
            return

        self.cb_monitor.current(self.monitors.index(mon))
        self.refresh_windows()
        found = system.find_window(spec_win, self.windows)
        self._launch(found.hwnd if found else None, spec_win, mon.device)


    def quit(self) -> None:
        self.stop_mirror()
        self._save()
        self.tray.stop()
        self.root.destroy()

    def _on_tk_error(self, exc, val, tb) -> None:
        log.error("Ошибка интерфейса", exc_info=(exc, val, tb))
        messagebox.showerror(TITLE, f"Произошла ошибка: {val}\n\nПодробности в журнале:\n{settings.LOG_PATH}")
