<template>
  <div>
    <div class="card">
      <div class="card-head"><h3 class="card-title">系统设置</h3></div>
      <div class="card-body">
        <div style="display:flex;flex-direction:column;gap:14px;max-width:520px">
          <div>
            <div class="muted" style="font-size:12px;margin-bottom:4px">服务地址</div>
            <div>http://127.0.0.1:8000</div>
          </div>
          <div>
            <div class="muted" style="font-size:12px;margin-bottom:4px">AI 模型</div>
            <div>{{ aiModel || '—' }}</div>
          </div>
          <div>
            <div class="muted" style="font-size:12px;margin-bottom:4px">数据库</div>
            <div>SQLite (data/dev.db)</div>
          </div>
          <div>
            <div class="muted" style="font-size:12px;margin-bottom:4px">采集调度</div>
            <div>APScheduler (IntervalTrigger)</div>
          </div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-head"><h3 class="card-title">平台采集状态</h3><button class="btn aux sm" @click="loadStatus">刷新</button></div>
      <table class="table">
        <thead><tr><th>平台</th><th>状态</th><th>最后采集</th><th>错误</th></tr></thead>
        <tbody>
          <tr v-for="p in platformStatus" :key="p.platform">
            <td><b>{{ platformLabel(p.platform) }}</b></td>
            <td><span class="tag" :class="statusClass(p.status)"><span class="dot" :class="statusDot(p.status)"></span>{{ statusLabel(p.status) }}</span></td>
            <td class="muted">{{ fmt(p.last_run_at) }}</td>
            <td class="muted" style="max-width:320px;overflow:hidden;text-overflow:ellipsis">{{ p.error || '—' }}</td>
          </tr>
          <tr v-if="!platformStatus.length"><td colspan="4" class="empty">暂无数据</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { getPlatformStatus, getSettings } from '../api.js'
const platformStatus = ref([])
const aiModel = ref('')
const settings = ref({})
const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }
function statusLabel(s){ return { normal:'正常', collecting:'采集中', rate_limited:'限流', blocked:'风控阻断', auth_expired:'登录失效', network_error:'网络错误', stopped:'已停止' }[s] || s }
function statusClass(s){ return { normal:'pos', collecting:'info', rate_limited:'warn', blocked:'neg', auth_expired:'warn', network_error:'neg', stopped:'aux' }[s] || 'neu' }
function statusDot(s){ return { normal:'green', collecting:'blue', rate_limited:'amber', blocked:'red', auth_expired:'amber', network_error:'red', stopped:'gray' }[s] || 'gray' }
function fmt(s){ return s ? s.replace('T',' ').slice(0,19) : '—' }
async function loadStatus(){ try { platformStatus.value = await getPlatformStatus() } catch(e) {} }
async function loadSettings(){ try { settings.value = await getSettings(); aiModel.value = settings.value.ai_model || '' } catch(e) {} }
onMounted(() => { loadStatus(); loadSettings() })
</script>
