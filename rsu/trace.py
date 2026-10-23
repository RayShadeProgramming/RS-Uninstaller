"""清理清单生成：追踪文件目录、注册表项、快捷方式与服务。"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from . import win_svc
from . import winreg_api as wreg
from .models import CleanItem, CleanPlan, ItemType, SoftwareItem
from .util import (
    dir_size,
    is_protected_path,
    normalize_token,
    strip_decorations,
)

STOPWORDS = {
    "microsoft", "windows", "corporation", "corp", "inc", "ltd", "llc", "co",
    "company", "technologies", "technology", "software", "systems", "system",
    "studio", "the", "and", "for", "pro", "premium", "free", "version",
    "edition", "x86", "x64", "setup", "update", "app", "application",
    "suite", "client", "service", "pack", "driver", "runtime",
    "redistributable", "platform", "framework", "tool", "tools",
    "utility", "utilities", "personal", "home", "business",
}


class Matcher:
    def __init__(self, item: SoftwareItem):
        self.names: list[str] = []
        self.pub_tokens: list[str] = []

        for raw in (item.display_name, strip_decorations(item.display_name)):
            name = normalize_token(raw)
            if len(name) >= 3 and name not in self.names:
                self.names.append(name)

        for token in (item.publisher or "").split():
            norm = normalize_token(token)
            if (len(norm) >= 3 and norm not in STOPWORDS
                    and not norm.isdigit() and norm not in self.pub_tokens):
                self.pub_tokens.append(norm)

    def strong_match(self, candidate: str) -> bool:
        value = normalize_token(candidate)
        if len(value) < 3:
            return False
        for name in self.names:
            if value == name:
                return True
            if len(value) >= 5 and value in name:
                return True
            if len(name) >= 5 and name in value:
                return True
        return False

    def vendor_match(self, candidate: str) -> bool:
        value = normalize_token(candidate)
        if len(value) < 3:
            return False
        for token in self.pub_tokens:
            if value == token:
                return True
            if len(token) >= 4 and token in value:
                return True
        return False


# ------------------------------------------------------------------ 安装目录推导

def _command_exe(command: str) -> str:
    """从 UninstallString / DisplayIcon 中取出可执行文件路径。

    支持：
      - "C:\\App\\uninstall.exe" /S
      - C:\\App\\app.exe,0
      - MsiExec.exe /X{GUID}   （返回相对路径，调用方会过滤）
    """
    text = (command or "").strip()
    if not text:
        return ""
    if text.startswith('"'):
        end = text.find('"', 1)
        if end > 1:
            return text[1:end]
    lower = text.lower()
    index = lower.find(".exe")
    if index != -1:
        return text[: index + 4]
    return text.split()[0]


def _tiny_suffix(shorter: str, longer: str) -> bool:
    """longer 是否只比 shorter 多出 1~2 个相同字符（如 devc → devcpp）。"""
    if not shorter or not longer.startswith(shorter):
        return False
    extra = longer[len(shorter):]
    if not extra or len(extra) > 2:
        return False
    return len(set(extra)) == 1


def _loose_path_match(name: str, matcher: "Matcher") -> bool:
    """目录名与产品名的宽松匹配，用于定位安装目录。

    只在「完全相等」或「末尾多 1~2 个重复字符」时放宽，
    避免 Java → JavaFX 这类误伤。
    """
    value = normalize_token(name)
    if len(value) < 3:
        return False
    if matcher.strong_match(name):
        return True

    for candidate in matcher.names:
        if len(candidate) < 4:
            continue
        if _tiny_suffix(value, candidate) or _tiny_suffix(candidate, value):
            return True
    return False


# ------------------------------------------------------------------ 收集

def _has(plan: CleanPlan, kind: str, target: str) -> bool:
    target = target.lower()
    return any(item.kind == kind and item.target.lower() == target for item in plan.items)


def add_folder(plan: CleanPlan, path: str) -> None:
    if not path or not os.path.isdir(path):
        return
    full = os.path.abspath(path)
    if is_protected_path(full) or _has(plan, ItemType.FOLDER, full):
        return

    size = dir_size(full)
    plan.items.append(CleanItem(
        kind=ItemType.FOLDER,
        label=os.path.basename(full.rstrip("\\")) or full,
        detail=full,
        target=full,
        size=size,
    ))
    plan.total_size += size


def add_file(plan: CleanPlan, path: str) -> None:
    if not path or not os.path.isfile(path):
        return
    full = os.path.abspath(path)
    if is_protected_path(full) or _has(plan, ItemType.FILE, full):
        return

    try:
        size = os.path.getsize(full)
    except OSError:
        size = 0
    plan.items.append(CleanItem(
        kind=ItemType.FILE,
        label=os.path.basename(full),
        detail=full,
        target=full,
        size=size,
    ))
    plan.total_size += size


def add_registry(plan: CleanPlan, hive: str, view: int, path: str) -> None:
    if not path:
        return
    root = wreg.hive_handle(hive)
    if not wreg.key_exists(root, view, path):
        return

    full = wreg.full_path(hive, path)
    if any(item.kind == ItemType.REGISTRY and item.detail.lower() == full.lower()
           for item in plan.items):
        return

    plan.items.append(CleanItem(
        kind=ItemType.REGISTRY,
        label=path.rsplit("\\", 1)[-1],
        detail=full,
        target=full,
        hive=hive,
        view=view,
        reg_path=path,
    ))


def add_service(plan: CleanPlan, name: str, display: str) -> None:
    if not name or _has(plan, ItemType.SERVICE, name):
        return
    plan.items.append(CleanItem(
        kind=ItemType.SERVICE,
        label=display or name,
        detail=f"服务：{name}",
        target=name,
    ))


# ------------------------------------------------------------------ 扫描

def _scan_data_root(plan: CleanPlan, root: str, matcher: Matcher) -> None:
    if not root or not os.path.isdir(root):
        return
    try:
        entries = list(os.scandir(root))
    except OSError:
        return

    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue

        if _loose_path_match(entry.name, matcher):
            add_folder(plan, entry.path)
            continue

        if not matcher.vendor_match(entry.name):
            continue

        try:
            children = list(os.scandir(entry.path))
        except OSError:
            continue
        for child in children:
            try:
                if child.is_dir(follow_symlinks=False) and _loose_path_match(child.name, matcher):
                    add_folder(plan, child.path)
            except OSError:
                continue


def _fixed_drives() -> list[str]:
    """只枚举本机固定磁盘，避免光驱 / 可移动盘拖慢扫描。"""
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetLogicalDrives.restype = wintypes.DWORD
        kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetDriveTypeW.restype = wintypes.UINT
        mask = kernel32.GetLogicalDrives()
    except Exception:  # noqa: BLE001
        return []

    drives: list[str] = []
    for index in range(26):
        if not mask & (1 << index):
            continue
        root = f"{chr(ord('A') + index)}:\\"
        try:
            if kernel32.GetDriveTypeW(root) == 3:  # DRIVE_FIXED
                drives.append(root)
        except Exception:  # noqa: BLE001
            continue
    return drives


def _program_roots() -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()

    candidates: list[str] = []
    for drive in _fixed_drives():
        candidates.append(os.path.join(drive, "Program Files"))
        candidates.append(os.path.join(drive, "Program Files (x86)"))
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(env)
        if value:
            candidates.append(value)

    for path in candidates:
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(path):
            roots.append(path)
    return roots


def _scan_program_dirs(plan: CleanPlan, matcher: Matcher) -> None:
    """在 Program Files 下按名称匹配目录。

    覆盖「注册表里没有 InstallLocation / DisplayIcon 可用路径」的软件，
    只扫一层目录（厂商目录再下探一层），开销很小。
    """
    for root in _program_roots():
        try:
            entries = list(os.scandir(root))
        except OSError:
            continue

        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue

            if _loose_path_match(entry.name, matcher):
                add_folder(plan, entry.path)
                continue

            if not matcher.vendor_match(entry.name):
                continue

            try:
                children = list(os.scandir(entry.path))
            except OSError:
                continue
            for child in children:
                try:
                    if child.is_dir(follow_symlinks=False) and \
                            _loose_path_match(child.name, matcher):
                        add_folder(plan, child.path)
                except OSError:
                    continue


def _scan_shortcut_dir(plan: CleanPlan, directory: str, matcher: Matcher, depth: int = 0) -> None:
    if depth > 2 or not os.path.isdir(directory):
        return
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return

    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                if matcher.strong_match(entry.name):
                    add_folder(plan, entry.path)
                else:
                    _scan_shortcut_dir(plan, entry.path, matcher, depth + 1)
            elif entry.name.lower().endswith(".lnk"):
                stem = entry.name[:-4]
                if matcher.strong_match(stem):
                    add_file(plan, entry.path)
        except OSError:
            continue


def _scan_desktop_links(plan: CleanPlan, directory: str, matcher: Matcher) -> None:
    if not directory or not os.path.isdir(directory):
        return
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    for entry in entries:
        try:
            if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(".lnk"):
                if matcher.strong_match(entry.name[:-4]):
                    add_file(plan, entry.path)
        except OSError:
            continue


def _scan_vendor_reg_root(plan: CleanPlan, hive: str, view: int, base: str,
                          matcher: Matcher) -> None:
    root = wreg.hive_handle(hive)
    for child in wreg.enum_subkeys(root, view, base):
        full = f"{base}\\{child}"
        norm_child = normalize_token(child)

        if norm_child in matcher.names:
            add_registry(plan, hive, view, full)
            continue

        subkeys = wreg.enum_subkeys(root, view, full)
        if not subkeys:
            if matcher.strong_match(child):
                add_registry(plan, hive, view, full)
            continue

        # 有子键且只是包含式匹配：可能为厂商键，只删除匹配的子键
        if matcher.strong_match(child) or matcher.vendor_match(child):
            for sub in subkeys:
                if matcher.strong_match(sub):
                    add_registry(plan, hive, view, f"{full}\\{sub}")


def _scan_services(plan: CleanPlan, install_location: str) -> None:
    if not install_location:
        return
    target = os.path.abspath(install_location).lower()
    if len(target) < 4:
        return

    try:
        services = win_svc.list_services()
    except Exception:
        return

    for service in services:
        image = (service.get("image") or "").lower()
        if image and target in image:
            add_service(plan, service.get("name", ""), service.get("display", ""))


# ------------------------------------------------------------------ 入口

def build_clean_plan(item: SoftwareItem) -> CleanPlan:
    plan = CleanPlan()
    matcher = Matcher(item)

    # 1) 卸载注册表项
    add_registry(plan, item.hive, item.view, item.reg_path)

    # 2) 厂商 / 产品注册表项
    _scan_vendor_reg_root(plan, "HKCU", wreg.VIEW_64, "Software", matcher)
    _scan_vendor_reg_root(plan, "HKLM", wreg.VIEW_64, "Software", matcher)
    _scan_vendor_reg_root(plan, "HKLM", wreg.VIEW_32, "Software", matcher)

    # 3) 安装目录：InstallLocation → DisplayIcon / UninstallString → Program Files 扫描
    candidates: list[str] = []
    if item.install_location:
        location = item.install_location
        if os.path.isfile(location):
            location = os.path.dirname(location)
        candidates.append(location)

    for raw in (item.display_icon, item.uninstall_string):
        exe = _command_exe(raw)
        if exe and os.path.isabs(exe):
            directory = os.path.dirname(exe)
            if directory and _loose_path_match(os.path.basename(directory), matcher):
                candidates.append(directory)

    for directory in candidates:
        add_folder(plan, directory)

    # 仍未定位到目录时，逐级扩大搜索范围
    if not any(entry.kind == ItemType.FOLDER for entry in plan.items):
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env)
            if base:
                add_folder(plan, os.path.join(base, item.display_name))

    if not any(entry.kind == ItemType.FOLDER for entry in plan.items):
        _scan_program_dirs(plan, matcher)

    # 4) 用户数据目录
    local_app = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    common_data = os.environ.get("ProgramData", "")

    _scan_data_root(plan, local_app, matcher)
    _scan_data_root(plan, roaming, matcher)
    _scan_data_root(plan, common_data, matcher)
    if local_app:
        _scan_data_root(plan, os.path.join(local_app, "Programs"), matcher)

    # 5) 开始菜单与桌面快捷方式
    start_common = os.path.join(common_data, r"Microsoft\Windows\Start Menu\Programs")
    start_user = os.path.join(roaming, r"Microsoft\Windows\Start Menu\Programs")
    _scan_shortcut_dir(plan, start_common, matcher)
    _scan_shortcut_dir(plan, start_user, matcher)

    _scan_desktop_links(plan, os.path.join(os.environ.get("PUBLIC", ""), "Desktop"), matcher)
    _scan_desktop_links(plan, os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"), matcher)

    # 6) 相关服务
    if item.install_location:
        _scan_services(plan, item.install_location)

    return plan
