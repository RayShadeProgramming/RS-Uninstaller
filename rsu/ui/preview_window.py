"""清理预览窗口：勾选清理项、确认、执行并展示进度。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from ..cleaner import execute
from ..models import ItemType
from ..trace import build_clean_plan
from ..util import format_bytes
from .widgets import CheckTreeview

TYPE_NAMES = {
    ItemType.REGISTRY: "注册表",
    ItemType.FOLDER: "目录",
    ItemType.FILE: "文件",
    ItemType.SERVICE: "服务",
}


class PreviewWindow(tk.Toplevel):
    def __init__(self, master, item, on_done=None):
        super().__init__(master)
        self.item = item
        self.on_done = on_done
        self.plan = build_clean_plan(item)
        self.queue: queue.Queue = queue.Queue()
        self.running = False
        self.total = 0

        self.withdraw()
        self.title(f"清理预览 - {item.display_name}")
        self.resizable(True, True)
        self._build()
        self._populate()
        self._center(master)
        self.deiconify()

        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -------------------------------------------------------------- 界面

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        pad = 14

        title = ttk.Label(self, text=self.item.display_name,
                          font=("Microsoft YaHei UI", 12, "bold"))
        title.grid(row=0, column=0, sticky="w", padx=pad, pady=(pad, 0))

        subtitle_parts = []
        if self.item.publisher:
            subtitle_parts.append(self.item.publisher)
        if self.item.version:
            subtitle_parts.append(f"版本 {self.item.version}")
        if self.item.install_location:
            subtitle_parts.append(self.item.install_location)
        ttk.Label(self, text="  ·  ".join(subtitle_parts) or "—",
                  foreground="#555555").grid(row=1, column=0, sticky="w",
                                             padx=pad, pady=(0, 8))

        body = ttk.Frame(self)
        body.grid(row=2, column=0, sticky="nsew", padx=pad)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.tree = CheckTreeview(
            body,
            columns=("type", "label", "detail", "size"),
        )
        self.tree.heading("type", text="类型")
        self.tree.heading("label", text="项目")
        self.tree.heading("detail", text="位置 / 说明")
        self.tree.heading("size", text="大小")
        self.tree.column("type", width=80, anchor="center", stretch=False)
        self.tree.column("label", width=240, anchor="w", stretch=False)
        self.tree.column("detail", width=470, anchor="w", stretch=True)
        self.tree.column("size", width=90, anchor="e", stretch=False)

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        options = ttk.Frame(self)
        options.grid(row=3, column=0, sticky="ew", padx=pad, pady=(8, 0))

        self.var_restore_point = tk.BooleanVar(value=True)
        self.chk_restore = ttk.Checkbutton(
            options, text="清理前创建系统还原点（推荐）",
            variable=self.var_restore_point,
        )
        self.chk_restore.grid(row=0, column=0, sticky="w")

        self.var_keep_backup = tk.BooleanVar(value=False)
        self.chk_keep_backup = ttk.Checkbutton(
            options, text="保留备份到隔离区（可还原）",
            variable=self.var_keep_backup,
        )
        self.chk_keep_backup.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Label(
            options,
            text="默认永久删除，不保留备份；勾选后文件移入隔离区，可随时还原。",
            foreground="#777777",
        ).grid(row=2, column=0, sticky="w", pady=(2, 0))

        self.status = tk.StringVar(value="")
        ttk.Label(options, textvariable=self.status, foreground="#555555").grid(
            row=3, column=0, sticky="w", pady=(6, 0)
        )

        self.progress = ttk.Progressbar(options, mode="determinate", maximum=1)
        self.progress.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        options.columnconfigure(0, weight=1)

        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="e", padx=pad, pady=(10, pad))
        self.btn_cancel = ttk.Button(actions, text="取消", width=12,
                                     command=self._on_close)
        self.btn_cancel.grid(row=0, column=0, padx=(0, 8))
        self.btn_start = ttk.Button(actions, text="开始清理", width=14,
                                    command=self._start)
        self.btn_start.grid(row=0, column=1)

    def _center(self, master) -> None:
        self.update_idletasks()
        width = max(900, self.winfo_reqwidth())
        height = max(600, self.winfo_reqheight())
        try:
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        except tk.TclError:
            x = y = 120
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    def _populate(self) -> None:
        for index, clean_item in enumerate(self.plan.items):
            iid = str(index)
            self.tree.insert("", "end", iid=iid, values=(
                TYPE_NAMES.get(clean_item.kind, clean_item.kind),
                clean_item.label,
                clean_item.detail,
                format_bytes(clean_item.size) if clean_item.size else "—",
            ))
            self.tree.set_checked(iid, True)

        summary = (
            f"将清理 {len(self.plan.items)} 项，合计约 "
            f"{format_bytes(self.plan.total_size)}"
        )
        if not any(entry.kind == ItemType.FOLDER for entry in self.plan.items):
            summary += "　⚠ 未定位到安装目录，请谨慎确认"
        self.status.set(summary)

    # -------------------------------------------------------------- 执行

    def _start(self) -> None:
        selected = [int(iid) for iid in self.tree.checked_items()]
        if not selected:
            messagebox.showinfo("提示", "没有勾选任何要清理的内容。", parent=self)
            return

        total_size = sum(self.plan.items[i].size for i in selected)
        keep_backup = bool(self.var_keep_backup.get())

        if keep_backup:
            backup_lines = (
                "• 文件与目录会移动到隔离区，可随时还原\n"
                "• 注册表项会先导出备份，再删除\n"
            )
        else:
            backup_lines = (
                "• 文件与目录将被【永久删除】，无法从隔离区恢复\n"
                "• 注册表项将直接删除，不保留备份\n"
            )

        question = (
            f"即将清理 {len(selected)} 项内容（约 {format_bytes(total_size)}）。\n\n"
            f"{backup_lines}"
            "• 服务会被停止并删除\n\n"
            "是否继续？"
        )
        if not messagebox.askyesno("确认清理", question, icon="warning",
                                   default=messagebox.NO, parent=self):
            return

        self.running = True
        self.total = len(selected)
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.chk_restore.configure(state="disabled")
        self.chk_keep_backup.configure(state="disabled")
        self.progress.configure(maximum=max(1, self.total), value=0)
        self.status.set("正在清理，请稍候…")

        make_restore_point = bool(self.var_restore_point.get())
        thread = threading.Thread(
            target=self._worker, args=(selected, make_restore_point, keep_backup),
            daemon=True,
        )
        thread.start()
        self.after(100, self._poll)

    def _worker(self, selected: list[int], make_restore_point: bool,
                keep_backup: bool) -> None:
        try:
            result = execute(
                self.plan, selected, make_restore_point, keep_backup,
                progress=lambda done, total, _label: self.queue.put(
                    ("progress", done, total)
                ),
            )
            self.queue.put(("done", result))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", str(exc)))

    def _poll(self) -> None:
        try:
            while True:
                message = self.queue.get_nowait()
                if message[0] == "progress":
                    done, total = message[1], message[2]
                    self.progress.configure(value=done)
                    self.status.set(f"正在清理… {done} / {total}")
                elif message[0] == "done":
                    self._finish(message[1])
                    return
                else:
                    self._fail(message[1])
                    return
        except queue.Empty:
            pass

        if self.running:
            self.after(100, self._poll)

    def _finish(self, result) -> None:
        self.running = False
        self.progress.configure(value=self.total)
        self.status.set("清理完成")

        lines = [
            "清理完成。",
            "",
            f"成功：{result.ok} 项",
            f"失败：{result.failed} 项",
        ]
        if result.restore_point_created:
            lines.append("系统还原点：已创建")
        elif result.restore_point_error:
            lines.append(f"系统还原点：未创建（{result.restore_point_error}）")

        if result.kept_backup and result.session_dir:
            lines += ["", "备份目录：", result.session_dir]
        else:
            lines += ["", "备份：未保留（文件已永久删除，无法还原）"]

        if result.errors:
            lines += ["", "失败详情："]
            for error in result.errors[:6]:
                lines.append(f"• {error}")
            if len(result.errors) > 6:
                lines.append(f"… 其余 {len(result.errors) - 6} 项见日志")

        messagebox.showinfo("清理结果", "\n".join(lines), parent=self)

        if self.on_done:
            try:
                self.on_done()
            except Exception:  # noqa: BLE001
                pass
        self.destroy()

    def _fail(self, error: str) -> None:
        self.running = False
        messagebox.showerror("清理失败", f"执行过程中出现异常：\n{error}", parent=self)
        self.destroy()

    def _on_close(self) -> None:
        if self.running:
            self.bell()
            return
        self.destroy()
