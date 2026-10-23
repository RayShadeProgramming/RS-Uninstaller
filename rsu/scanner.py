"""已安装软件扫描：读取注册表 Uninstall 三处来源并过滤系统项。

性能要点：每个软件只打开一次注册表键，一次性读取全部值，
避免「每个字段打开一次键」造成的重复开销。
"""

from __future__ import annotations

import os
import winreg

from . import winreg_api as wreg
from .models import SoftwareItem
from .util import log

UNINSTALL_BASE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"

_NOISE_RELEASE_TYPES = {"update", "hotfix", "security update", "servicepack", "service pack"}
_NOISE_PREFIXES = ("update for ", "security update for ", "hotfix for ")


def _string_value(values: dict, name: str) -> str:
    entry = values.get(name)
    if not entry:
        return ""
    value, kind = entry
    if not isinstance(value, str):
        return ""
    if kind == winreg.REG_EXPAND_SZ:
        value = os.path.expandvars(value)
    return value.strip()


def _dword_value(values: dict, name: str) -> int:
    entry = values.get(name)
    if not entry:
        return 0
    value, kind = entry
    if kind != winreg.REG_DWORD or not isinstance(value, int):
        return 0
    return int(value)


def _is_noise(release_type: str, display_name: str) -> bool:
    if (release_type or "").strip().lower() in _NOISE_RELEASE_TYPES:
        return True
    name = (display_name or "").strip().lower()
    return any(name.startswith(prefix) for prefix in _NOISE_PREFIXES)


def _scan_root(hive: str, root, view: int, is_64: bool,
               out: list[SoftwareItem], seen: set[str]) -> None:
    for sub in wreg.enum_subkeys(root, view, UNINSTALL_BASE):
        path = f"{UNINSTALL_BASE}\\{sub}"
        values = wreg.read_values(root, view, path)
        if not values:
            continue

        display_name = _string_value(values, "DisplayName")
        if not display_name:
            continue

        if _dword_value(values, "SystemComponent") == 1:
            continue

        if _string_value(values, "ParentKeyName"):
            continue

        if _is_noise(_string_value(values, "ReleaseType"), display_name):
            continue

        item = SoftwareItem(
            display_name=display_name,
            hive=hive,
            view=view,
            reg_path=path,
            is_64=is_64,
        )
        item.version = _string_value(values, "DisplayVersion")
        item.publisher = _string_value(values, "Publisher")
        item.install_location = _string_value(values, "InstallLocation")
        item.uninstall_string = _string_value(values, "UninstallString")
        item.display_icon = _string_value(values, "DisplayIcon")
        item.install_date = _string_value(values, "InstallDate")
        item.estimated_size_kb = _dword_value(values, "EstimatedSize")
        item.windows_installer = _dword_value(values, "WindowsInstaller") == 1

        location = item.install_location
        if len(location) >= 2 and location[0] == '"' and location[-1] == '"':
            item.install_location = location[1:-1]

        key = f"{display_name.lower()}|{item.install_location.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)


def scan_installed_software() -> list[SoftwareItem]:
    out: list[SoftwareItem] = []
    seen: set[str] = set()

    sources = (
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, wreg.VIEW_64, True),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE, wreg.VIEW_32, False),
        ("HKCU", winreg.HKEY_CURRENT_USER, wreg.VIEW_64, True),
        ("HKCU", winreg.HKEY_CURRENT_USER, wreg.VIEW_32, False),
    )
    for hive, root, view, is_64 in sources:
        try:
            _scan_root(hive, root, view, is_64, out, seen)
        except OSError as exc:
            log(f"扫描 {hive} 失败：{exc}")

    out.sort(key=lambda item: item.display_name.lower())
    return out
