"""备份与还原：注册表快照、文件隔离区、还原点。"""

from __future__ import annotations

import json
import os
import shutil
import winreg

from . import winreg_api as wreg
from .models import CleanItem, RestoreResult
from .restore_point import create_restore_point
from .util import (
    app_data_dir,
    ensure_dir,
    format_bytes,
    log,
    now_stamp,
    path_exists,
)

JOURNAL_NAME = "journal.tsv"


# ------------------------------------------------------------------ 隔离区

def quarantine_root() -> str:
    return os.path.join(app_data_dir(), "Quarantine")


def new_session() -> str:
    base = quarantine_root()
    ensure_dir(base)
    stamp = now_stamp()
    session = os.path.join(base, stamp)
    suffix = 1
    while os.path.exists(session):
        session = os.path.join(base, f"{stamp}-{suffix}")
        suffix += 1
    ensure_dir(os.path.join(session, "files"))
    ensure_dir(os.path.join(session, "reg"))
    return session


def move_to_quarantine(src: str, session: str) -> tuple[bool, str, str]:
    """返回 (是否成功, 备份路径, 错误信息)。"""
    full = os.path.abspath(src)
    if not os.path.exists(full):
        return False, "", "路径不存在"

    drive, rest = os.path.splitdrive(full)
    relative = (drive.rstrip(":") or "X") + rest
    dest = os.path.join(session, "files", relative)
    ensure_dir(os.path.dirname(dest))

    try:
        shutil.move(full, dest)
    except Exception as first_error:  # noqa: BLE001
        try:
            if os.path.isdir(full):
                shutil.copytree(full, dest, dirs_exist_ok=True)
                shutil.rmtree(full)
            else:
                ensure_dir(os.path.dirname(dest))
                shutil.copy2(full, dest)
                os.remove(full)
        except Exception as second_error:  # noqa: BLE001
            return False, dest, f"移动失败：{second_error}（原始错误：{first_error}）"

    if os.path.exists(full):
        return False, dest, "已备份，但原路径仍然存在（文件可能被占用）"
    return True, dest, ""


# ------------------------------------------------------------------ 注册表快照

def _encode_value(value):
    if isinstance(value, bytes):
        return {"k": "b", "v": value.hex()}
    return {"k": "n", "v": value}


def _decode_value(payload):
    if payload.get("k") == "b":
        return bytes.fromhex(payload.get("v", ""))
    return payload.get("v")


def _collect_key(hive: str, view: int, path: str, out: list[dict], depth: int = 0) -> None:
    if depth > 64:
        return
    root = wreg.hive_handle(hive)
    if not wreg.key_exists(root, view, path):
        return

    values = []
    for name, value, kind in wreg.enum_values(root, view, path):
        values.append({"name": name, "type": kind, "data": _encode_value(value)})

    out.append({"path": path, "values": values})

    for sub in wreg.enum_subkeys(root, view, path):
        _collect_key(hive, view, f"{path}\\{sub}", out, depth + 1)


def save_reg_snapshot(item: CleanItem, out_file: str) -> tuple[bool, str]:
    """把注册表项及其子键完整导出为 JSON 快照。"""
    try:
        ensure_dir(os.path.dirname(out_file))
        keys: list[dict] = []
        _collect_key(item.hive, item.view, item.reg_path, keys)
        if not keys:
            return False, "注册表项不存在或无法读取"

        payload = {
            "version": 1,
            "hive": item.hive,
            "view": wreg.view_name(item.view),
            "keys": keys,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def restore_reg_snapshot(path: str) -> tuple[bool, str]:
    if not path_exists(path):
        return False, "备份文件不存在"
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as exc:
        return False, f"读取备份失败：{exc}"

    hive = payload.get("hive", "HKLM")
    view = wreg.VIEW_32 if str(payload.get("view")) == "32" else wreg.VIEW_64
    root = wreg.hive_handle(hive)

    ok = True
    for entry in payload.get("keys", []):
        try:
            key = wreg.create_key(root, view, entry.get("path", ""))
        except OSError:
            ok = False
            continue
        try:
            for value in entry.get("values", []):
                name = value.get("name", "")
                kind = int(value.get("type", winreg.REG_SZ))
                data = _decode_value(value.get("data", {}))
                try:
                    winreg.SetValueEx(key, name, 0, kind, data)
                except OSError:
                    ok = False
        finally:
            key.Close()

    return ok, "" if ok else "部分注册表内容还原失败"


# ------------------------------------------------------------------ 日志文件

def append_journal(handle, line: str) -> None:
    if handle is None:
        return
    try:
        handle.write(line + "\n")
        handle.flush()
    except OSError:
        pass


# ------------------------------------------------------------------ 还原

def _merge_tree(src: str, dst: str) -> bool:
    """把备份目录中缺失的文件补回目标目录，已存在的文件不覆盖。"""
    ok = True
    ensure_dir(dst)
    try:
        entries = list(os.scandir(src))
    except OSError:
        return False
    for entry in entries:
        try:
            target = os.path.join(dst, entry.name)
            if entry.is_dir(follow_symlinks=False):
                if not _merge_tree(entry.path, target):
                    ok = False
            elif not os.path.exists(target):
                ensure_dir(os.path.dirname(target))
                shutil.copy2(entry.path, target)
        except OSError:
            ok = False
    return ok


def _restore_file(orig: str, backup: str, result: RestoreResult) -> None:
    if not path_exists(backup):
        result.failed += 1
        result.errors.append(f"备份缺失：{orig}")
        return

    if path_exists(orig):
        if os.path.isdir(backup) and os.path.isdir(orig) and _merge_tree(backup, orig):
            result.files += 1
        else:
            result.failed += 1
            result.errors.append(f"目标已存在，跳过：{orig}")
        return

    try:
        ensure_dir(os.path.dirname(orig))
        shutil.move(backup, orig)
        result.files += 1
    except Exception as exc:  # noqa: BLE001
        result.failed += 1
        result.errors.append(f"还原失败：{orig}（{exc}）")


def restore_session(session_dir: str) -> RestoreResult:
    result = RestoreResult()
    journal = os.path.join(session_dir, JOURNAL_NAME)

    try:
        with open(journal, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        result.failed += 1
        result.errors.append("找不到 journal.tsv")
        return result

    for line in lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue

        kind = parts[0]
        if kind == "F" and len(parts) >= 3:
            _restore_file(parts[1], parts[2], result)
        elif kind == "R":
            ok, err = restore_reg_snapshot(parts[1])
            if ok:
                result.regs += 1
            else:
                result.failed += 1
                result.errors.append(f"注册表还原失败：{parts[1]}（{err}）")

    log(f"还原完成：文件 {result.files}，注册表 {result.regs}，失败 {result.failed}")
    return result


def list_sessions() -> list[str]:
    root = quarantine_root()
    if not os.path.isdir(root):
        return []
    try:
        names = [entry.name for entry in os.scandir(root) if entry.is_dir()]
    except OSError:
        return []
    return sorted(names, reverse=True)


__all__ = [
    "quarantine_root",
    "new_session",
    "move_to_quarantine",
    "save_reg_snapshot",
    "restore_reg_snapshot",
    "append_journal",
    "restore_session",
    "list_sessions",
    "create_restore_point",
    "format_bytes",
]
