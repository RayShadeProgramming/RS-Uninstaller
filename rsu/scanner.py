"""已安装软件扫描：读取注册表 Uninstall 三处来源并过滤系统项。"""

from __future__ import annotations

import winreg

from . import winreg_api as wreg
from .models import SoftwareItem
from .util import log

UNINSTALL_BASE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"

_NOISE_RELEASE_TYPES = {"update", "hotfix", "security update", "servicepack", "service pack"}
_NOISE_PREFIXES = ("update for ", "security update for ", "hotfix for ")


def _is_noise(release_type: str, display_name: str) -> bool:
    if (release_type or "").strip().lower() in _NOISE_RELEASE_TYPES:
        return True
    name = (display_name or "").strip().lower()
    return any(name.startswith(prefix) for prefix in _NOISE_PREFIXES)


def _scan_root(hive: str, root, view: int, is_64: bool, out: list[SoftwareItem], seen: set[str]) -> None:
    for sub in wreg.enum_subkeys(root, view, UNINSTALL_BASE):
        path = f"{UNINSTALL_BASE}\\{sub}"
        display_name = (wreg.read_string(root, view, path, "DisplayName") or "").strip()
        if not display_name:
            continue

        system_component = wreg.read_dword(root, view, path, "SystemComponent")
        if system_component == 1:
            continue

        parent_key = wreg.read_string(root, view, path, "ParentKeyName")
        if parent_key:
            continue

        release_type = wreg.read_string(root, view, path, "ReleaseType") or ""
        if _is_noise(release_type, display_name):
            continue

        item = SoftwareItem(
            display_name=display_name,
            hive=hive,
            view=view,
            reg_path=path,
            is_64=is_64,
        )
        item.version = (wreg.read_string(root, view, path, "DisplayVersion") or "").strip()
        item.publisher = (wreg.read_string(root, view, path, "Publisher") or "").strip()
        item.install_location = (wreg.read_string(root, view, path, "InstallLocation") or "").strip()
        item.uninstall_string = wreg.read_string(root, view, path, "UninstallString") or ""
        item.display_icon = wreg.read_string(root, view, path, "DisplayIcon") or ""
        item.install_date = (wreg.read_string(root, view, path, "InstallDate") or "").strip()

        size = wreg.read_dword(root, view, path, "EstimatedSize")
        if size:
            item.estimated_size_kb = int(size)

        item.windows_installer = wreg.read_dword(root, view, path, "WindowsInstaller") == 1

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
