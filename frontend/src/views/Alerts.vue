<template>
  <div>
    <div class="card">
      <div class="card-body">
        <div class="filter-bar">
          <input class="input" v-model="search" placeholder="搜索告警内容" style="flex:1;min-width:240px" />
          <select class="select" v-model="levelFilter">
            <option value="">全部等级</option>
            <option value="critical">严重</option>
            <option value="warn">警告</option>
            <option value="info">提示</option>
          </select>
          <select class="select" v-model="statusFilter">
            <option value="">全部状态</option>
            <option value="open">未处理</option>
            <option value="resolved">已处理</option>
            <option value="ignored">已忽略</option>
          </select>
          <button class="btn sm" @click="scan">扫描负面预警</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3 class="card-title">告警列表 ({{ filtered.length }})</h3></div>
      <table class="table">
        <thead>
          <tr>
            <th style="width:30%">告警内容</th>
            <th>命中关键词</th>
            <th>平台</th>
            <th>风险等级</th>
            <th>时间</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in filtered" :key="a.id">
            <td>{{ a.title }}</td>
            <td><span class="tag aux">{{ a.keyword || '—' }}</span></td>
            <td>{{ alertPlatform(a) }}</td>
            <td><span class="tag" :class="levelClass(a.level)"><span class="dot" :class="levelDot(a.level)"></span>{{ levelLabel(a.level) }}</span></td>
            <td class="muted">{{ fmt(a.created_at) }}</td>
            <td><span class="tag" :class="statusClass(a.status)">{{ statusLabel(a.status) }}</span></td>
            <td>
              <button v-if="a.status==='open'" class="btn sm" @click="resolve(a.id)">处理</button>
              <span v-else class="muted">—</span>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="7" class="empty">
            <span class="empty-icon">◉</span>暂无告警
          </td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { listAlerts, scanAlerts, resolveAlert, listCommunities } from '../api.js'

const items = ref([])
const communities = ref([])
const search = ref('')
const levelFilter = ref('')
const statusFilter = ref('')

function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }
function levelClass(l){ return { critical:'neg', warn:'warn', info:'info' }[l] || 'neu' }
function levelDot(l){ return { critical:'red', warn:'amber', info:'blue' }[l] || 'gray' }
function levelLabel(l){ return { critical:'严重', warn:'警告', info:'提示' }[l] || l }
function statusClass(s){ return { open:'neg', resolved:'pos', ignored:'aux' }[s] || 'neu' }
function statusLabel(s){ return { open:'未处理', resolved:'已处理', ignored:'已忽略' }[s] || s }
function alertPlatform(a){
  const c = communities.value.find(x => x.id === a.community_id)
  const PLATFORM_LABELS = { taptap:'TapTap' }
  return c ? (PLATFORM_LABELS[c.platform] || c.platform) : '—'
}

const filtered = computed(() => {
  let arr = items.value
  if (search.value) {
    const q = search.value.toLowerCase()
    arr = arr.filter(a => (a.title||'').toLowerCase().includes(q) || (a.keyword||'').toLowerCase().includes(q))
  }
  if (levelFilter.value) arr = arr.filter(a => a.level === levelFilter.value)
  if (statusFilter.value) arr = arr.filter(a => a.status === statusFilter.value)
  return arr
})

async function load(){ items.value = await listAlerts({ limit: 200 }) }
async function scan(){ await scanAlerts(); await load() }
async function resolve(id){ await resolveAlert(id); await load() }
onMounted(async () => { try { communities.value = await listCommunities() } catch(e) {}; await load() })
</script>
