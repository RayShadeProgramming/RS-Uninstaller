"""数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


class ItemType:
    REGISTRY = "registry"
    FOLDER = "folder"
    FILE = "file"
    SERVICE = "service"


@dataclass
class SoftwareItem:
    display_name: str
    version: str = ""
    publisher: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    display_icon: str = ""
    install_date: str = ""
    estimated_size_kb: int = 0
    windows_installer: bool = False
    is_64: bool = True
    hive: str = "HKLM"
    view: int = 0
    reg_path: str = ""


@dataclass
class CleanItem:
    kind: str
    label: str
    detail: str
    target: str = ""
    hive: str = ""
    view: int = 0
    reg_path: str = ""
    size: int = 0


@dataclass
class CleanPlan:
    items: list[CleanItem] = field(default_factory=list)
    total_size: int = 0


@dataclass
class CleanResult:
    total: int = 0
    ok: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    session_dir: str = ""
    kept_backup: bool = False
    restore_point_created: bool = False
    restore_point_error: str = ""


@dataclass
class RestoreResult:
    files: int = 0
    regs: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
