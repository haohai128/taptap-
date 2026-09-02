<template>
  <div id="app">
    <aside class="sidebar">
      <div class="logo">
        <span class="logo-mark"></span>
        <span class="logo-text">舆情监测</span>
      </div>
      <nav class="nav">
        <router-link to="/" class="nav-item" exact><span class="nav-ico">▦</span>看板</router-link>
        <router-link to="/communities" class="nav-item"><span class="nav-ico">◫</span>社区管理</router-link>
        <router-link to="/content-library" class="nav-item"><span class="nav-ico">≣</span>内容库</router-link>
        <router-link to="/negative-library" class="nav-item"><span class="nav-ico">⚠</span>负面库</router-link>
        <router-link to="/collector-records" class="nav-item"><span class="nav-ico">↻</span>采集记录</router-link>
        <router-link to="/settings" class="nav-item"><span class="nav-ico">⚙</span>系统设置</router-link>
      </nav>
    </aside>
    <div class="wrapper">
      <header class="topbar">
        <div class="topbar-title">{{ $route.meta.title || '看板' }}</div>
        <div class="topbar-right">
          <span class="topbar-time">{{ now }}</span>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
const now = ref('')
let timer = null
function tick() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  now.value = `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
onMounted(() => { tick(); timer = setInterval(tick, 1000) })
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style>
:root {
  --primary: #0F766E;
  --primary-light: #F0FDFA;
  --primary-dark: #0B5A53;
  --aux: #64748B;
  --bg: #F5F7FA;
  --card-bg: #FFFFFF;
  --border: #E5E7EB;
  --border-light: #F1F5F9;
  --text: #1E293B;
  --text-muted: #64748B;
  --text-light: #94A3B8;
  --radius: 8px;
  --shadow: 0 1px 2px rgba(15,23,42,.04);
  --shadow-hover: 0 2px 8px rgba(15,23,42,.06);
  --danger: #DC2626;
  --warn: #D97706;
  --success: #16A34A;
  --info: #2563EB;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--text); font-size: 13px;
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale;
}
#app { display: flex; min-height: 100vh; }

/* ===== Sidebar ===== */
.sidebar {
  width: 208px; flex-shrink: 0; background: #fff; border-right: 1px solid var(--border);
  position: sticky; top: 0; height: 100vh; overflow-y: auto; z-index: 10;
}
.logo { display: flex; align-items: center; gap: 9px; padding: 16px 18px; border-bottom: 1px solid var(--border-light); }
.logo-mark { width: 18px; height: 18px; background: var(--primary); border-radius: 4px; }
.logo-text { font-size: 15px; font-weight: 600; color: var(--text); letter-spacing: 0.3px; }
.nav { display: flex; flex-direction: column; padding: 8px 8px; }
.nav-item { display: flex; align-items: center; gap: 9px; color: var(--text-muted); text-decoration: none; padding: 9px 12px; border-radius: 6px; font-size: 13px; margin: 1px 0; transition: all .12s; }
.nav-ico { width: 16px; text-align: center; font-size: 13px; opacity: .7; }
.nav-item:hover { background: var(--border-light); color: var(--text); }
.nav-item.router-link-active { background: var(--primary-light); color: var(--primary); font-weight: 500; }
.nav-item.router-link-active .nav-ico { opacity: 1; }

/* ===== Wrapper / Topbar ===== */
.wrapper { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.topbar {
  height: 48px; background: #fff; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; position: sticky; top: 0; z-index: 9;
}
.topbar-title { font-size: 15px; font-weight: 600; color: var(--text); }
.topbar-right { display: flex; align-items: center; gap: 12px; }
.topbar-time { font-size: 12px; color: var(--text-light); font-variant-numeric: tabular-nums; }
.content { flex: 1; padding: 16px 24px; overflow: auto; width: 100%; max-width: 1400px; margin: 0 auto; }

/* ===== Generic components ===== */
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow); margin-bottom: 14px; }
.card-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-light); }
.card-title { font-size: 14px; font-weight: 600; color: var(--text); margin: 0; }
.card-body { padding: 14px 16px; }

.grid { display: grid; gap: 14px; }
.grid-2 { grid-template-columns: 1fr 1fr; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }
.grid-6 { grid-template-columns: repeat(6, 1fr); }
@media (max-width: 1280px) { .grid-6 { grid-template-columns: repeat(3, 1fr); } .grid-4 { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 900px) { .grid-2, .grid-3, .grid-4, .grid-6 { grid-template-columns: 1fr; } }

/* KPI card */
.kpi { background: #fff; border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 16px; box-shadow: var(--shadow); }
.kpi-label { font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
.kpi-value { font-size: 26px; font-weight: 700; color: var(--text); font-variant-numeric: tabular-nums; line-height: 1.1; }
.kpi-value.primary { color: var(--primary); }
.kpi-value.danger { color: var(--danger); }
.kpi-value.warn { color: var(--warn); }
.kpi-foot { margin-top: 6px; font-size: 11px; color: var(--text-light); }

/* Buttons */
.btn { background: var(--primary); color: #fff; border: 1px solid var(--primary); padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; line-height: 1.4; transition: all .12s; white-space: nowrap; }
.btn:hover { background: var(--primary-dark); border-color: var(--primary-dark); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn.ghost { background: #fff; color: var(--primary); }
.btn.ghost:hover { background: var(--primary-light); }
.btn.aux { background: #fff; color: var(--text-muted); border-color: var(--border); }
.btn.aux:hover { background: var(--border-light); color: var(--text); }
.btn.danger { background: #fff; color: var(--danger); border-color: #FCA5A5; }
.btn.danger:hover { background: #FEF2F2; }
.btn.sm { padding: 4px 10px; font-size: 11px; }
.btn.lg { padding: 8px 18px; font-size: 13px; }

/* Inputs */
.input, .select, .textarea { padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 12px; outline: none; background: #fff; color: var(--text); transition: border-color .12s, box-shadow .12s; }
.input:focus, .select:focus, .textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(15,118,110,.1); }
.input::placeholder { color: var(--text-light); }

/* Table */
.table { width: 100%; border-collapse: collapse; font-size: 12px; }
.table th { text-align: left; padding: 9px 12px; color: var(--text-muted); font-weight: 600; background: #FAFBFC; border-bottom: 1px solid var(--border); font-size: 11px; letter-spacing: .2px; }
.table td { padding: 9px 12px; border-bottom: 1px solid var(--border-light); color: var(--text); vertical-align: middle; }
.table tbody tr:hover { background: #FAFBFC; }
.table .num { font-variant-numeric: tabular-nums; text-align: right; }
.table .muted { color: var(--text-muted); }

/* Tags / badges */
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; line-height: 1.5; }
.tag.pos { background: #F0FDF4; color: #15803D; border: 1px solid #BBF7D0; }
.tag.neg { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
.tag.neu { background: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; }
.tag.warn { background: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
.tag.info { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
.tag.primary { background: var(--primary-light); color: var(--primary); border: 1px solid #99F6E4; }
.tag.aux { background: #F1F5F9; color: var(--aux); border: 1px solid var(--border); }
.tag.danger { background: #FEF2F2; color: var(--danger); border: 1px solid #FECACA; }

/* Status dot */
.dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
.dot.green { background: var(--success); }
.dot.red { background: var(--danger); }
.dot.amber { background: var(--warn); }
.dot.gray { background: #94A3B8; }
.dot.blue { background: var(--info); }

/* Muted text */
.muted { color: var(--text-muted); }
.light { color: var(--text-light); }

/* Link */
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Empty state */
.empty { padding: 40px 20px; text-align: center; color: var(--text-light); font-size: 13px; }
.empty-icon { font-size: 32px; opacity: .4; margin-bottom: 8px; display: block; }

/* Filter bar */
.filter-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.filter-bar .input, .filter-bar .select { min-width: 120px; }

/* Pagination */
.pagination { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border-top: 1px solid var(--border-light); font-size: 12px; color: var(--text-muted); }
.pagination-actions { display: flex; gap: 6px; }

/* Drawer */
.drawer-mask { position: fixed; inset: 0; background: rgba(15,23,42,.32); z-index: 100; }
.drawer { position: fixed; right: 0; top: 0; bottom: 0; width: 480px; max-width: 92vw; background: #fff; box-shadow: -4px 0 16px rgba(0,0,0,.08); z-index: 101; display: flex; flex-direction: column; }
.drawer-head { padding: 14px 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
.drawer-title { font-size: 14px; font-weight: 600; }
.drawer-body { flex: 1; overflow-y: auto; padding: 16px 18px; }
.drawer-foot { padding: 12px 18px; border-top: 1px solid var(--border); display: flex; gap: 8px; justify-content: flex-end; }

/* Tabs */
.tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border); margin-bottom: 14px; }
.tab { padding: 8px 16px; cursor: pointer; font-size: 13px; color: var(--text-muted); border-bottom: 2px solid transparent; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 500; }

/* Page title (when needed inside content) */
.page-title { font-size: 16px; font-weight: 600; margin: 0 0 14px; color: var(--text); }

/* Scrollbar (subtle) */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
::-webkit-scrollbar-track { background: transparent; }
</style>
