"""隔离区窗口：查看历史清理会话并还原。"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from ..backup import list_sessions, quarantine_root, restore_session


class QuarantineWindow(tk.Toplevel):
    def __init__(self, master, on_done=None):
        super().__init__(master)
        self.on_done = on_done
        self.sessions: list[str] = []

        self.withdraw()
        self.title("隔离区 / 还原 - RS-Uninstaller")
        self._build()
        self._center(master)
        self.deiconify()
        self.transient(master)
        self.grab_set()

        self.reload()

    # -------------------------------------------------------------- 界面

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        pad = 12

        body = ttk.Frame(self)
        body.grid(row=0, column=0, sticky="nsew", padx=pad, pady=(pad, 0))
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(body, columns=("time", "path"),
                                 show="headings", selectmode="browse")
        self.tree.heading("time", text="会话时间")
        self.tree.heading("path", text="备份路径")
        self.tree.column("time", width=180, anchor="w", stretch=False)
        self.tree.column("path", width=620, anchor="w", stretch=True)
        self.tree.bind("<Double-1>", lambda _e: self.open_folder())

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        footer = ttk.Frame(self)
        footer.grid(row=1, column=0, sticky="ew", padx=pad, pady=10)
        footer.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self.status, foreground="#555555").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(footer, text="打开目录", width=12,
                   command=self.open_folder).grid(row=0, column=1, padx=(8, 8))
        ttk.Button(footer, text="还原此会话", width=14,
                   command=self.restore_selected).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(footer, text="关闭", width=10,
                   command=self.destroy).grid(row=0, column=3)

    def _center(self, master) -> None:
        self.update_idletasks()
        width, height = 900, 520
        try:
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        except tk.TclError:
            x = y = 140
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    # -------------------------------------------------------------- 数据

    def reload(self) -> None:
        self.sessions = list_sessions()
        self.tree.delete(*self.tree.get_children(""))

        for index, name in enumerate(self.sessions):
            self.tree.insert("", "end", iid=str(index), values=(
                name,
                os.path.join(quarantine_root(), name),
            ))

        if self.sessions:
            self.status.set(f"共 {len(self.sessions)} 个清理会话。选择后点击「还原此会话」。")
        else:
            self.status.set("隔离区目前为空。执行清理后，被删除的文件会出现在这里。")

    def _selected_session(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            return None
        index = int(selection[0])
        return self.sessions[index] if 0 <= index < len(self.sessions) else None

    # -------------------------------------------------------------- 操作

    def open_folder(self) -> None:
        folder = quarantine_root()
        try:
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)  # noqa: S606
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc), parent=self)

    def restore_selected(self) -> None:
        name = self._selected_session()
        if not name:
            messagebox.showinfo("提示", "请先选择一个清理会话。", parent=self)
            return

        if not messagebox.askyesno(
            "确认还原",
            "将把该会话中备份的文件还原到原位置，并重新导入注册表备份。\n\n"
            "若目标位置已存在同名文件，将跳过。是否继续？",
            icon="question", default=messagebox.NO, parent=self,
        ):
            return

        session_path = os.path.join(quarantine_root(), name)
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            result = restore_session(session_path)
        except Exception as exc:  # noqa: BLE001
            result = None
            messagebox.showerror("还原失败", str(exc), parent=self)
        finally:
            self.configure(cursor="")

        if result is None:
            return

        lines = [
            "还原完成。",
            "",
            f"文件：{result.files} 项",
            f"注册表：{result.regs} 项",
            f"失败：{result.failed} 项",
        ]
        if result.errors:
            lines.append("")
            lines.append("详情：")
            for error in result.errors[:5]:
                lines.append(f"• {error}")

        messagebox.showinfo("还原结果", "\n".join(lines), parent=self)

        if self.on_done:
            try:
                self.on_done()
            except Exception:  # noqa: BLE001
                pass
        self.reload()
