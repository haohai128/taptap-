<template>
  <div>
    <div class="card">
      <div class="card-body">
        <div class="filter-bar">
          <input class="input" v-model="newWord" placeholder="新增负面关键词" style="flex:1;min-width:240px" @keyup.enter="addWord" />
          <button class="btn danger sm" @click="addWord">添加</button>
        </div>
        <div class="kw-chips">
          <span class="kw-chip neg" v-for="k in keywords" :key="k.id" :class="{ disabled: !k.enabled }">
            {{ k.word }}
            <button class="kw-x" @click="toggleWord(k)">{{ k.enabled ? '禁用' : '启用' }}</button>
            <button class="kw-x danger" @click="removeWord(k.id)">×</button>
          </span>
          <span v-if="!keywords.length" class="muted" style="font-size:12px">暂无负面关键词。添加后，命中且情绪为负面的帖子会自动生成预警。</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-body">
        <div class="filter-bar">
          <input class="input" v-model="search" placeholder="搜索标题/作者" style="flex:1;min-width:240px" />
          <select class="select" v-model="riskFilter">
            <option value="">全部风险</option>
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
          <button class="btn aux sm" @click="exportData">导出</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3 class="card-title">负面内容工单 ({{ filtered.length }})</h3></div>
      <table class="table">
        <thead>
          <tr>
            <th style="width:32%">标题</th>
            <th>风险等级</th>
            <th>平台</th>
            <th>作者</th>
            <th>发布时间</th>
            <th>热度</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(p,i) in filtered" :key="i">
            <td>
              <div class="cell-title" @click="openDetail(p)">{{ p.title || '(无标题)' }}</div>
              <div class="cell-content muted">{{ truncate(p.content, 50) }}</div>
            </td>
            <td><span class="tag" :class="riskClass(p)">{{ riskLabel(p) }}</span></td>
            <td>{{ platformLabel(p.platform) }}</td>
            <td class="muted">{{ p.author || '—' }}</td>
            <td class="muted">{{ fmt(p.published_at) }}</td>
            <td class="num">{{ (p.like_count||0) + (p.reply_count||0) }}</td>
            <td>
              <button class="btn aux sm" @click="openDetail(p)">详情</button>
              <a v-if="p.raw_url" :href="p.raw_url" target="_blank" class="btn aux sm" style="margin-left:4px">原帖</a>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="7" class="empty">
            <span class="empty-icon">⚠</span>暂无负面内容
          </td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="detail">
      <div class="drawer-mask" @click="detail=null"></div>
      <div class="drawer">
        <div class="drawer-head">
          <div class="drawer-title">负面内容详情</div>
          <button class="btn aux sm" @click="detail=null">关闭</button>
        </div>
        <div class="drawer-body">
          <h3 style="margin:0 0 8px;font-size:15px">{{ detail.title || '(无标题)' }}</h3>
          <div class="muted" style="font-size:12px;margin-bottom:12px">
            {{ platformLabel(detail.platform) }} · {{ detail.author || '—' }} · {{ fmt(detail.published_at) }}
          </div>
          <div style="padding:10px 12px;background:#FEF2F2;border-radius:6px;font-size:13px;line-height:1.7;margin-bottom:14px;border:1px solid #FECACA">
            {{ detail.content || '(无正文)' }}
          </div>
          <div class="grid grid-2" style="margin-bottom:14px">
            <div><div class="muted" style="font-size:11px">风险等级</div><span class="tag" :class="riskClass(detail)">{{ riskLabel(detail) }}</span></div>
            <div><div class="muted" style="font-size:11px">热度</div><b>{{ (detail.like_count||0)+(detail.reply_count||0) }}</b></div>
          </div>
          <a v-if="detail.raw_url" :href="detail.raw_url" target="_blank" class="btn sm">查看原帖 →</a>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { getNegativeLibrary, listKeywords, addKeyword, deleteKeyword, toggleKeyword } from '../api.js'

const items = ref([])
const search = ref('')
const riskFilter = ref('')
const detail = ref(null)
const keywords = ref([])
const newWord = ref('')

async function loadWords(){ keywords.value = await listKeywords('negative') }
async function addWord(){ if(!newWord.value.trim())return; await addKeyword({word:newWord.value, category:'negative'}); newWord.value=''; await loadWords() }
async function removeWord(id){ await deleteKeyword(id); await loadWords() }
async function toggleWord(k){ await toggleKeyword(k.id, !k.enabled); await loadWords() }

const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }
function truncate(s, n){ if(!s) return ''; return s.length > n ? s.slice(0,n)+'…' : s }

function heatOf(p){ return (p.like_count||0) + (p.reply_count||0) }
function riskClass(p){
  const h = heatOf(p)
  if (h >= 50) return 'neg'
  if (h >= 10) return 'warn'
  return 'aux'
}
function riskLabel(p){
  const h = heatOf(p)
  if (h >= 50) return '高'
  if (h >= 10) return '中'
  return '低'
}
function riskValue(p){ return heatOf(p) >= 50 ? 'high' : heatOf(p) >= 10 ? 'medium' : 'low' }

const filtered = computed(() => {
  let arr = items.value
  if (search.value) {
    const q = search.value.toLowerCase()
    arr = arr.filter(p => (p.title||'').toLowerCase().includes(q) || (p.author||'').toLowerCase().includes(q))
  }
  if (riskFilter.value) arr = arr.filter(p => riskValue(p) === riskFilter.value)
  return arr
})

function openDetail(p){ detail.value = p }

function exportData(){
  const rows = [['标题','风险等级','平台','作者','发布时间','热度','链接']]
  filtered.value.forEach(p => rows.push([p.title, riskLabel(p), platformLabel(p.platform), p.author, fmt(p.published_at), heatOf(p), p.raw_url]))
  const csv = rows.map(r => r.map(c => `"${String(c||'').replace(/"/g,'""')}"`).join(',')).join('\n')
  const blob = new Blob(['\uFEFF'+csv], { type:'text/csv;charset=utf-8' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'negative_library.csv'; a.click()
}

onMounted(async () => { try { await loadWords() } catch(e) {} ; items.value = await getNegativeLibrary() })
</script>
<style scoped>
.kw-chips { display: flex; flex-wrap: wrap; gap: 6px; min-height: 32px; padding: 4px 0; }
.kw-chip.neg { display: inline-flex; align-items: center; gap: 4px; background: #FEF2F2; color: var(--danger); border:1px solid #FECACA; padding: 3px 8px; border-radius: 4px; font-size: 12px; }
.kw-chip.disabled { opacity: .5; text-decoration: line-through; }
.kw-x { background: transparent; border: none; color: inherit; cursor: pointer; font-size: 11px; padding: 0 2px; }
.kw-x.danger { font-size: 14px; line-height: 1; }
.kw-x:hover { opacity: .7; }
.cell-title { font-weight: 500; cursor: pointer; color: var(--text); }
.cell-title:hover { color: var(--primary); }
.cell-content { font-size: 11px; margin-top: 2px; }
.num { font-variant-numeric: tabular-nums; text-align: right; }
</style>
