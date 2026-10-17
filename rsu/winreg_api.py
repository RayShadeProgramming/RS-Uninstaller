"""注册表访问封装（仅使用标准库 winreg）。"""

from __future__ import annotations

import os
import winreg

VIEW_64 = winreg.KEY_WOW64_64KEY
VIEW_32 = winreg.KEY_WOW64_32KEY

HIVES = {
    "HKLM": winreg.HKEY_LOCAL_MACHINE,
    "HKCU": winreg.HKEY_CURRENT_USER,
}


def hive_handle(hive: str):
    return HIVES.get(hive, winreg.HKEY_LOCAL_MACHINE)


def view_name(view: int) -> str:
    return "32" if view & VIEW_32 else "64"


def full_path(hive: str, path: str) -> str:
    return f"{hive}\\{path}" if path else hive


def read_string(root, view: int, path: str, name: str):
    """读取字符串值；不存在或类型不符时返回 None。"""
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
            value, kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    if not isinstance(value, str):
        return None
    if kind == winreg.REG_EXPAND_SZ:
        value = os.path.expandvars(value)
    return value


def read_dword(root, view: int, path: str, name: str):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
            value, kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    if kind != winreg.REG_DWORD or not isinstance(value, int):
        return None
    return value


def key_exists(root, view: int, path: str) -> bool:
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view):
            return True
    except OSError:
        return False


def enum_subkeys(root, view: int, path: str) -> list[str]:
    out: list[str] = []
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
            index = 0
            while True:
                try:
                    out.append(winreg.EnumKey(key, index))
                except OSError:
                    break
                index += 1
    except OSError:
        return []
    return out


def enum_values(root, view: int, path: str) -> list[tuple[str, object, int]]:
    """返回 [(名称, 数据, 类型)]。"""
    out: list[tuple[str, object, int]] = []
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
            index = 0
            while True:
                try:
                    name, value, kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                out.append((name, value, kind))
                index += 1
    except OSError:
        return []
    return out


def create_key(root, view: int, path: str):
    return winreg.CreateKeyEx(root, path, 0, winreg.KEY_WRITE | view)


def delete_key_tree(root, view: int, path: str) -> bool:
    """递归删除注册表键。"""
    if not path:
        return False

    subkeys = enum_subkeys(root, view, path)
    if not subkeys and not key_exists(root, view, path):
        return True  # 已不存在

    for sub in subkeys:
        delete_key_tree(root, view, f"{path}\\{sub}")

    parent, _, leaf = path.rpartition("\\")
    if not leaf:
        return False

    try:
        if parent:
            with winreg.OpenKey(root, parent, 0, winreg.KEY_ALL_ACCESS | view) as parent_key:
                winreg.DeleteKey(parent_key, leaf)
        else:
            winreg.DeleteKey(root, leaf)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
