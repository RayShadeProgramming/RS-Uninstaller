"""自定义控件：带勾选列的可多选列表。"""

from __future__ import annotations

from tkinter import ttk

CHECKED = "☑"
UNCHECKED = "☐"


class CheckTreeview(ttk.Treeview):
    """用树形列模拟复选框，点击首列即可切换勾选状态。"""

    def __init__(self, master, columns, **kwargs):
        kwargs.setdefault("show", "tree headings")
        kwargs.setdefault("selectmode", "none")
        super().__init__(master, columns=columns, **kwargs)
        self._checked: set[str] = set()
        self.column("#0", width=48, minwidth=48, stretch=False, anchor="center")
        self.heading("#0", text="选择")
        self.bind("<Button-1>", self._on_click, add="+")

    def _on_click(self, event):
        if self.identify_column(event.x) != "#0":
            return
        iid = self.identify_row(event.y)
        if iid:
            self.toggle(iid)
            return "break"

    def toggle(self, iid: str) -> None:
        self.set_checked(iid, iid not in self._checked)

    def set_checked(self, iid: str, checked: bool) -> None:
        if checked:
            self._checked.add(iid)
        else:
            self._checked.discard(iid)
        self.item(iid, text=CHECKED if checked else UNCHECKED)

    def is_checked(self, iid: str) -> bool:
        return iid in self._checked

    def checked_items(self) -> list[str]:
        return [iid for iid in self.get_children("") if iid in self._checked]

    def clear_checks(self) -> None:
        self._checked.clear()
