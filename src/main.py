from __future__ import annotations

import argparse
import ctypes
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True

APP_USER_MODEL_ID = "Tandem.App"


def _setup_logging() -> None:
    import settings
    try:
        os.makedirs(settings.APP_DIR, exist_ok=True)
        logging.basicConfig(
            filename=settings.LOG_PATH, encoding="utf-8", level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except (OSError, ValueError):
        logging.basicConfig(level=logging.INFO)


def main() -> int:
    if sys.platform != "win32":
        sys.stderr.write("Tandem работает только в Windows 10/11.\n")
        return 1

    parser = argparse.ArgumentParser(description="Зеркало окна на второй монитор")
    parser.add_argument("--autostart", action="store_true", help="запуск при входе в Windows")
    parser.add_argument("--quit", action="store_true", help="закрыть запущенную копию")
    parser.add_argument("--uninstall", action="store_true", help="закрыть копию и убрать автозапуск")
    args = parser.parse_args()

    _setup_logging()
    if args.quit or args.uninstall:
        from tray import request_quit_existing
        request_quit_existing()
        if args.uninstall:
            import autostart
            try:
                autostart.set_enabled(False)
            except OSError:
                logging.exception("Не удалось убрать автозапуск")
        return 0

    import winapi
    winapi.enable_dpi_awareness()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass

    mutex = winapi.CreateMutexW(None, False, "Local\\Tandem.SingleInstance")
    if ctypes.get_last_error() == winapi.ERROR_ALREADY_EXISTS:
        if not args.autostart:
            from tray import request_show_existing
            if not request_show_existing():
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo("Tandem", "Программа уже запущена — её значок находится в трее.")
                root.destroy()
        return 0

    from app import App
    logging.info("Запуск (autostart=%s)", args.autostart)
    App(autostart_mode=args.autostart).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
