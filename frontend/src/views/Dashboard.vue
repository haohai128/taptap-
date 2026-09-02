<template>
  <div>
    <!-- 第一层：4 KPI -->
    <div class="grid grid-4" style="margin-bottom:14px">
      <div class="kpi">
        <div class="kpi-label">总内容</div>
        <div class="kpi-value primary">{{ kpi.total }}</div>
        <div class="kpi-foot">全部已采集帖子</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">相关内容</div>
        <div class="kpi-value">{{ kpi.related }}</div>
        <div class="kpi-foot">命中追踪关键词</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">噪声内容</div>
        <div class="kpi-value muted">{{ kpi.noise }}</div>
        <div class="kpi-foot">未命中关键词</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">负面内容</div>
        <div class="kpi-value danger">{{ kpi.negative }}</div>
        <div class="kpi-foot">AI 判定负面</div>
      </div>
    </div>

    <!-- 第二层：平台概览卡片 -->
    <div class="card">
      <div class="card-head"><h3 class="card-title">平台概览</h3></div>
      <div class="card-body">
        <div class="grid grid-6">
          <div v-for="p in platforms" :key="p.platform" class="plat-card">
            <div class="plat-name">{{ platformLabel(p.platform) }}</div>
            <div class="plat-row"><span class="muted">总量</span><b class="num">{{ p.post_count }}</b></div>
            <div class="plat-row"><span class="muted">负面</span><b class="num" :class="{'text-danger':(p.sentiments.negative||0)>0}">{{ p.sentiments.negative||0 }}</b></div>
            <router-link to="/content-library" class="plat-link">查看 →</router-link>
          </div>
        </div>
      </div>
    </div>

    <!-- 第三层：平台汇总表 -->
    <div class="card">
      <div class="card-head">
        <h3 class="card-title">平台汇总</h3>
        <div class="filter-bar" style="margin:0">
          <input class="input" v-model="platSearch" placeholder="搜索平台" style="width:160px" />
          <button class="btn aux sm" @click="exportPlat">导出</button>
        </div>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th @click="sortPlat('platform')" class="sortable">平台</th>
            <th @click="sortPlat('post_count')" class="sortable num">总内容</th>
            <th @click="sortPlat('related')" class="sortable num">相关内容</th>
            <th @click="sortPlat('noise')" class="sortable num">噪声内容</th>
            <th @click="sortPlat('negative')" class="sortable num">负面内容</th>
            <th>最近采集</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in sortedPlatforms" :key="r.platform">
            <td><b>{{ platformLabel(r.platform) }}</b></td>
            <td class="num">{{ r.post_count }}</td>
            <td class="num">{{ r.related }}</td>
            <td class="num muted">{{ r.noise }}</td>
            <td class="num"><span :class="{'text-danger':r.negative>0}">{{ r.negative }}</span></td>
            <td class="muted">{{ platformLastRun(r.platform) }}</td>
          </tr>
          <tr v-if="!sortedPlatforms.length"><td colspan="6" class="empty">暂无数据</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 第四层：三个模块 -->
    <div class="grid grid-3">
      <!-- 最近采集状态 -->
      <div class="card">
        <div class="card-head"><h3 class="card-title">最近采集状态</h3><router-link to="/collector-records" class="muted" style="font-size:12px">全部 →</router-link></div>
        <table class="table">
          <thead><tr><th>社区</th><th>状态</th><th>新增</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="r in recentRuns" :key="r.id">
              <td>{{ r.community_name || ('#'+r.community_id) }}</td>
              <td><span class="tag" :class="runClass(r.status)">{{ runLabel(r.status) }}</span></td>
              <td class="num">{{ r.new_count }}</td>
              <td class="muted">{{ fmt(r.ended_at) }}</td>
            </tr>
            <tr v-if="!recentRuns.length"><td colspan="4" class="empty">暂无采集记录</td></tr>
          </tbody>
        </table>
      </div>

      <!-- 最近负面内容 -->
      <div class="card">
        <div class="card-head"><h3 class="card-title">最近负面内容</h3><router-link to="/negative-library" class="muted" style="font-size:12px">全部 →</router-link></div>
        <table class="table">
          <thead><tr><th>标题</th><th>平台</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(p,i) in recentNegative" :key="i">
              <td class="ellipsis">{{ p.title || '(无标题)' }}</td>
              <td>{{ platformLabel(p.platform) }}</td>
              <td class="muted">{{ fmt(p.published_at) }}</td>
            </tr>
            <tr v-if="!recentNegative.length"><td colspan="3" class="empty">暂无负面内容</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPlatformOverview, getNegativeLibrary, listCommunities } from '../api.js'

