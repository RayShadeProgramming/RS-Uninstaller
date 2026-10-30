"""v0.2.0 视觉主题：浅色、简约。"""

from __future__ import annotations

from nicegui import ui

COLORS = {
    "accent": "#2f6bff",
    "accent2": "#6b8cff",
    "danger": "#e5484d",
    "ok": "#12a150",
}

THEME_CSS = """
<style>
:root{
  --bg:#f5f7fa; --surface:#ffffff; --surface-2:#f7f9fc;
  --stroke:#e6e9ef; --stroke-strong:#d7dce5;
  --text:#161b22; --muted:#66707d; --faint:#98a2b3;
  --accent:#2f6bff; --accent-hover:#2359e0; --accent-soft:#eef4ff;
  --danger:#e5484d; --ok:#12a150;
}
html,body{height:100%;}
body, body.body--light{
  margin:0; color:var(--text);
  background:
    radial-gradient(900px 520px at 88% -12%, rgba(47,107,255,.05), transparent 62%),
    linear-gradient(180deg,#f7f9fc 0%,#eef1f6 100%) !important;
  font-family:"Segoe UI Variable Text","Segoe UI","Microsoft YaHei UI","PingFang SC",sans-serif;
  -webkit-font-smoothing:antialiased; overflow:hidden;
}
.nicegui-content{padding:0!important; gap:0!important; height:100vh; overflow:hidden;}

/* 页面骨架：固定四行网格，避免内容把底部操作栏顶出窗口 */
.app-shell{height:100vh; width:100%; z-index:1; display:grid;
  grid-template-rows:auto auto minmax(0,1fr) auto; gap:14px;
  padding:24px 24px 16px; box-sizing:border-box;
  background:
    radial-gradient(900px 520px at 88% -12%, rgba(47,107,255,.05), transparent 62%),
    linear-gradient(180deg,#f7f9fc 0%,#eef1f6 100%);}
.app-shell > *{min-width:0;}
.card-shell{display:grid; grid-template-rows:auto minmax(0,1fr); min-height:0;
  padding:4px 4px 6px; overflow:hidden;}
.card-body{min-height:0; overflow-y:auto; padding:2px 4px 4px;}

/* 卡片 */
.glass{background:var(--surface); border:1px solid var(--stroke); border-radius:16px;
  box-shadow:0 1px 2px rgba(16,24,40,.04), 0 10px 28px rgba(16,24,40,.05);}
.glass-soft{background:var(--surface-2); border:1px solid var(--stroke); border-radius:10px;}

.text-muted{color:var(--muted)!important;}
.text-faint{color:var(--faint)!important;}
.text-ok{color:var(--ok)!important;}
.text-danger{color:var(--danger)!important;}

/* 品牌标识 */
.brand-mark{width:42px; height:42px; border-radius:12px; display:flex; align-items:center;
  justify-content:center; background:var(--accent);
  box-shadow:0 6px 16px rgba(47,107,255,.22);}
.brand-mark .q-icon{color:#fff; font-size:22px;}

/* 按钮 */
.q-btn{text-transform:none!important; font-weight:600!important; letter-spacing:.2px;
  border-radius:10px!important; box-shadow:none;}
body .q-btn.btn-primary{background:var(--accent)!important; color:#fff!important;
  box-shadow:0 1px 2px rgba(16,24,40,.08)!important;}
body .q-btn.btn-primary:hover{background:var(--accent-hover)!important;}
body .q-btn.btn-primary.disabled{background:#eef1f6!important; color:#a9b2be!important;
  box-shadow:none!important;}
body .q-btn.disabled{opacity:1!important;}
body .q-btn.is-disabled{background:#eef1f6!important; color:#a9b2be!important;
  pointer-events:none!important; box-shadow:none!important;}
body .q-btn.is-disabled .q-icon{color:#a9b2be!important;}
body .q-btn.btn-ghost.is-disabled{background:#fff!important; color:#b9c0c9!important;
  border-color:var(--stroke)!important;}
body .q-btn.btn-danger{background:var(--danger)!important; color:#fff!important;
  box-shadow:0 1px 2px rgba(16,24,40,.08)!important;}
body .q-btn.btn-danger:hover{background:#cf3b40!important;}
body .q-btn.btn-ghost{background:#fff!important; color:var(--text)!important;
  border:1px solid var(--stroke)!important;}
body .q-btn.btn-ghost .q-icon{color:var(--muted)!important;}
body .q-btn.btn-ghost:hover{background:var(--surface-2)!important;
  border-color:var(--stroke-strong)!important;}
body .q-btn.btn-quiet{background:transparent!important; color:var(--muted)!important;}
body .q-btn.btn-quiet:hover{background:var(--surface-2)!important; color:var(--text)!important;}

/* 输入框 */
.search .q-field__control{height:40px; background:transparent!important;}
.search .q-field__control:before, .search .q-field__control:after{border:none!important;}
.search .q-field__native{color:var(--text)!important; font-size:14px;}
.search .q-field__native::placeholder{color:var(--faint);}
.search .q-icon{color:var(--faint);}

/* 表头 / 行 */
.shead{display:grid;
  grid-template-columns:minmax(240px,2.6fr) 100px minmax(150px,1.3fr) 86px 104px minmax(180px,1.7fr);
  gap:14px; padding:12px 16px 9px; color:var(--faint); font-size:11px;
  letter-spacing:.12em; text-transform:uppercase; font-weight:700;
  border-bottom:1px solid var(--stroke);}
.shead > div{cursor:pointer; user-select:none; transition:color .15s ease;}
.shead > div:hover{color:var(--muted);}
.shead .sorted{color:var(--accent);}
.srow{display:grid;
  grid-template-columns:minmax(240px,2.6fr) 100px minmax(150px,1.3fr) 86px 104px minmax(180px,1.7fr);
  gap:14px; align-items:center; padding:11px 16px; border-radius:10px;
  cursor:pointer; transition:background .14s ease;}
.srow:hover{background:#f6f8fb;}
.srow.sel{background:var(--accent-soft); box-shadow:inset 0 0 0 1px #cbdcff;}
.srow .name{font-weight:600; font-size:13.5px; color:var(--text);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.srow .cell{font-size:12.5px; color:var(--muted); white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis;}
.srow .mono{font-variant-numeric:tabular-nums;}
.srow.sel .cell{color:#4a6491;}

/* 滚动区 */
.scroll{overflow-y:auto; scrollbar-width:thin;
  scrollbar-color:#d5dae2 transparent;}
.scroll::-webkit-scrollbar{width:9px;}
.scroll::-webkit-scrollbar-thumb{background:#d9dee6; border-radius:6px;
  border:2px solid transparent; background-clip:content-box;}
.scroll::-webkit-scrollbar-thumb:hover{background:#c6ccd6;}
.scroll::-webkit-scrollbar-track{background:transparent;}

/* 统计小卡 */
.chip{display:inline-flex; align-items:center; gap:6px; padding:4px 11px; border-radius:999px;
  background:var(--surface-2); border:1px solid var(--stroke);
  font-size:11.5px; color:var(--muted); white-space:nowrap;}
.chip .q-icon{font-size:14px;}

/* Quasar 覆盖 */
.q-dialog__inner > .q-card{background:#fff!important;
  border:1px solid var(--stroke); border-radius:16px!important; color:var(--text);
  box-shadow:0 24px 64px rgba(16,24,40,.18)!important;}
.q-card{background:transparent!important; box-shadow:none!important; color:var(--text);}
.q-field__label{color:var(--faint)!important;}
.q-checkbox__label, .q-toggle__label{color:var(--muted)!important; font-size:13px!important;}
.q-linear-progress{border-radius:99px!important; background:#eef1f6!important;}
.q-linear-progress__track{background:transparent!important;}
.q-item{color:var(--text)!important;}
.q-notification{background:#fff!important; color:var(--text)!important;
  border:1px solid var(--stroke); border-radius:12px!important;
  box-shadow:0 18px 44px rgba(16,24,40,.16)!important;}
.q-separator{background:var(--stroke)!important;}

/* 弹窗内条目 */
.pitem{display:grid; grid-template-columns:26px 74px minmax(160px,1fr) minmax(220px,1.7fr) 84px;
  gap:12px; align-items:center; padding:9px 12px; border-radius:10px;
  cursor:pointer; transition:background .14s ease;}
.pitem:hover{background:#f6f8fb;}
.pitem .box{width:18px; height:18px; border-radius:5px; border:1.5px solid #cfd6e0;
  background:#fff; display:flex; align-items:center; justify-content:center;
  transition:all .14s ease;}
.pitem.on .box{background:var(--accent); border-color:var(--accent);}
.pitem .box .q-icon{font-size:13px; color:#fff;}
.ptype{font-size:11px; color:var(--muted); text-align:center; padding:2px 0; border-radius:6px;
  background:var(--surface-2); border:1px solid var(--stroke);}
.pitem .plabel{font-size:13px; color:var(--text); overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap;}
.pitem .pdetail{font-size:11.5px; color:var(--faint); overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap;}
.pitem .psize{font-size:11.5px; color:var(--muted); text-align:right;
  font-variant-numeric:tabular-nums;}

/* 会话行 */
.qrow{display:grid; grid-template-columns:180px 1fr 110px; gap:14px; align-items:center;
  padding:11px 14px; border-radius:10px; cursor:pointer;}
.qrow:hover{background:#f6f8fb;}
.qrow.sel{background:var(--accent-soft); box-shadow:inset 0 0 0 1px #cbdcff;}

/* 空状态 */
.empty{display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:8px; padding:64px 0; color:var(--faint);}
.empty .q-icon{font-size:38px; opacity:.75;}
</style>
"""


def inject_theme() -> None:
    ui.add_head_html(THEME_CSS, shared=True)
    ui.dark_mode().disable()
