"""应用入口：权限检查、DPI、主题与主窗口。"""

from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import ttk

from .privileges import is_admin, relaunch_as_admin
from .ui.main_window import MainWindow
from .util import APP_NAME, APP_VERSION, log, resource_path


def _set_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def _apply_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    for theme in ("vista", "winnative", "clam"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    family = "Microsoft YaHei UI"
    root.option_add("*Font", (family, 10))
    style.configure(".", font=(family, 10))
    style.configure("Treeview", font=(family, 10), rowheight=28)
    style.configure("Treeview.Heading", font=(family, 10, "bold"))
    style.configure("TButton", padding=(10, 5))
    style.configure("TCheckbutton", padding=(0, 3))


def main() -> None:
    if os.name != "nt":
        raise SystemExit("RS-Uninstaller 仅支持 Windows。")

    if not is_admin():
        if relaunch_as_admin():
            raise SystemExit(0)
        ctypes.windll.user32.MessageBoxW(
            None,
            "RS-Uninstaller 需要管理员权限才能清理系统目录与注册表。\n"
            "请右键选择「以管理员身份运行」。",
            APP_NAME,
            0x10,
        )
        raise SystemExit(1)

    _set_dpi_awareness()

    root = tk.Tk()
    root.title(f"{APP_NAME} {APP_VERSION}")
    root.minsize(960, 580)

    try:
        root.iconbitmap(resource_path("res/icon.ico"))
    except tk.TclError:
        pass

    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:  # noqa: BLE001
        pass

    _apply_theme(root)

    width, height = 1120, 720
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = max((screen_w - width) // 2, 0)
    y = max((screen_h - height) // 2, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")

    MainWindow(root).pack(fill="both", expand=True)
    log(f"启动 {APP_NAME} {APP_VERSION}")
    root.mainloop()


if __name__ == "__main__":
    main()
