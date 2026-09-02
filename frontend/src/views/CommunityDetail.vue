<template>
  <div>
    <!-- 顶部信息条 -->
    <div class="card">
      <div class="card-body" style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div>
          <div class="muted" style="font-size:11px">社区</div>
          <div style="font-size:16px;font-weight:600">{{ community ? (community.name || community.taptap_id) : '加载中…' }}</div>
        </div>
        <div>
          <div class="muted" style="font-size:11px">平台</div>
          <div>{{ community ? platformLabel(community.platform) : '—' }}</div>
        </div>
        <div>
          <div class="muted" style="font-size:11px">帖子数</div>
          <div style="font-weight:600">{{ postCount }}</div>
        </div>
        <div>
          <div class="muted" style="font-size:11px">最近采集</div>
          <div class="muted">{{ community && community.last_run ? fmt(community.last_run.ended_at) : '尚未采集' }}</div>
        </div>
        <div style="margin-left:auto;display:flex;gap:8px">
          <span v-if="community" class="tag" :class="collectClass(community.collect_status)">{{ collectLabel(community.collect_status) }}</span>
          <button v-if="community && community.collect_status!=='stopped'" class="btn aux sm" @click="collectNow_" :disabled="collecting">{{ collecting ? '采集中…' : '立即采集' }}</button>
          <button v-if="community && community.collect_status!=='stopped'" class="btn danger sm" @click="stop" :disabled="stopping">{{ stopping ? '停止中…' : '停止采集' }}</button>
          <button v-if="community && community.collect_status==='stopped'" class="btn sm" @click="start">重新启用</button>
          <button class="btn aux sm" @click="reanalyze">重新分析</button>
        </div>
      </div>
    </div>

    <!-- 舆情摘要 KPI -->
    <div class="grid grid-3" style="margin-bottom:14px">
      <div class="kpi">
        <div class="kpi-label">正面</div>
        <div class="kpi-value" style="color:var(--success)">{{ sentimentCount.positive }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">中性</div>
        <div class="kpi-value muted">{{ sentimentCount.neutral }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">负面</div>
        <div class="kpi-value danger">{{ sentimentCount.negative }}</div>
      </div>
    </div>

    <!-- Tab 内容 -->
    <div class="card">
      <div class="tabs" style="padding:0 16px">
        <div class="tab" :class="{active:tab==='all'}" @click="tab='all'">全部内容 ({{ allPosts.length }})</div>
        <div class="tab" :class="{active:tab==='bug'}" @click="tab='bug'">BUG 反馈 ({{ bugPosts.length }})</div>
        <div class="tab" :class="{active:tab==='suggestion'}" @click="tab='suggestion'">玩家建议 ({{ suggestionPosts.length }})</div>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th style="width:32%">标题</th>
            <th>作者</th>
            <th>发布时间</th>
            <th>情绪</th>
            <th class="num">点赞</th>
            <th class="num">回复</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in currentPosts" :key="p.id">
            <td>
              <div class="cell-title" @click="openDetail(p)">{{ p.title || '(无标题)' }}</div>
            </td>
            <td class="muted">{{ p.author || '—' }}</td>
            <td class="muted">{{ fmt(p.published_at) }}</td>
            <td><span class="tag" :class="sentClass(p.sentiment)">{{ sentLabel(p.sentiment) }}</span></td>
            <td class="num">{{ p.like_count }}</td>
            <td class="num">{{ p.reply_count }}</td>
            <td><a v-if="p.raw_url" :href="p.raw_url" target="_blank" class="muted" style="font-size:12px">原帖</a></td>
          </tr>
          <tr v-if="!currentPosts.length"><td colspan="7" class="empty">暂无内容</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 详情抽屉 -->
    <div v-if="detail">
      <div class="drawer-mask" @click="detail=null"></div>
      <div class="drawer">
        <div class="drawer-head"><div class="drawer-title">帖子详情</div><button class="btn aux sm" @click="detail=null">关闭</button></div>
        <div class="drawer-body">
          <h3 style="margin:0 0 8px;font-size:15px">{{ detail.title || '(无标题)' }}</h3>
          <div class="muted" style="font-size:12px;margin-bottom:12px">{{ detail.author || '—' }} · {{ fmt(detail.published_at) }}</div>
          <div style="padding:10px 12px;background:#F8FAFC;border-radius:6px;font-size:13px;line-height:1.7;margin-bottom:14px">{{ detail.content || '(无正文)' }}</div>
          <a v-if="detail.raw_url" :href="detail.raw_url" target="_blank" class="btn sm">查看原帖 →</a>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { listCommunities, collectNow, stopCollection, startCollection, reanalyze, listRuns, drillPosts, getContentLibrary } from '../api.js'

const props = defineProps({ id: [String, Number] })
const community = ref(null)
const allPosts = ref([])
const collecting = ref(false)
const stopping = ref(false)
const tab = ref('all')
const detail = ref(null)

const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }
function sentClass(s){ return { positive:'pos', negative:'neg', neutral:'neu' }[s] || 'neu' }
function sentLabel(s){ return { positive:'正面', negative:'负面', neutral:'中性' }[s] || s || '未分析' }
function collectClass(s){ return { enabled:'pos', stopped:'aux' }[s] || 'neu' }
function collectLabel(s){ return { enabled:'采集中', stopped:'已停止' }[s] || s }

const postCount = computed(() => allPosts.value.length)
const sentimentCount = computed(() => {
  const c = { positive:0, negative:0, neutral:0 }
  allPosts.value.forEach(p => { if (c[p.sentiment] !== undefined) c[p.sentiment]++ })
  return c
})
const bugPosts = computed(() => allPosts.value.filter(p => p.analysis && p.analysis.bugs && p.analysis.bugs.length))
const suggestionPosts = computed(() => allPosts.value.filter(p => p.analysis && p.analysis.suggestions && p.analysis.suggestions.length))
const currentPosts = computed(() => tab.value === 'all' ? allPosts.value : tab.value === 'bug' ? bugPosts.value : suggestionPosts.value)

function openDetail(p){ detail.value = p }

async function loadCommunity(){
  const all = await listCommunities()
  community.value = all.find(c => c.id == props.id) || null
}
async function loadPosts(){
  try {
    allPosts.value = await getContentLibrary({ community_id: props.id })
  } catch(e) { allPosts.value = [] }
}
async function collectNow_(){
  collecting.value = true
  try {
    await collectNow(props.id)
    await loadCommunity()
    await loadPosts()
  } catch(e){ alert(e.response?.data?.detail || e.message) }
  finally { collecting.value = false }
}
async function stop(){ stopping.value = true; try { await stopCollection(props.id); await loadCommunity() } finally { stopping.value = false } }
async function start(){ await startCollection(props.id); await loadCommunity() }
async function reanalyze_(){ await reanalyze(props.id); }

onMounted(async () => { await loadCommunity(); await loadPosts() })
</script>
<style scoped>
.cell-title { font-weight: 500; cursor: pointer; }
.cell-title:hover { color: var(--primary); }
.num { font-variant-numeric: tabular-nums; text-align: right; }
</style>
