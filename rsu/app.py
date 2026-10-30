"""应用入口：管理员权限检查 + NiceGUI 原生窗口启动。"""

from __future__ import annotations

import ctypes
import multiprocessing
import os
import threading
import time
from ctypes import wintypes

from .privileges import is_admin, relaunch_as_admin
from .util import APP_NAME, APP_VERSION, log, resource_path

WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
SPI_GETWORKAREA = 0x0030


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


def _work_area() -> tuple[int, int, int, int]:
    """返回任务栏之外的可用工作区（物理像素）。"""
    user32 = ctypes.windll.user32
    rect = _RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _favicon() -> str:
    path = resource_path(os.path.join("res", "icon.ico"))
    return path if os.path.exists(path) else "🗂️"


def _window_size() -> tuple[int, int]:
    """按屏幕工作区（排除任务栏）计算窗口尺寸，逻辑像素。"""
    try:
        user32 = ctypes.windll.user32
        try:
            dpi = user32.GetDpiForSystem()
        except Exception:  # noqa: BLE001
            dpi = 96
        scale = 96.0 / max(dpi, 96)
        left, top, right, bottom = _work_area()
        work_w = int((right - left) * scale)
        work_h = int((bottom - top) * scale)
    except Exception:  # noqa: BLE001
        return 1320, 860

    width = min(1320, max(980, work_w - 80))
    height = min(860, max(620, work_h - 70))
    return width, height


def _polish_window(title: str) -> None:
    """把系统标题栏切成深色，并换上应用图标（原生窗口默认是白色标题栏）。"""
    icon_path = resource_path(os.path.join("res", "icon.ico"))

    def worker() -> None:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        deadline = time.time() + 25
        while time.time() < deadline:
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                if os.path.exists(icon_path):
                    icon = user32.LoadImageW(
                        None, icon_path, 1, 0, 0, 0x10  # IMAGE_ICON, LR_LOADFROMFILE
                    )
                    if icon:
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, icon)
                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, icon)

                # 居中到可用工作区，保证底部操作栏不会被任务栏盖住
                rect = _RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                left, top, right, bottom = _work_area()
                win_w = rect.right - rect.left
                win_h = rect.bottom - rect.top
                x = left + max(0, ((right - left) - win_w) // 2)
                y = top + max(0, ((bottom - top) - win_h) // 2)
                user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)  # NOSIZE|NOZORDER

                # 部分系统需要等窗口真正显示后重复设置才生效（0 = 浅色标题栏）
                for _ in range(6):
                    value = ctypes.c_int(0)
                    dwmapi.DwmSetWindowAttribute(
                        hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
                    )
                    user32.SetWindowPos(
                        hwnd, 0, 0, 0, 0, 0,
                        0x0020 | 0x0002 | 0x0004 | 0x0001,  # FRAMECHANGED|NOMOVE|NOZORDER|NOSIZE
                    )
                    time.sleep(0.5)
                return
            time.sleep(0.25)

    threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    # PyInstaller + 多进程（NiceGUI 内部可能用到）必须调用
    multiprocessing.freeze_support()

    if os.name != "nt":
        raise SystemExit("RS-Uninstaller 仅支持 Windows。")

    if not is_admin():
        if relaunch_as_admin():
            return
        ctypes.windll.user32.MessageBoxW(
            None,
            "RS-Uninstaller 需要管理员权限才能清理系统目录与注册表。\n"
            "请右键选择「以管理员身份运行」。",
            APP_NAME,
            0x10,
        )
        return

    # 先注册页面，再启动服务；延迟导入避免多进程启动时重复执行界面代码
    from nicegui import ui

    from .ui_web.page_main import main_page  # noqa: F401  注册 "/" 页面

    title = f"{APP_NAME} {APP_VERSION}"
    width, height = _window_size()
    log(f"启动 {title}，窗口 {width}x{height}")
    _polish_window(title)
    ui.run(
        native=True,
        window_size=(width, height),
        title=title,
        favicon=_favicon(),
        reload=False,
        show=False,
    )


if __name__ == "__main__":
    main()