const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }

const platforms = ref([])
const negative = ref([])
const communities = ref([])
const platSearch = ref('')
const sortKey = ref('')
const sortDir = ref(1)

const kpi = computed(() => {
  const total = platforms.value.reduce((s,p)=>s+p.post_count,0)
  const negativeCount = platforms.value.reduce((s,p)=>s+(p.sentiments.negative||0),0)
  const related = platforms.value.reduce((s,p)=>s+(p.sentiments.positive||0)+(p.sentiments.negative||0)+(p.sentiments.neutral||0),0)
  return {
    total,
    related,
    noise: Math.max(0, total - related),
    negative: negativeCount,
  }
})

const sortedPlatforms = computed(() => {
  let arr = platforms.value.map(p => ({
    ...p,
    related: (p.sentiments.positive||0)+(p.sentiments.negative||0)+(p.sentiments.neutral||0),
    noise: Math.max(0, p.post_count - ((p.sentiments.positive||0)+(p.sentiments.negative||0)+(p.sentiments.neutral||0))),
    negative: p.sentiments.negative||0,
  }))
  if (platSearch.value) {
    const q = platSearch.value.toLowerCase()
    arr = arr.filter(p => platformLabel(p.platform).toLowerCase().includes(q))
  }
  if (sortKey.value) {
    arr = [...arr].sort((a,b) => {
      const va = a[sortKey.value], vb = b[sortKey.value]
      if (typeof va === 'number') return (va-vb)*sortDir.value
      return String(va).localeCompare(String(vb))*sortDir.value
    })
  }
  return arr
})

function sortPlat(key) {
  if (sortKey.value === key) { sortDir.value = -sortDir.value } else { sortKey.value = key; sortDir.value = 1 }
}

const recentRuns = ref([])
const recentNegative = computed(() => negative.value.slice(0,6))

function platformLastRun(platform) {
  const c = communities.value.find(c => c.platform === platform && c.last_run)
  return c && c.last_run ? fmt(c.last_run.ended_at) : '—'
}

function runClass(s){ return { success:'pos', blocked:'neg', partial:'warn', failed:'neg', stopped:'aux', running:'info' }[s] || 'neu' }
function runLabel(s){ return { success:'成功', blocked:'风控阻断', partial:'部分成功', failed:'失败', stopped:'已停止', running:'采集中' }[s] || s }
function sentClass(s){ return { positive:'pos', negative:'neg', neutral:'neu' }[s] || 'neu' }
function sentLabel(s){ return { positive:'正面', negative:'负面', neutral:'中性' }[s] || s }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }

function exportPlat() {
  const rows = [['平台','总内容','相关内容','噪声内容','负面内容','最近采集']]
  sortedPlatforms.value.forEach(r => rows.push([platformLabel(r.platform), r.post_count, r.related, r.noise, r.negative, platformLastRun(r.platform)]))
  const csv = rows.map(r => r.join(',')).join('\n')
  const blob = new Blob(['\uFEFF'+csv], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'platforms.csv'; a.click()
}

async function load() {
  platforms.value = await getPlatformOverview()
  communities.value = await listCommunities()
  // 最近采集：从各社区 last_run 聚合
  const runs = []
  communities.value.forEach(c => { if (c.last_run) runs.push({ ...c.last_run, community_id: c.id, community_name: c.name }) })
  runs.sort((a,b) => (b.started_at||'').localeCompare(a.started_at||''))
  recentRuns.value = runs.slice(0,6)
  // 负面内容
  try { negative.value = await getNegativeLibrary() } catch(e) {}
}
onMounted(load)
</script>

<style scoped>
.plat-card { border: 1px solid var(--border); border-radius: 6px; padding: 12px; background: #FAFBFC; }
.plat-name { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: var(--text); }
.plat-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; }
.plat-link { display: block; margin-top: 8px; font-size: 11px; color: var(--primary); text-decoration: none; }
.plat-link:hover { text-decoration: underline; }
.text-danger { color: var(--danger); }
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--primary); }
.ellipsis { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.num { font-variant-numeric: tabular-nums; text-align: right; }
</style>
