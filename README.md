# Tandem

Дублирование окна на втором мониторе.

## Платформа
Windows 10/11, 64-бит, два монитора.

## Стек
- Python 3.9+, только стандартная библиотека
- tkinter — UI
- ctypes + WinAPI — захват окна, окно-дубль, трей
- Inno Setup 6 — установщик `.exe`
- WiX Toolset 5 — установщик `.msi`

## Сборка
| Файл | Что делает |
|---|---|
| `run.bat` | Запускает программу из исходников |
| `build-exe.bat` | Собирает `dist\Tandem-Setup.exe` |
| `build-msi.bat` | Собирает `dist\Tandem-Setup.msi` |