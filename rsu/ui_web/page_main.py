"""主界面（NiceGUI）。"""

from __future__ import annotations

import time

from nicegui import events, run, ui

from ..models import SoftwareItem
from ..scanner import scan_installed_software
from ..util import format_bytes, format_install_date, log
from .dialog_preview import PreviewDialog
from .dialog_quarantine import QuarantineDialog
from .state import item_key, state
from .theme import inject_theme

COLUMNS = (
    ("name", "软件名称"),
    ("version", "版本"),
    ("publisher", "厂商"),
    ("size", "大小"),
    ("date", "安装日期"),
    ("location", "安装位置"),
)


@ui.page("/")
def main_page() -> None:
    inject_theme()

    # 行元素缓存：选中时只改 class，避免整表重绘导致滚动位置跳回顶部
    row_elements: dict[str, ui.element] = {}

    async def do_scan() -> None:
        if state.scanning:
            return
        state.scanning = True
        header_meta.refresh()
        rows.refresh()
        try:
            items = await run.io_bound(scan_installed_software) or []
            state.set_items(items, time.strftime("%H:%M:%S"))
            log(f"扫描完成，共 {len(items)} 个软件")
        except Exception as exc:  # noqa: BLE001
            log(f"扫描失败：{exc}")
            ui.notify(f"扫描失败：{exc}", type="negative")
        finally:
            state.scanning = False
        header_meta.refresh()
        header_row.refresh()
        rows.refresh()
        count_chip.refresh()
        footer.refresh()

    def select(item: SoftwareItem) -> None:
        key = item_key(item)
        previous = state.selected_key
        state.selected_key = None if previous == key else key

        if previous and previous in row_elements:
            row_elements[previous].classes(remove="sel")
        if state.selected_key and state.selected_key in row_elements:
            row_elements[state.selected_key].classes(add="sel")
        footer.refresh()

    def sort_by(key: str) -> None:
        state.toggle_sort(key)
        header_row.refresh()
        rows.refresh()

    def open_preview() -> None:
        item = state.selected()
        if not item:
            return

        def after_clean() -> None:
            ui.timer(0.15, do_scan, once=True)

        PreviewDialog(item, on_done=after_clean)

    def open_quarantine() -> None:
        def after_restore() -> None:
            ui.timer(0.15, do_scan, once=True)

        QuarantineDialog(on_done=after_restore)

    # ---------------------------------------------------------- 头部

    @ui.refreshable
    def header_meta() -> None:
        with ui.row().classes("items-center gap-2"):
            label = (
                f"扫描于 {state.last_scan}" if state.last_scan else "尚未扫描"
            )
            ui.label(label).classes("chip").style("height:34px;")
            btn = ui.button("刷新", icon="refresh", on_click=do_scan, color=None).props(
                "flat no-caps"
            ).classes("btn-ghost")
            if state.scanning:
                btn.classes(add="is-disabled")
            if state.scanning:
                ui.spinner("dots", size="18px", color="primary")

    # ---------------------------------------------------------- 列表

    @ui.refreshable
    def count_chip() -> None:
        ui.label(f"{len(state.filtered())} 项").classes("chip")

    @ui.refreshable
    def header_row() -> None:
        with ui.element("div").classes("shead"):
            for key, label in COLUMNS:
                classes = "sorted" if state.sort_key == key else ""
                text = label
                if state.sort_key == key:
                    text += " ↓" if state.sort_reverse else " ↑"
                def on_header_click(_e: events.GenericEventArguments,
                                    k: str = key) -> None:
                    sort_by(k)

                ui.label(text).classes(classes).on("click", on_header_click)

    @ui.refreshable
    def rows() -> None:
        row_elements.clear()
        if state.scanning and not state.items:
            with ui.column().classes("empty"):
                ui.spinner("dots", size="30px", color="primary")
                ui.label("正在扫描本机软件…").style("font-size:13px;")
            return

        data = state.filtered()
        if not data:
            with ui.column().classes("empty"):
                ui.icon("search_off")
                ui.label("没有找到匹配的软件" if state.query else "没有扫描到已安装软件")
                ui.label("试试清空搜索条件，或点击右上角「刷新」重新扫描").classes(
                    "text-faint"
                ).style("font-size:12px;")
            return

        for item in data:
            key = item_key(item)
            selected = key == state.selected_key

            def on_row_click(_e: events.GenericEventArguments,
                             current: SoftwareItem = item) -> None:
                select(current)

            with ui.element("div").classes(
                f"srow{' sel' if selected else ''}"
            ).on("click", on_row_click) as row:
                ui.label(item.display_name).classes("name")
                ui.label(item.version or "—").classes("cell mono")
                ui.label(item.publisher or "—").classes("cell")
                ui.label(
                    format_bytes(item.estimated_size_kb * 1024)
                    if item.estimated_size_kb else "—"
                ).classes("cell mono")
                ui.label(format_install_date(item.install_date) or "—").classes("cell")
                ui.label(item.install_location or "—").classes("cell")
            row_elements[key] = row

    # ---------------------------------------------------------- 底部

    @ui.refreshable
    def footer() -> None:
        selected = state.selected()
        with ui.row().classes("w-full items-center justify-between").style(
            "padding:12px 4px 0; border-top:1px solid var(--stroke);"
        ):
            with ui.row().classes("items-center gap-3"):
                if selected:
                    ui.icon("check_circle").style(
                        "font-size:18px; color:var(--accent);"
                    )
                    ui.label(f"已选择 {selected.display_name}").style(
                        "font-size:13px; font-weight:600;"
                    )
                    if selected.estimated_size_kb:
                        ui.label("·").classes("text-faint")
                        ui.label(
                            f"约 {format_bytes(selected.estimated_size_kb * 1024)}"
                        ).classes("text-muted").style("font-size:12.5px;")
                else:
                    ui.icon("info_outline").style(
                        "font-size:18px; color:var(--faint);"
                    )
                    ui.label(
                        f"共 {len(state.items)} 个软件"
                        + (f"　·　扫描于 {state.last_scan}" if state.last_scan else "")
                    ).classes("text-muted").style("font-size:13px;")

            with ui.row().classes("gap-2"):
                ui.button(
                    "隔离区 / 还原", icon="inventory_2", on_click=open_quarantine,
                    color=None,
                ).props("flat no-caps").classes("btn-ghost")
                btn = ui.button(
                    "卸载选中软件", icon="delete_sweep", on_click=open_preview,
                    color=None,
                ).props("no-caps unelevated").classes("btn-primary")
                if not selected:
                    btn.classes(add="is-disabled")

    # ---------------------------------------------------------- 布局

    with ui.element("div").classes("app-shell"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-4"):
                with ui.element("div").classes("brand-mark"):
                    ui.icon("layers")
                with ui.column().classes("gap-0"):
                    ui.label("RS-Uninstaller").style(
                        "font-size:22px; font-weight:700; letter-spacing:-.02em;"
                    )
                    ui.label("强制卸载 · 干净到不留痕迹").classes(
                        "text-muted"
                    ).style("font-size:12px;")
            header_meta()

        with ui.element("div").classes("glass w-full").style(
            "padding:9px 16px; display:flex; align-items:center; gap:12px;"
        ):
            ui.icon("search").style("font-size:20px; color:var(--faint);")
            search = ui.input(
                placeholder="搜索软件名称、厂商或安装路径…"
            ).props("borderless dense debounce=150").classes("search").style(
                "flex:1;"
            )
            search.bind_value(state, "query")
            search.on_value_change(
                lambda _e: (rows.refresh(), count_chip.refresh(), footer.refresh())
            )
            count_chip()

        with ui.element("div").classes("glass card-shell"):
            header_row()
            with ui.element("div").classes("scroll card-body"):
                rows()

        footer()

    # 键盘快捷键：F5 重新扫描
    def on_key(event: events.KeyEventArguments) -> None:
        if event.action.keydown and event.key.name == "F5":
            ui.timer(0.01, do_scan, once=True)

    ui.keyboard(on_key=on_key)
    ui.timer(0.1, do_scan, once=True)
