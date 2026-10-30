"""界面状态（单窗口应用，模块级共享）。"""

from __future__ import annotations

from ..models import SoftwareItem


def item_key(item: SoftwareItem) -> str:
    return f"{item.reg_path}|{item.display_name}"


class AppState:
    def __init__(self) -> None:
        self.items: list[SoftwareItem] = []
        self.query: str = ""
        self.sort_key: str = "name"
        self.sort_reverse: bool = False
        self.selected_key: str | None = None
        self.last_scan: str = ""
        self.scanning: bool = False

    def set_items(self, items: list[SoftwareItem], scan_time: str) -> None:
        self.items = items
        self.last_scan = scan_time
        if self.selected_key and not any(item_key(i) == self.selected_key for i in items):
            self.selected_key = None

    def selected(self) -> SoftwareItem | None:
        if not self.selected_key:
            return None
        for item in self.items:
            if item_key(item) == self.selected_key:
                return item
        return None

    def filtered(self) -> list[SoftwareItem]:
        query = self.query.strip().lower()
        rows: list[SoftwareItem] = []
        for item in self.items:
            if query:
                haystack = " ".join((
                    item.display_name, item.publisher, item.version, item.install_location,
                )).lower()
                if query not in haystack:
                    continue
            rows.append(item)
        rows.sort(key=self._sort_value, reverse=self.sort_reverse)
        return rows

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

    def toggle_sort(self, key: str) -> None:
        if key == self.sort_key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = False


state = AppState()
