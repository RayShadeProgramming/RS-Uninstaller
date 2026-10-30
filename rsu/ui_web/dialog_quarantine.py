"""隔离区对话框（NiceGUI）。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from nicegui import events, run, ui

from ..backup import (
    clear_quarantine,
    list_sessions,
    quarantine_root,
    restore_session,
)
from ..util import dir_size, format_bytes


def _pretty_session(name: str) -> str:
    try:
        stamp = time.strptime(name.split("-")[0], "%Y%m%d")
        base = time.strftime("%Y-%m-%d", stamp)
        if "-" in name:
            tail = name.split("-", 1)[1]
            if len(tail) == 6 and tail.isdigit():
                base += f" {tail[:2]}:{tail[2:4]}"
        return base
    except (ValueError, IndexError):
        return name


class QuarantineDialog:
    def __init__(self, on_done: Callable[[], None] | None = None) -> None:
        self.on_done = on_done
        self.sessions: list[str] = []
        self.sizes: dict[str, int] = {}
        self.selected: str | None = None
        self.busy = False

        self.dialog = ui.dialog()
        with self.dialog, ui.card().style(
            "width:820px; max-width:94vw; max-height:86vh; display:flex;"
            " flex-direction:column; padding:0; overflow:hidden;"
        ):
            with ui.row().classes("w-full items-start justify-between").style(
                "padding:22px 24px 8px;"
            ):
                with ui.column().classes("gap-1"):
                    ui.label("隔离区").style(
                        "font-size:20px; font-weight:700; letter-spacing:-.01em;"
                    )
                    ui.label("只有勾选「保留备份到隔离区」的清理才会出现在这里").classes(
                        "text-muted"
                    ).style("font-size:12.5px;")
                ui.button(icon="close", on_click=self.close, color=None).props(
                    "flat round dense"
                ).classes("btn-quiet")

            self.list_box = ui.column().classes("w-full scroll").style(
                "flex:1; min-height:0; max-height:46vh; padding:6px 16px; gap:2px;"
            )

            with ui.row().classes("w-full items-center justify-between").style(
                "padding:14px 24px 18px; border-top:1px solid var(--stroke);"
                " margin-top:12px;"
            ):
                self.status = ui.label("").classes("text-faint").style("font-size:12px;")
                with ui.row().classes("gap-2"):
                    ui.button(
                        "打开目录", icon="folder_open", on_click=self.open_folder,
                        color=None,
                    ).props("flat no-caps").classes("btn-ghost")
                    self.btn_clear = ui.button(
                        "清空隔离区", icon="delete_sweep",
                        on_click=self._confirm_clear, color=None,
                    ).props("flat no-caps").classes("btn-ghost")
                    self.btn_restore = ui.button(
                        "还原此会话", icon="restore",
                        on_click=self._confirm_restore, color=None,
                    ).props("no-caps unelevated").classes("btn-primary")

        self.dialog.open()
        ui.timer(0.05, self.reload, once=True)

    # ------------------------------------------------------------ 数据

    async def reload(self) -> None:
        self.list_box.clear()
        with self.list_box:
            with ui.row().classes("w-full items-center justify-center").style(
                "padding:44px 0; gap:12px;"
            ):
                ui.spinner("dots", size="24px", color="primary")
                ui.label("正在读取隔离区…").classes("text-muted").style("font-size:13px;")

        sessions = await run.io_bound(list_sessions)
        self.sessions = sessions or []
        sizes = await run.io_bound(self._compute_sizes, self.sessions)
        self.sizes = sizes or {}
        self.selected = None
        self._render()
        self._update_buttons()

    @staticmethod
    def _compute_sizes(sessions: list[str]) -> dict[str, int]:
        root = quarantine_root()
        return {name: dir_size(os.path.join(root, name)) for name in sessions}

    def _render(self) -> None:
        self.list_box.clear()
        if not self.sessions:
            with self.list_box:
                with ui.column().classes("empty"):
                    ui.icon("inventory_2")
                    ui.label("隔离区是空的")
                    ui.label("默认清理不保留备份，文件会被永久删除").classes(
                        "text-faint"
                    ).style("font-size:12px;")
            self.status.set_text("共 0 个会话")
            return

        with self.list_box:
            for name in self.sessions:
                selected = name == self.selected
                def on_session_click(_e: events.GenericEventArguments,
                                     n: str = name) -> None:
                    self._select(n)

                with ui.element("div").classes(
                    f"qrow{' sel' if selected else ''}"
                ).on("click", on_session_click):
                    ui.label(_pretty_session(name)).style(
                        "font-size:12.5px; font-weight:600;"
                    )
                    ui.label(name).classes("text-muted").style(
                        "font-size:12px; overflow:hidden; text-overflow:ellipsis;"
                        " white-space:nowrap;"
                    )
                    ui.label(format_bytes(self.sizes.get(name, 0))).classes(
                        "text-muted"
                    ).style("font-size:12px; text-align:right; font-variant-numeric:tabular-nums;")

        total = sum(self.sizes.values())
        self.status.set_text(
            f"共 {len(self.sessions)} 个会话 · 约 {format_bytes(total)}"
        )

    def _select(self, name: str) -> None:
        self.selected = name
        self._render()
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = bool(self.selected) and not self.busy
        if has_selection:
            self.btn_restore.classes(remove="is-disabled")
        else:
            self.btn_restore.classes(add="is-disabled")

        if self.sessions and not self.busy:
            self.btn_clear.classes(remove="is-disabled")
        else:
            self.btn_clear.classes(add="is-disabled")

    # ------------------------------------------------------------ 操作

    def open_folder(self) -> None:
        try:
            folder = quarantine_root()
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)  # noqa: S606
        except OSError as exc:
            ui.notify(f"打开目录失败：{exc}", type="negative")

    def _confirm_restore(self) -> None:
        if not self.selected:
            ui.notify("请先选择一个清理会话", type="warning")
            return

        with ui.dialog() as confirm, ui.card().style("width:460px; padding:24px;"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("restore").style("font-size:24px; color:var(--accent);")
                ui.label("确认还原").style("font-size:17px; font-weight:700;")
            ui.label(
                "将把该会话中备份的文件还原到原位置，并重新导入注册表备份。"
                "若目标位置已存在同名文件，将跳过。"
            ).classes("text-muted").style("font-size:12.5px; margin-top:10px;")
            with ui.row().classes("w-full justify-end gap-2").style("margin-top:18px;"):
                ui.button("取消", on_click=confirm.close, color=None).props(
                    "flat no-caps"
                ).classes("btn-quiet")
                ui.button(
                    "确认还原",
                    on_click=lambda: (confirm.close(), self._do_restore()),
                    color=None,
                ).props("no-caps unelevated").classes("btn-primary")
        confirm.open()

    async def _do_restore(self) -> None:
        if not self.selected:
            return
        name = self.selected
        path = os.path.join(quarantine_root(), name)
        self.busy = True
        self._update_buttons()
        ui.notify("正在还原…", type="ongoing", timeout=1500)
        try:
            result = await run.io_bound(restore_session, path)
        except Exception as exc:  # noqa: BLE001
            self.busy = False
            self._update_buttons()
            ui.notify(f"还原失败：{exc}", type="negative", timeout=6000)
            return
        self.busy = False

        if result is None:
            self._update_buttons()
            ui.notify("还原失败：未返回结果", type="negative", timeout=6000)
            return

        summary = (
            f"文件 {result.files} 项 · 注册表 {result.regs} 项"
            + (f" · 失败 {result.failed} 项" if result.failed else "")
        )
        ui.notify(f"还原完成：{summary}", type="positive" if not result.failed else "warning")
        if self.on_done:
            try:
                self.on_done()
            except Exception:  # noqa: BLE001
                pass
        await self.reload()

    def _confirm_clear(self) -> None:
        if not self.sessions:
            ui.notify("隔离区已经是空的", type="info")
            return

        total = sum(self.sizes.values())
        with ui.dialog() as confirm, ui.card().style("width:460px; padding:24px;"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning_amber").style("font-size:24px; color:#ffb020;")
                ui.label("清空隔离区").style("font-size:17px; font-weight:700;")
            ui.label(
                f"将永久删除 {len(self.sessions)} 个会话（约 {format_bytes(total)}），"
                "删除后这些备份无法再还原。"
            ).classes("text-muted").style("font-size:12.5px; margin-top:10px;")
            with ui.row().classes("w-full justify-end gap-2").style("margin-top:18px;"):
                ui.button("取消", on_click=confirm.close, color=None).props(
                    "flat no-caps"
                ).classes("btn-quiet")
                ui.button(
                    "确认清空",
                    on_click=lambda: (confirm.close(), self._do_clear()),
                    color=None,
                ).props("no-caps unelevated").classes("btn-danger")
        confirm.open()

    async def _do_clear(self) -> None:
        self.busy = True
        self._update_buttons()
        try:
            outcome = await run.io_bound(clear_quarantine)
        except Exception as exc:  # noqa: BLE001
            self.busy = False
            self._update_buttons()
            ui.notify(f"清空失败：{exc}", type="negative", timeout=6000)
            return
        self.busy = False

        if outcome is None:
            self._update_buttons()
            ui.notify("清空失败：未返回结果", type="negative", timeout=6000)
            return
        deleted, failed, errors = outcome

        if failed:
            detail = errors[0] if errors else "部分文件被占用"
            ui.notify(f"已删除 {deleted} 个，失败 {failed} 个（{detail}）", type="warning")
        else:
            ui.notify(f"已清空 {deleted} 个会话", type="positive")
        await self.reload()

    def close(self) -> None:
        if self.busy:
            ui.notify("操作进行中，请稍候", type="warning")
            return
        self.dialog.close()
