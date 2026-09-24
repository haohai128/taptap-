<template>
  <div>
    <div class="card">
      <div class="card-body">
        <div class="filter-bar">
          <input class="input" v-model="f.keyword" placeholder="搜索标题/作者/内容" style="flex:1;min-width:240px" @keyup.enter="load" />
          <select class="select" v-model="f.community_id" @change="load">
            <option value="">全部社区</option>
            <option v-for="c in communityOpts" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
          <select class="select" v-model="f.platform" @change="load">
            <option value="">全部平台</option>
            <option v-for="p in platformOpts" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
          <select class="select" v-model="f.sentiment" @change="load">
            <option value="">全部情绪</option>
            <option value="positive">正面</option>
            <option value="negative">负面</option>
            <option value="neutral">中性</option>
          </select>
          <select class="select" v-model="f.deleted" @change="load">
            <option value="">全部状态</option>
            <option value="normal">正常</option>
            <option value="deleted">被删除</option>
          </select>
          <select class="select" v-model="sortBy">
            <option value="published_at_desc">发布时间 ↓</option>
            <option value="published_at_asc">发布时间 ↑</option>
            <option value="like_desc">点赞数 ↓</option>
            <option value="reply_desc">回复数 ↓</option>
          </select>
          <button class="btn sm" @click="load">查询</button>
          <button class="btn aux sm" @click="reset">重置</button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3 class="card-title">内容列表 ({{ total }})</h3>
        <button class="btn aux sm" @click="exportData">导出</button>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>标题</th>
            <th>社区</th>
            <th>平台</th>
            <th>作者</th>
            <th>发布时间</th>
            <th>情绪</th>
            <th class="num">热度</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in sortedItems" :key="p.id">
            <td class="wrap-cell">
              <div class="cell-title" @click="openDetail(p)">{{ p.title || '(无标题)' }}</div>
              <div class="cell-content muted">{{ truncate(p.content, 60) }}</div>
              <div v-if="p.topics && p.topics.length" style="margin-top:3px;display:flex;gap:4px;flex-wrap:wrap">
                <span class="tag aux" v-for="t in p.topics" :key="t" style="font-size:10px;padding:1px 5px">{{ t }}</span>
              </div>
            </td>
            <td class="muted">{{ p.community_name || '—' }}</td>
            <td>{{ platformLabel(p.platform) }}</td>
            <td class="muted">{{ p.author || '—' }}</td>
            <td class="muted">{{ fmt(p.published_at) }}</td>
            <td class="wrap-cell">
              <span class="tag" :class="sentClass(p.sentiment)">{{ sentLabel(p.sentiment) }}</span>
              <div v-if="p.sentiment_reason" class="sent-reason">{{ p.sentiment_reason }}</div>
            </td>
            <td class="num"><span title="点赞">👍 {{ p.like_count }}</span> <span title="回复" style="margin-left:8px">💬 {{ p.reply_count }}</span></td>
            <td><span class="tag" :class="p.is_deleted ? 'neg' : 'pos'">{{ p.is_deleted ? '被删除' : '正常' }}</span></td>
            <td>
              <button class="btn aux sm" @click="openDetail(p)">详情</button>
              <a v-if="p.raw_url" :href="p.raw_url" target="_blank" class="btn aux sm" style="margin-left:4px">原帖</a>
            </td>
          </tr>
          <tr v-if="!sortedItems.length"><td colspan="9" class="empty">
            <span class="empty-icon">▤</span>暂无内容
          </td></tr>
        </tbody>
      </table>
      <div class="pagination" v-if="total > 0">
        <span>共 {{ total }} 条</span>
        <div class="pagination-actions">
          <button class="btn aux sm" :disabled="page<=1" @click="page--;load()">上一页</button>
          <span class="muted" style="padding:0 8px">第 {{ page }} 页</span>
          <button class="btn aux sm" :disabled="page*pageSize>=total" @click="page++;load()">下一页</button>
        </div>
      </div>
    </div>

    <!-- 详情抽屉 -->
    <div v-if="detail">
      <div class="drawer-mask" @click="detail=null"></div>
      <div class="drawer">
        <div class="drawer-head">
          <div class="drawer-title">内容详情</div>
          <button class="btn aux sm" @click="detail=null">关闭</button>
        </div>
        <div class="drawer-body">
          <h3 style="margin:0 0 8px;font-size:15px">{{ detail.title || '(无标题)' }}</h3>
          <div class="muted" style="font-size:12px;margin-bottom:12px">
            {{ detail.community_name || '—' }} · {{ platformLabel(detail.platform) }} · {{ detail.author || '—' }} · {{ fmt(detail.published_at) }}
          </div>
          <div style="padding:10px 12px;background:#F8FAFC;border-radius:6px;font-size:13px;line-height:1.7;margin-bottom:14px">
            {{ detail.content || '(无正文)' }}
          </div>

          <!-- AI 分析结果 -->
          <div class="grid grid-4" style="margin-bottom:14px">
            <div><div class="muted" style="font-size:11px">AI 情绪</div><span class="tag" :class="sentClass(detail.sentiment)">{{ sentLabel(detail.sentiment) }}</span></div>
            <div><div class="muted" style="font-size:11px">点赞</div><b>{{ detail.like_count }}</b></div>
            <div><div class="muted" style="font-size:11px">回复</div><b>{{ detail.reply_count }}</b></div>
            <div><div class="muted" style="font-size:11px">社区</div><b>{{ detail.community_name || '—' }}</b></div>
          </div>

          <div v-if="detail.sentiment_reason" style="margin-bottom:14px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">AI 情绪分析理由</div>
            <div style="font-size:13px;line-height:1.6;padding:8px 10px;background:#F8FAFC;border-radius:4px">{{ detail.sentiment_reason }}</div>
          </div>

          <div v-if="detail.topics && detail.topics.length" style="margin-bottom:14px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">话题标签</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap">
              <span class="tag aux" v-for="t in detail.topics" :key="t">{{ t }}</span>
            </div>
          </div>

          <div v-if="detail.bugs && detail.bugs.length" style="margin-bottom:14px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">BUG ({{ detail.bugs.length }})</div>
            <div v-for="(b, i) in detail.bugs" :key="'b'+i" style="font-size:12px;padding:6px 10px;background:#FEF2F2;border-radius:4px;margin-bottom:4px">
              <span class="tag neg" style="margin-right:6px">{{ b.category || b.severity || 'BUG' }}</span>{{ b.description || b.text || JSON.stringify(b) }}
            </div>
          </div>

          <div v-if="detail.suggestions && detail.suggestions.length" style="margin-bottom:14px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">建议 ({{ detail.suggestions.length }})</div>
            <div v-for="(s, i) in detail.suggestions" :key="'s'+i" style="font-size:12px;padding:6px 10px;background:#F0FDFA;border-radius:4px;margin-bottom:4px">
              <span class="tag pos" style="margin-right:6px">{{ s.category || s.type || '建议' }}</span>{{ s.description || s.text || JSON.stringify(s) }}
            </div>
          </div>

          <div v-if="detail.content_reviews && detail.content_reviews.length" style="margin-bottom:14px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">内容评价 ({{ detail.content_reviews.length }})</div>
            <div v-for="(r, i) in detail.content_reviews" :key="'cr'+i" style="font-size:12px;padding:6px 10px;background:#F8FAFC;border-radius:4px;margin-bottom:4px">
              <span class="tag aux" style="margin-right:6px">{{ r.aspect || r.dimension || '评价' }}</span>{{ r.comment || r.text || JSON.stringify(r) }}
            </div>
          </div>

          <a v-if="detail.raw_url" :href="detail.raw_url" target="_blank" class="btn sm">查看原帖 →</a>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { getContentLibrary, listPlatforms, listCommunities } from '../api.js'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const f = ref({ keyword:'', community_id:'', platform:'', sentiment:'', deleted:'' })
