"""主窗口：软件列表、搜索、排序、入口按钮。"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ..models import SoftwareItem
from ..scanner import scan_installed_software
from ..util import format_bytes, format_install_date, log
from .preview_window import PreviewWindow
from .quarantine_window import QuarantineWindow


class MainWindow(ttk.Frame):
    COLUMNS = (
        ("name", "软件名称", 320, "w"),
        ("version", "版本", 110, "w"),
        ("publisher", "厂商", 190, "w"),
        ("size", "大小", 90, "e"),
        ("date", "安装日期", 100, "center"),
        ("location", "安装位置", 360, "w"),
    )

    def __init__(self, master):
        super().__init__(master, padding=12)
        self.master = master
        self.items: list[SoftwareItem] = []
        self.by_iid: dict[str, SoftwareItem] = {}
        self.sort_key = "name"
        self.sort_reverse = False
        self.last_scan = ""
        self.query = tk.StringVar()
        self.status = tk.StringVar(value="正在扫描…")

        self._build()
        self.query.trace_add("write", lambda *_: self.populate())

        # 每次启动都重新扫描；F5 / Ctrl+R 可随时手动刷新
        self.master.bind("<F5>", lambda _e: self.refresh())
        self.master.bind("<Control-r>", lambda _e: self.refresh())
        self.after(30, self.refresh)

    # -------------------------------------------------------------- 界面

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="搜索").grid(row=0, column=0, padx=(0, 6))
        self.search_entry = ttk.Entry(top, textvariable=self.query)
        self.search_entry.grid(row=0, column=1, sticky="ew", ipady=3)
        self.btn_refresh = ttk.Button(top, text="刷新 (F5)", width=12,
                                      command=self.refresh)
        self.btn_refresh.grid(row=0, column=2, padx=(8, 0))

        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            body,
            columns=[c[0] for c in self.COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for key, title, width, anchor in self.COLUMNS:
            self.tree.heading(key, text=title, command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor=anchor,
                             stretch=(key in ("name", "location")))

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())
        self.tree.bind("<Double-1>", lambda _e: self.open_preview())

        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, textvariable=self.status).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="隔离区 / 还原", width=16,
                   command=self.open_quarantine).grid(row=0, column=1, padx=(8, 8))
        self.btn_uninstall = ttk.Button(bottom, text="卸载选中软件", width=16,
                                        command=self.open_preview, state="disabled")
        self.btn_uninstall.grid(row=0, column=2)

    # -------------------------------------------------------------- 数据

    def refresh(self) -> None:
        self.btn_refresh.configure(state="disabled")
        self.configure(cursor="watch")
        self.status.set("正在扫描本机软件…")
        self.update_idletasks()
        try:
            self.items = scan_installed_software()
            self.last_scan = time.strftime("%H:%M:%S")
            log(f"扫描完成，共 {len(self.items)} 个软件")
        except Exception as exc:  # noqa: BLE001
            log(f"扫描失败：{exc}")
            self.items = []
        finally:
            self.configure(cursor="")
            self.btn_refresh.configure(state="normal")
        self.populate()

    def populate(self) -> None:
        query = self.query.get().strip().lower()

        rows = []
        for item in self.items:
            if query:
                haystack = " ".join((
                    item.display_name, item.publisher, item.version,
                    item.install_location,
                )).lower()
                if query not in haystack:
                    continue
            rows.append(item)

        rows.sort(key=lambda item: self._sort_value(item), reverse=self.sort_reverse)

        self.tree.delete(*self.tree.get_children(""))
        self.by_iid.clear()

        for index, item in enumerate(rows):
            iid = f"row{index}"
            size_text = (format_bytes(item.estimated_size_kb * 1024)
                         if item.estimated_size_kb else "—")
            self.tree.insert("", "end", iid=iid, values=(
                item.display_name,
                item.version or "—",
                item.publisher or "—",
                size_text,
                format_install_date(item.install_date) or "—",
                item.install_location or "—",
            ))
            self.by_iid[iid] = item

        text = f"共 {len(self.items)} 个软件"
        if len(rows) != len(self.items):
            text += f"，当前显示 {len(rows)} 个"
        if self.last_scan:
            text += f"　·　扫描于 {self.last_scan}"
        self.status.set(text)
        self._update_buttons()

    def _sort_value(self, item: SoftwareItem):
        if self.sort_key == "version":
            return item.version.lower()
        if self.sort_key == "publisher":
            return item.publisher.lower()
        if self.sort_key == "size":
            return item.estimated_size_kb
        if self.sort_key == "date":
            return item.install_date
        if self.sort_key == "location":
            return item.install_location.lower()
        return item.display_name.lower()

    def sort_by(self, key: str) -> None:
        if key == self.sort_key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = False
        self.populate()

    # -------------------------------------------------------------- 交互

    def _selected(self) -> SoftwareItem | None:
        selection = self.tree.selection()
        return self.by_iid.get(selection[0]) if selection else None

    def _update_buttons(self) -> None:
        state = "normal" if self._selected() else "disabled"
        self.btn_uninstall.configure(state=state)

    def open_preview(self) -> None:
        item = self._selected()
        if not item:
            return
        PreviewWindow(self.master, item, on_done=self.refresh)

    def open_quarantine(self) -> None:
        QuarantineWindow(self.master, on_done=self.refresh)
