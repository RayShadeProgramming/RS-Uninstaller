"""清理预览对话框（NiceGUI）。"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Literal

from nicegui import events, run, ui

from ..cleaner import execute
from ..models import CleanItem, CleanPlan, CleanResult, ItemType, SoftwareItem
from ..trace import build_clean_plan
from ..util import format_bytes

QueueMessage = (
    tuple[Literal["p"], int, int]
    | tuple[Literal["done"], CleanResult]
    | tuple[Literal["error"], str]
)

TYPE_META: dict[str, tuple[str, str]] = {
    ItemType.REGISTRY: ("注册表", "key"),
    ItemType.FOLDER: ("目录", "folder"),
    ItemType.FILE: ("文件", "description"),
    ItemType.SERVICE: ("服务", "settings_suggest"),
}


class PreviewDialog:
    def __init__(self, item: SoftwareItem,
                 on_done: Callable[[], None] | None = None) -> None:
        self.item = item
        self.on_done = on_done
        self.plan: CleanPlan | None = None
        self.checked: set[int] = set()
        self.queue: queue.Queue[QueueMessage] = queue.Queue()
        self.timer: ui.timer | None = None
        self.running = False
        self.row_elements: dict[int, ui.element] = {}
        self.check_icons: dict[int, ui.icon] = {}

        self.dialog = ui.dialog().props("persistent")
        with self.dialog, ui.card().style(
            "width:1000px; max-width:94vw; max-height:90vh; display:flex;"
            " flex-direction:column; padding:0; overflow:hidden;"
        ):
            self._build_header()
            self._build_summary()
            self.list_box = ui.column().classes("w-full scroll").style(
                "flex:1; min-height:0; max-height:52vh; padding:2px 16px; gap:1px;"
            )
            self._build_options()
            self.progress_box = self._build_progress()
            self._build_footer()

        self._show_loading()
        self.dialog.open()
        ui.timer(0.05, self._load, once=True)

    # ------------------------------------------------------------ 构建

    def _build_header(self) -> None:
        with ui.row().classes("w-full items-start justify-between").style(
            "padding:22px 24px 12px;"
        ):
            with ui.column().classes("gap-1"):
                ui.label(self.item.display_name).style(
                    "font-size:20px; font-weight:700; letter-spacing:-.01em;"
                )
                meta = "　·　".join(x for x in (
                    self.item.publisher,
                    f"版本 {self.item.version}" if self.item.version else "",
                    self.item.install_location,
                ) if x)
                ui.label(meta or "—").classes("text-muted").style("font-size:12.5px")
            ui.button(icon="close", on_click=self.close, color=None).props(
                "flat round dense"
            ).classes("btn-quiet")

    def _build_summary(self) -> None:
        with ui.row().classes("w-full items-center justify-between").style(
            "padding:0 24px 10px;"
        ):
            self.summary = ui.label("正在生成清理清单…").classes("text-muted").style(
                "font-size:12.5px;"
            )
            self.badge = ui.label("").classes("chip")

    def _build_options(self) -> None:
        with ui.row().classes("w-full items-center gap-8").style(
            "padding:14px 24px 0;"
        ):
            with ui.column().classes("gap-0"):
                self.var_restore = ui.switch(
                    "清理前创建系统还原点", value=True
                ).props("dense color=primary")
                ui.label("作为默认情况下的回滚手段，推荐保留").classes(
                    "text-faint"
                ).style("font-size:11px; padding-left:2px;")
            with ui.column().classes("gap-0"):
                self.var_backup = ui.switch(
                    "保留备份到隔离区", value=False
                ).props("dense color=primary").on_value_change(
                    lambda _e: self._update_hint()
                )
                ui.label("默认永久删除；勾选后文件移入隔离区，可还原").classes(
                    "text-faint"
                ).style("font-size:11px; padding-left:2px;")

    def _update_hint(self) -> None:
        hint = getattr(self, "hint", None)
        if hint is None:
            return
        if self.var_backup.value:
            hint.set_text("将保留备份到隔离区，可随时还原")
        else:
            hint.set_text("默认永久删除，不保留备份")

    def _build_progress(self) -> ui.column:
        box = ui.column().classes("w-full").style(
            "padding:12px 24px 0; display:none;"
        )
        with box:
            self.progress_label = ui.label("准备中…").classes("text-muted").style(
                "font-size:12px;"
            )
            self.progress = ui.linear_progress(value=0).props("rounded size=8px")
        return box

    def _build_footer(self) -> None:
        with ui.row().classes("w-full items-center justify-between").style(
            "padding:16px 24px 20px; border-top:1px solid var(--stroke);"
            " margin-top:12px;"
        ):
            self.hint = ui.label("默认永久删除，不保留备份").classes(
                "text-faint"
            ).style("font-size:12px;")
            with ui.row().classes("gap-2"):
                ui.button("取消", on_click=self.close, color=None).props(
                    "flat no-caps"
                ).classes("btn-quiet")
                self.btn_start = ui.button(
                    "开始清理", icon="delete_sweep", on_click=self._confirm,
                    color=None,
                ).props("no-caps unelevated").classes("btn-primary")

    # ------------------------------------------------------------ 数据

    def _show_loading(self) -> None:
        self.list_box.clear()
        with self.list_box:
            with ui.row().classes("w-full items-center justify-center").style(
                "padding:52px 0; gap:12px;"
            ):
                ui.spinner("dots", size="26px", color="primary")
                ui.label("正在分析安装痕迹…").classes("text-muted").style(
                    "font-size:13px;"
                )

    async def _load(self) -> None:
        try:
            plan = await run.io_bound(build_clean_plan, self.item)
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"生成清理清单失败：{exc}")
            return

        if plan is None:
            self._show_error("生成清理清单失败：未返回结果")
            return

        self.plan = plan
        self.checked = set(range(len(plan.items)))
        self._render_list()
        self._update_summary()

    def _show_error(self, message: str) -> None:
        self.list_box.clear()
        with self.list_box:
            with ui.column().classes("empty"):
                ui.icon("error_outline")
                ui.label(message)

    def _render_list(self) -> None:
        self.list_box.clear()
        self.row_elements.clear()
        self.check_icons.clear()
        if not self.plan or not self.plan.items:
            with self.list_box:
                with ui.column().classes("empty"):
                    ui.icon("search_off")
                    ui.label("没有找到可清理的内容")
                    ui.label("可能该软件已被移除，或痕迹位于受保护位置").classes(
                        "text-faint"
                    ).style("font-size:12px;")
            return

        with self.list_box:
            for index, clean_item in enumerate(self.plan.items):
                self._render_row(index, clean_item)

    def _render_row(self, index: int, clean_item: CleanItem) -> None:
        on = index in self.checked
        label, _icon = TYPE_META.get(clean_item.kind, ("其他", "help_outline"))
        def on_item_click(_e: events.GenericEventArguments,
                          i: int = index) -> None:
            self._toggle(i)

        with ui.element("div").classes(
            f"pitem{' on' if on else ''}"
        ).on("click", on_item_click) as row:
            with ui.element("div").classes("box"):
                check = ui.icon("check")
                check.set_visibility(on)
            ui.label(label).classes("ptype")
            ui.label(clean_item.label).classes("plabel")
            ui.label(clean_item.detail).classes("pdetail")
            ui.label(
                format_bytes(clean_item.size) if clean_item.size else "—"
            ).classes("psize")
        self.row_elements[index] = row
        self.check_icons[index] = check

    def _toggle(self, index: int) -> None:
        if self.running:
            return

        if index in self.checked:
            self.checked.discard(index)
            on = False
        else:
            self.checked.add(index)
            on = True

        row = self.row_elements.get(index)
        if row is not None:
            if on:
                row.classes(add="on")
            else:
                row.classes(remove="on")

        check = self.check_icons.get(index)
        if check is not None:
            check.set_visibility(on)

        self._update_summary()

    def _update_summary(self) -> None:
        if not self.plan:
            return
        chosen = len(self.checked)
        total_size = sum(self.plan.items[i].size for i in self.checked)
        self.summary.set_text(
            f"共 {len(self.plan.items)} 项，已勾选 {chosen} 项"
        )
        self.badge.set_text(f"约 {format_bytes(total_size)}")
        if chosen > 0 and not self.running:
            self.btn_start.classes(remove="is-disabled")
        else:
            self.btn_start.classes(add="is-disabled")

    # ------------------------------------------------------------ 执行

    def _confirm(self) -> None:
        if not self.plan or not self.plan.items:
            ui.notify("清理清单还没准备好", type="warning")
            return

        selected = sorted(self.checked)
        if not selected:
            ui.notify("没有勾选任何内容", type="warning")
            return

        keep_backup = bool(self.var_backup.value)
        total_size = sum(self.plan.items[i].size for i in selected)

        if keep_backup:
            bullets = [
                ("inventory_2", "文件与目录会移动到隔离区，可随时还原"),
                ("history", "注册表项会先导出备份，再删除"),
            ]
        else:
            bullets = [
                ("delete_forever", "文件与目录将被永久删除，无法从隔离区恢复"),
                ("history_toggle_off", "注册表项将直接删除，不保留备份"),
            ]

        with ui.dialog() as confirm, ui.card().style("width:480px; padding:24px;"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning_amber").style(
                    "font-size:26px; color:#ffb020;"
                )
                ui.label("确认清理").style("font-size:17px; font-weight:700;")
            ui.label(
                f"即将清理 {len(selected)} 项内容，约 {format_bytes(total_size)}。"
            ).style("font-size:13px; margin-top:10px;")
            with ui.column().classes("gap-2").style("margin-top:10px;"):
                for icon_name, text in bullets:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon(icon_name).style(
                            "font-size:16px; color:var(--muted);"
                        )
                        ui.label(text).classes("text-muted").style("font-size:12.5px;")
            ui.label("此操作不可撤销，请确认清单无误。").classes("text-faint").style(
                "font-size:11.5px; margin-top:12px;"
            )
            with ui.row().classes("w-full justify-end gap-2").style("margin-top:16px;"):
                ui.button("取消", on_click=confirm.close, color=None).props(
                    "flat no-caps"
                ).classes("btn-quiet")
                ui.button(
                    "确认清理",
                    on_click=lambda: (confirm.close(), self._start(selected, keep_backup)),
                    color=None,
                ).props("no-caps unelevated").classes("btn-danger")
        confirm.open()

    def _start(self, selected: list[int], keep_backup: bool) -> None:
        if self.running:
            return
        self.running = True
        self.btn_start.classes(add="is-disabled")
        self.progress_box.style("display:block")
        self.progress.value = 0
        self.progress_label.set_text("正在清理…")
        self.hint.set_text(
            "正在移动到隔离区…" if keep_backup else "正在永久删除…"
        )
        self.queue = queue.Queue()

        make_restore_point = bool(self.var_restore.value)
        thread = threading.Thread(
            target=self._worker,
            args=(selected, make_restore_point, keep_backup),
            daemon=True,
        )
        thread.start()
        self.timer = ui.timer(0.12, self._poll)

    def _worker(self, selected: list[int], make_restore_point: bool,
                keep_backup: bool) -> None:
        plan = self.plan
        if plan is None:
            self.queue.put(("error", "清理清单尚未就绪"))
            return
        try:
            result = execute(
                plan, selected, make_restore_point, keep_backup,
                progress=lambda done, total, _label: self.queue.put(("p", done, total)),
            )
            self.queue.put(("done", result))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", str(exc)))

    def _poll(self) -> None:
        try:
            while True:
                message = self.queue.get_nowait()
                if message[0] == "p":
                    _, done, total = message
                    self.progress.value = done / max(total, 1)
                    self.progress_label.set_text(f"正在清理… {done} / {total}")
                elif message[0] == "done":
                    self._stop_timer()
                    self._finish(message[1])
                    return
                else:
                    self._stop_timer()
                    self._fail(message[1])
                    return
        except queue.Empty:
            pass

    def _stop_timer(self) -> None:
        if self.timer:
            self.timer.active = False
            self.timer = None
        self.running = False

    def _finish(self, result: CleanResult) -> None:
        self.dialog.close()
        if self.on_done:
            try:
                self.on_done()
            except Exception:  # noqa: BLE001
                pass
        self._show_result(result)

    def _fail(self, error: str) -> None:
        self.dialog.close()
        ui.notify(f"清理过程中出现异常：{error}", type="negative", timeout=6000)

    def _show_result(self, result: CleanResult) -> None:
        ok = result.failed == 0
        with ui.dialog() as dialog, ui.card().style("width:560px; padding:26px;"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("check_circle" if ok else "error").style(
                    f"font-size:30px; color:{'var(--ok)' if ok else 'var(--danger)'};"
                )
                with ui.column().classes("gap-0"):
                    ui.label("清理完成").style("font-size:18px; font-weight:700;")
                    ui.label(
                        f"成功 {result.ok} 项" + (f" · 失败 {result.failed} 项" if result.failed else "")
                    ).classes("text-muted").style("font-size:12.5px;")

            with ui.row().classes("w-full gap-3").style("margin-top:16px;"):
                self._stat("成功", str(result.ok), "var(--ok)")
                self._stat(
                    "失败", str(result.failed),
                    "var(--danger)" if result.failed else "var(--muted)",
                )
                self._stat(
                    "还原点", "已创建" if result.restore_point_created else "未创建",
                    "var(--muted)",
                )

            if result.errors:
                ui.label("失败详情").classes("text-faint").style(
                    "font-size:11px; margin-top:14px; letter-spacing:.08em;"
                )
                with ui.column().classes("gap-1").style("margin-top:6px;"):
                    for error in result.errors[:5]:
                        ui.label(f"· {error}").classes("text-muted").style(
                            "font-size:12px;"
                        )
                    if len(result.errors) > 5:
                        ui.label(f"… 其余 {len(result.errors) - 5} 项见日志").classes(
                            "text-faint"
                        ).style("font-size:11.5px;")

            if result.kept_backup and result.session_dir:
                ui.label("备份位置").classes("text-faint").style(
                    "font-size:11px; margin-top:14px; letter-spacing:.08em;"
                )
                ui.label(result.session_dir).classes("text-muted").style(
                    "font-size:11.5px; word-break:break-all;"
                )
            elif not result.kept_backup:
                ui.label("未保留备份，文件已永久删除").classes("text-faint").style(
                    "font-size:11.5px; margin-top:12px;"
                )

            with ui.row().classes("w-full justify-end").style("margin-top:20px;"):
                ui.button("完成", on_click=dialog.close, color=None).props(
                    "no-caps unelevated"
                ).classes("btn-primary")
        dialog.open()

    @staticmethod
    def _stat(label: str, value: str, color: str) -> None:
        with ui.column().classes("glass-soft items-center").style(
            "padding:10px 14px; min-width:96px; gap:2px;"
        ):
            ui.label(value).style(f"font-size:16px; font-weight:700; color:{color};")
            ui.label(label).classes("text-faint").style("font-size:11px;")

    def close(self) -> None:
        if self.running:
            ui.notify("清理进行中，请稍候", type="warning")
            return
        self.dialog.close()