const sortBy = ref('published_at_desc')
const platformOpts = ref([])
const communityOpts = ref([])
const detail = ref(null)

const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }
function sentClass(s){ return { positive:'pos', negative:'neg', neutral:'neu' }[s] || 'neu' }
function sentLabel(s){ return { positive:'正面', negative:'负面', neutral:'中性' }[s] || s || '未分析' }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }
function truncate(s, n){ if(!s) return ''; return s.length > n ? s.slice(0,n)+'…' : s }

const sortedItems = computed(() => {
  const arr = [...items.value]
  if (sortBy.value === 'published_at_asc') arr.sort((a,b) => (a.published_at||'').localeCompare(b.published_at||''))
  else if (sortBy.value === 'like_desc') arr.sort((a,b) => (b.like_count||0)-(a.like_count||0))
  else if (sortBy.value === 'reply_desc') arr.sort((a,b) => (b.reply_count||0)-(a.reply_count||0))
  else arr.sort((a,b) => (b.published_at||'').localeCompare(a.published_at||''))
  return arr
})

function openDetail(p){ detail.value = p }

async function load(){
  const params = { ...f.value }
  // API 不支持分页，前端模拟（数据量不大）
  let arr = await getContentLibrary(params)
  if (f.value.deleted === 'normal') arr = arr.filter(p => !p.is_deleted)
  else if (f.value.deleted === 'deleted') arr = arr.filter(p => p.is_deleted)
  items.value = arr
  total.value = arr.length
  page.value = 1
}
function reset(){ f.value = { keyword:'', community_id:'', platform:'', sentiment:'', deleted:'' }; sortBy.value = 'published_at_desc'; load() }

function exportData(){
  const rows = [['标题','社区','平台','作者','发布时间','情绪','话题','点赞','回复','链接']]
  sortedItems.value.forEach(p => rows.push([p.title, p.community_name||'', platformLabel(p.platform), p.author, fmt(p.published_at), sentLabel(p.sentiment), (p.topics||[]).join('/'), p.like_count, p.reply_count, p.raw_url]))
  const csv = rows.map(r => r.map(c => `"${String(c||'').replace(/"/g,'""')}"`).join(',')).join('\n')
  const blob = new Blob(['\uFEFF'+csv], { type:'text/csv;charset=utf-8' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'content_library.csv'; a.click()
}

onMounted(async () => {
  try { platformOpts.value = await listPlatforms() } catch(e) {}
  try {
    communityOpts.value = await listCommunities()
    if (communityOpts.value.length && !f.value.community_id) f.value.community_id = communityOpts.value[0].id
  } catch(e) {}
  await load()
})
</script>
<style scoped>
.cell-title { font-weight: 500; cursor: pointer; color: var(--text); overflow: hidden; text-overflow: ellipsis; }
.cell-title:hover { color: var(--primary); }
.cell-content { font-size: 11px; margin-top: 2px; white-space: normal; }
.sent-reason { font-size: 12px; margin-top: 4px; color: var(--text-muted); line-height: 1.4; white-space: normal; }
.num { font-variant-numeric: tabular-nums; text-align: right; }
</style>
