"""通用工具：路径、格式化、日志、路径保护判断。"""

from __future__ import annotations

import datetime
import functools
import os
import sys
import threading

APP_NAME = "RS-Uninstaller"
APP_VERSION = "0.1.1"

_log_lock = threading.Lock()


# ------------------------------------------------------------------ 路径

def app_data_dir() -> str:
    base = os.environ.get("ProgramData") or r"C:\ProgramData"
    return os.path.join(base, APP_NAME)


def ensure_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def resource_path(relative: str) -> str:
    """兼容 PyInstaller 打包后的资源路径。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, relative)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, relative)


def normalize_path(path: str) -> str:
    try:
        p = os.path.abspath(path)
    except OSError:
        p = path
    return os.path.normcase(os.path.normpath(p)).rstrip("\\")


def now_stamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def now_readable() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ 日志

def log(message: str) -> None:
    try:
        with _log_lock:
            ensure_dir(app_data_dir())
            with open(os.path.join(app_data_dir(), "app.log"), "a", encoding="utf-8") as f:
                f.write(f"[{now_readable()}] {message}\n")
    except OSError:
        pass


# ------------------------------------------------------------------ 文本

def normalize_token(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def is_all_digits(text: str) -> bool:
    return bool(text) and text.isdigit()


def strip_decorations(name: str) -> str:
    """去掉结尾括号内容与版本号，得到更稳定的名称。"""
    s = (name or "").strip()
    for _ in range(4):
        t = s.strip()
        if t.endswith(")") and "(" in t:
            s = t[: t.rfind("(")].strip()
            continue
        parts = t.split()
        if parts:
            last = parts[-1]
            looks_version = last.isdigit() or (
                last.lower().startswith("v") and any(c.isdigit() for c in last)
            )
            if looks_version and t.rfind(last) > 0:
                s = t[: t.rfind(last)].strip()
                continue
        break
    return s


def format_bytes(size: int) -> str:
    size = int(size or 0)
    if size < 1024:
        return f"{size} B"
    value = float(size)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024.0:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} TB"


def format_install_date(raw: str) -> str:
    raw = (raw or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


# ------------------------------------------------------------------ 路径保护

@functools.lru_cache(maxsize=1)
def _protected_sets():
    exact: set[str] = set()
    prefix: set[str] = set()

    def add_exact(path: str) -> None:
        if path:
            exact.add(normalize_path(path))

    def add_prefix(path: str) -> None:
        if path:
            prefix.add(normalize_path(path))

    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    common_data = os.environ.get("ProgramData", r"C:\ProgramData")
    user_profile = os.environ.get("USERPROFILE", "")
    public_dir = os.environ.get("PUBLIC", r"C:\Users\Public")
    local_app = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")

    for path in (
        os.environ.get("SystemDrive", "C:") + "\\",
        sys_root,
        pf,
        pf86,
        common_data,
        user_profile,
        public_dir,
        local_app,
        roaming,
        os.path.join(local_app, "Low") if local_app else "",
        os.path.join(public_dir, "Desktop"),
        os.path.join(user_profile, "Desktop") if user_profile else "",
        os.path.join(user_profile, "Documents") if user_profile else "",
        os.path.join(user_profile, "Downloads") if user_profile else "",
        r"C:\Users",
        r"C:\PerfLogs",
        r"C:\Recovery",
        r"C:\$Recycle.Bin",
        r"C:\System Volume Information",
    ):
        add_exact(path)

    for path in (
        sys_root,
        os.path.join(pf, "Common Files"),
        os.path.join(pf86, "Common Files"),
        os.path.join(pf, "WindowsApps"),
    ):
        add_prefix(path)

    return frozenset(exact), frozenset(prefix)


def is_protected_path(path: str) -> bool:
    if not path:
        return True
    p = normalize_path(path)
    if len(p) <= 3:
        return True
    # 非盘符开头的路径（UNC、相对路径）一律拒绝
    if len(p) < 2 or p[1] != ":":
        return True

    exact, prefix = _protected_sets()
    if p in exact:
        return True
    for base in prefix:
        if p == base or p.startswith(base + "\\"):
            return True
    return False


def path_exists(path: str) -> bool:
    try:
        return os.path.exists(path)
    except OSError:
        return False


def dir_size(path: str, _depth: int = 0) -> int:
    """递归统计目录大小，跳过符号链接，限制深度避免异常结构。"""
    if _depth > 32 or not path:
        return 0
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        total += dir_size(entry.path, _depth + 1)
                    else:
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def path_size(path: str) -> int:
    if os.path.isdir(path):
        return dir_size(path)
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
