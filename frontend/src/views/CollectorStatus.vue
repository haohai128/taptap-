<template>
  <div>
    <h2 class="page-title">平台采集状态</h2>
    <div class="card">
      <h3>各平台当前状态</h3>
      <p class="muted" style="font-size:12px;margin-bottom:12px">
        合规声明：本系统不绕过验证码、不破解风控、不伪造身份。平台明确拒绝请求时停止该平台采集，不影响其他平台运行。
      </p>
      <table v-if="platforms.length">
        <thead>
          <tr><th>平台</th><th>当前状态</th><th>最后采集时间</th><th>错误原因</th><th>最近一次采集记录</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in platforms" :key="p.platform">
            <td><b>{{ platformLabel(p.platform) }}</b></td>
            <td><span class="status-tag" :class="statusClass(p.status)">{{ statusLabel(p.status) }}</span></td>
            <td class="muted">{{ fmt(p.last_run_at) }}</td>
            <td class="muted" style="max-width:300px;overflow:hidden;text-overflow:ellipsis">{{ p.error || '—' }}</td>
            <td>
              <span v-if="p.last_run" class="muted">
                {{ p.last_run.status }} · 抓取 {{ p.last_run.fetched_count }} · 新增 {{ p.last_run.new_count }} · 失败 {{ p.last_run.failed_count }}
                <span v-if="p.last_run.error_type" style="color:#dc2626"> · {{ p.last_run.error_type }}</span>
              </span>
              <span v-else class="muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">加载中...</p>
    </div>

    <div class="card" v-if="communities.length">
      <h3>社区采集启停控制</h3>
      <table>
        <thead>
          <tr><th>社区</th><th>平台</th><th>采集状态</th><th>最近采集</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in communities" :key="c.id">
            <td><b>{{ c.name || c.taptap_id }}</b></td>
            <td>{{ platformLabel(c.platform) }}</td>
            <td><span class="tag" :class="collectStatusClass(c.collect_status)">{{ collectStatusLabel(c.collect_status) }}</span></td>
            <td class="muted">{{ c.last_run ? fmt(c.last_run.ended_at) : '尚未采集' }}</td>
            <td>
              <button v-if="c.collect_status!=='stopped'" class="danger" @click="stop(c.id)" :disabled="stopping[c.id]">
                {{ stopping[c.id] ? '停止中...' : '停止采集' }}
              </button>
              <button v-else @click="start(c.id)">重新启用</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card" v-if="hasBlocked">
      <h3>风控阻断提示</h3>
      <div v-for="p in blockedPlatforms" :key="p.platform" class="blocked-tip">
        <b>{{ platformLabel(p.platform) }}</b> 当前处于「{{ statusLabel(p.status) }}」状态。
        <span v-if="p.error">原因：{{ p.error }}</span>
        建议检查：平台授权是否有效、是否需要使用官方 API、登录状态是否过期、或采用其他合规的数据获取方式。
      </div>
    </div>

    <div style="margin-top:12px">
      <button class="ghost" @click="load">刷新</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount } from 'vue'
import { getPlatformStatus, listCommunities, stopCollection, startCollection } from '../api.js'

const platforms = ref([])
const communities = ref([])
const stopping = reactive({})
let pollTimer = null

const platformLabel = (pf) => ({ taptap:'TapTap' }[pf] || pf)
const statusLabel = (s) => ({
  normal: '正常', collecting: '采集中', rate_limited: '限流',
  blocked: '风控阻断', auth_expired: '登录失效', network_error: '网络错误',
  stopped: '已停止',
}[s] || s)
const statusClass = (s) => ({
  normal: 'st-normal', collecting: 'st-collecting', rate_limited: 'st-rate',
  blocked: 'st-blocked', auth_expired: 'st-auth', network_error: 'st-net',
  stopped: 'st-stopped',
}[s] || 'st-normal')
function collectStatusLabel(s){return { enabled:'采集中', stopped:'已停止' }[s]||s}
function collectStatusClass(s){return { enabled:'pos', stopped:'neg' }[s]||'neu'}

const hasBlocked = computed(() => platforms.value.some(p => ['blocked','rate_limited','auth_expired','network_error'].includes(p.status)))
const blockedPlatforms = computed(() => platforms.value.filter(p => ['blocked','rate_limited','auth_expired','network_error'].includes(p.status)))

function fmt(s) { return s ? s.replace('T',' ').slice(0,19) : '—' }

async function load() {
  try { platforms.value = await getPlatformStatus() } catch (e) { console.error(e) }
  try { communities.value = await listCommunities() } catch (e) { console.error(e) }
}

async function stop(id) {
  stopping[id] = true
  try {
    await stopCollection(id)
    await load()
    // 轮询直到 collect_status 变为 stopped（正在执行的任务收尾）
    const poll = async () => {
      await load()
      const c = communities.value.find(x => x.id === id)
      if (c && c.collect_status === 'stopped') {
        stopping[id] = false
        return
      }
      pollTimer = setTimeout(poll, 2000)
    }
    setTimeout(poll, 2000)
  } catch (e) {
    stopping[id] = false
    alert(e.response?.data?.detail || e.message)
  }
}

async function start(id) {
  try { await startCollection(id); await load() }
  catch (e) { alert(e.response?.data?.detail || e.message) }
}

onMounted(load)
onBeforeUnmount(() => { if (pollTimer) clearTimeout(pollTimer) })
</script>

<style scoped>
.page-title { margin-top: 0; }
.status-tag { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 600; }
.st-normal { background: #dcfce7; color: #166534; }
.st-collecting { background: #dbeafe; color: #1d4ed8; }
.st-rate { background: #fef3c7; color: #b45309; }
.st-blocked { background: #fee2e2; color: #b91c1c; }
.st-auth { background: #f3e8ff; color: #7e22ce; }
.st-net { background: #fee2e2; color: #b91c1c; }
.st-stopped { background: #f3f4f6; color: #4b5563; }
.blocked-tip { padding: 8px 12px; background: #fef2f2; border-left: 3px solid #dc2626; margin-bottom: 8px; font-size: 13px; color: #7f1d1d; }
</style>
