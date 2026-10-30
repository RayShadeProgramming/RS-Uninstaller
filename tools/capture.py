"""开发辅助：按窗口标题抓取窗口内容（PrintWindow，不抢焦点）。"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from PIL import Image, ImageGrab

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:  # noqa: BLE001
    pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def find_window(title_part: str) -> int:
    found = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if title_part in buf.value:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found[0] if found else 0


def capture(hwnd: int) -> Image.Image:
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    # 置顶但不抢焦点，随后整屏抓取，避免 PrintWindow 拿到旧帧
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE_NOSIZE = 0x0002 | 0x0001
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE_NOSIZE)
    time.sleep(0.6)
    image = ImageGrab.grab()
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE_NOSIZE)

    if width > 0 and height > 0:
        image = image.crop((rect.left, rect.top, rect.right, rect.bottom))
    return image.convert("RGB")


def main() -> None:
    title = sys.argv[1] if len(sys.argv) > 1 else "RS-Uninstaller"
    out = sys.argv[2] if len(sys.argv) > 2 else "shot.png"

    hwnd = find_window(title)
    if not hwnd:
        print("window not found")
        return

    image = capture(hwnd)
    image.save(out)
    print(f"saved {out} {image.size[0]}x{image.size[1]}")


if __name__ == "__main__":
    main()
