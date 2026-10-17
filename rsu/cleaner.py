"""清理执行：备份 → 删除，失败项不阻断其余流程。"""

from __future__ import annotations

import os

from . import backup
from . import win_svc
from . import winreg_api as wreg
from .models import CleanPlan, CleanResult, ItemType
from .restore_point import create_restore_point
from .util import log


def execute(plan: CleanPlan, selected: list[int], make_restore_point: bool,
            progress=None) -> CleanResult:
    """执行清理。progress(done, total, label) 在每次处理前调用。"""
    result = CleanResult()
    result.session_dir = backup.new_session()
    journal_path = os.path.join(result.session_dir, backup.JOURNAL_NAME)

    if make_restore_point:
        ok, err = create_restore_point("RS-Uninstaller: before cleaning")
        result.restore_point_created = ok
        if not ok:
            result.restore_point_error = err
        log(f"系统还原点：{'已创建' if ok else err}")

    journal = None
    try:
        journal = open(journal_path, "a", encoding="utf-8")
    except OSError as exc:
        log(f"无法创建日志文件：{exc}")

    total = len(selected)
    try:
        for position, index in enumerate(selected):
            item = plan.items[index]
            if progress:
                progress(position, total, item.label)

            ok = False
            error = ""

            if item.kind == ItemType.REGISTRY:
                snapshot = os.path.join(result.session_dir, "reg", f"{position}.json")
                saved, save_error = backup.save_reg_snapshot(item, snapshot)
                if not saved:
                    error = f"备份失败，已跳过删除（{save_error}）"
                else:
                    root = wreg.hive_handle(item.hive)
                    ok = wreg.delete_key_tree(root, item.view, item.reg_path)
                    if not ok:
                        error = "删除注册表项失败（权限不足或被占用）"
                    backup.append_journal(journal, f"R\t{snapshot}")

            elif item.kind in (ItemType.FOLDER, ItemType.FILE):
                ok, dest, move_error = backup.move_to_quarantine(item.target, result.session_dir)
                backup.append_journal(journal, f"F\t{item.target}\t{dest}")
                if not ok:
                    error = move_error

            elif item.kind == ItemType.SERVICE:
                ok, error = win_svc.stop_and_delete(item.target)
                backup.append_journal(journal, f"S\t{item.target}")

            result.total += 1
            if ok:
                result.ok += 1
            else:
                result.failed += 1
                message = f"{item.label}：{error or '未知错误'}"
                result.errors.append(message)
                log("清理失败 - " + message)
    finally:
        if journal:
            journal.close()

    if progress:
        progress(total, total, "完成")

    log(f"清理结束：成功 {result.ok}，失败 {result.failed}")
    return result
