<template>
  <div>
    <!-- 准确率 KPI -->
    <div class="grid grid-4" style="margin-bottom:14px">
      <div class="kpi">
        <div class="kpi-label">已审核</div>
        <div class="kpi-value">{{ acc.total }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">总体准确率</div>
        <div class="kpi-value primary">{{ acc.total ? acc.overall_accuracy + '%' : '—' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">AI 错误</div>
        <div class="kpi-value danger">{{ acc.incorrect_count + acc.partial_count }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">待审核</div>
        <div class="kpi-value warn">{{ pendingCount }}</div>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="card">
      <div class="card-body">
        <div class="filter-bar">
          <select class="select" v-model="filter.community_id" @change="loadPosts">
            <option :value="null">全部社区</option>
            <option v-for="c in communities" :key="c.id" :value="c.id">{{ c.name || c.taptap_id }}</option>
          </select>
          <select class="select" v-model="filter.status" @change="loadPosts">
            <option value="unreviewed">未审核</option>
            <option value="reviewed">已审核</option>
            <option value="incorrect">AI 错误</option>
            <option value="">全部</option>
          </select>
          <button class="btn aux sm" @click="loadPosts">刷新</button>
        </div>
      </div>
    </div>

    <!-- 分析内容列表（内联展示） -->
    <div class="card" v-for="it in items" :key="it.post.id">
      <div class="card-head">
        <h3 class="card-title" style="cursor:pointer" @click="toggleExpand(it.post.id)">{{ it.post.title || '(无标题)' }}</h3>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="tag" :class="sentClass(it.analysis.sentiment)">{{ sentLabel(it.analysis.sentiment) }}</span>
          <span v-if="it.review" class="tag" :class="correctClass(it.review.status)">{{ correctLabel(it.review.status) }}</span>
          <span v-else class="tag aux">未审核</span>
          <span class="muted" style="font-size:11px">{{ platformLabel(it.post.platform) }} · {{ fmt(it.post.published_at) }}</span>
        </div>
      </div>
      <div class="card-body">
        <!-- 帖子摘要 -->
        <div style="padding:10px 12px;background:#F8FAFC;border-radius:6px;font-size:13px;line-height:1.7;margin-bottom:14px">
          {{ it.post.content || '(无正文)' }}
        </div>

        <!-- AI 分析结果（直接展示） -->
        <div class="grid grid-4" style="margin-bottom:14px">
          <div>
            <div class="muted" style="font-size:11px;margin-bottom:4px">AI 情绪</div>
            <span class="tag" :class="sentClass(it.analysis.sentiment)">{{ sentLabel(it.analysis.sentiment) }}</span>
          </div>
          <div>
            <div class="muted" style="font-size:11px;margin-bottom:4px">点赞</div>
            <b>{{ it.post.like_count }}</b>
          </div>
          <div>
            <div class="muted" style="font-size:11px;margin-bottom:4px">回复</div>
            <b>{{ it.post.reply_count }}</b>
          </div>
          <div>
            <div class="muted" style="font-size:11px;margin-bottom:4px">作者</div>
            <b>{{ it.post.author || '—' }}</b>
          </div>
        </div>

        <div v-if="it.analysis.sentiment_reason" style="margin-bottom:10px">
          <div class="muted" style="font-size:11px;margin-bottom:4px">情绪分析理由</div>
          <div style="font-size:13px;line-height:1.6">{{ it.analysis.sentiment_reason }}</div>
        </div>

        <div v-if="it.analysis.topics && it.analysis.topics.length" style="margin-bottom:10px">
          <div class="muted" style="font-size:11px;margin-bottom:4px">话题标签</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <span class="tag aux" v-for="t in it.analysis.topics" :key="t">{{ t }}</span>
          </div>
        </div>

        <!-- BUG / 建议 / 内容评价 可折叠 -->
        <div v-if="expanded.has(it.post.id)">
          <div v-if="it.analysis.bugs && it.analysis.bugs.length" style="margin-bottom:10px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">BUG ({{ it.analysis.bugs.length }})</div>
            <div v-for="(b, i) in it.analysis.bugs" :key="i" style="font-size:12px;padding:6px 10px;background:#FEF2F2;border-radius:4px;margin-bottom:4px">
              <span class="tag neg" style="margin-right:6px">{{ b.category || b.severity || 'BUG' }}</span>{{ b.description || b.text || JSON.stringify(b) }}
            </div>
          </div>

          <div v-if="it.analysis.suggestions && it.analysis.suggestions.length" style="margin-bottom:10px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">建议 ({{ it.analysis.suggestions.length }})</div>
            <div v-for="(s, i) in it.analysis.suggestions" :key="i" style="font-size:12px;padding:6px 10px;background:#F0FDFA;border-radius:4px;margin-bottom:4px">
              <span class="tag pos" style="margin-right:6px">{{ s.category || s.type || '建议' }}</span>{{ s.description || s.text || JSON.stringify(s) }}
            </div>
          </div>

          <div v-if="it.analysis.content_reviews && it.analysis.content_reviews.length" style="margin-bottom:10px">
            <div class="muted" style="font-size:11px;margin-bottom:4px">内容评价 ({{ it.analysis.content_reviews.length }})</div>
            <div v-for="(r, i) in it.analysis.content_reviews" :key="i" style="font-size:12px;padding:6px 10px;background:#F8FAFC;border-radius:4px;margin-bottom:4px">
              <span class="tag aux" style="margin-right:6px">{{ r.aspect || r.dimension || '评价' }}</span>{{ r.comment || r.text || JSON.stringify(r) }}
            </div>
          </div>
        </div>

        <!-- 人工审核结果 -->
        <div v-if="it.review" style="margin-bottom:10px;padding:8px 10px;background:#FFFBEB;border-radius:4px">
          <div class="muted" style="font-size:11px;margin-bottom:4px">人工审核 · {{ correctLabel(it.review.status) }} · {{ fmt(it.review.reviewed_at) }}</div>
          <div v-if="it.review.corrected_sentiment" style="font-size:12px">修正情绪: <span class="tag" :class="sentClass(it.review.corrected_sentiment)">{{ sentLabel(it.review.corrected_sentiment) }}</span></div>
        </div>

        <!-- 审核操作 -->
        <div v-if="!it.review || it.review.status !== 'correct'" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <button class="btn sm" @click="submitReview(it.post.id, 'correct', it)">标记正确</button>
          <button class="btn danger sm" @click="toggleCorrectForm(it.post.id)">标记错误/部分错误</button>
          <button class="btn aux sm" @click="toggleExpand(it.post.id)">{{ expanded.has(it.post.id) ? '收起详情' : '展开详情' }}</button>
        </div>
        <div v-else style="display:flex;gap:8px">
          <button class="btn aux sm" @click="toggleExpand(it.post.id)">{{ expanded.has(it.post.id) ? '收起详情' : '展开详情' }}</button>
        </div>

        <!-- 修正表单 -->
        <div v-if="correctForm.has(it.post.id)" style="margin-top:10px;padding:10px;background:#F8FAFC;border-radius:6px">
          <div v-for="d in dimensions" :key="d.key" style="margin-bottom:8px">
            <label style="font-size:12px;display:flex;align-items:center;gap:6px;margin-bottom:4px">
              <input type="checkbox" v-model="getForm(it.post.id)[d.key+'_correct']" /> {{ d.label }} 正确
            </label>
            <input v-if="d.type==='text'" class="input" v-model="getForm(it.post.id)['corrected_'+d.key]" :placeholder="'修正'+d.label" :disabled="getForm(it.post.id)[d.key+'_correct']" style="width:100%" />
            <textarea v-else class="textarea" v-model="getForm(it.post.id)['corrected_'+d.key+'_text']" :placeholder="'修正'+d.label+' (JSON)'" :disabled="getForm(it.post.id)[d.key+'_correct']" rows="2" style="width:100%"></textarea>
          </div>
          <button class="btn sm" @click="submitReview(it.post.id, 'partial', it)">提交修正</button>
        </div>
      </div>
    </div>

    <div v-if="!items.length" class="card"><div class="card-body empty">暂无符合条件的帖子</div></div>

    <!-- 分页 -->
    <div class="card" v-if="total > filter.page_size">
      <div class="card-body" style="display:flex;align-items:center;justify-content:space-between">
        <span class="muted">共 {{ total }} 条</span>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="btn aux sm" :disabled="filter.page<=1" @click="filter.page--;loadPosts()">上一页</button>
          <span class="muted" style="padding:0 8px">第 {{ filter.page }} 页</span>
          <button class="btn aux sm" :disabled="filter.page*filter.page_size>=total" @click="filter.page++;loadPosts()">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { listCommunities, listEvaluationPosts, submitReview as apiSubmitReview, getEvaluationAccuracy } from '../api.js'

const communities = ref([])
const items = ref([])
const total = ref(0)
const acc = ref({ total:0, correct_count:0, incorrect_count:0, partial_count:0, overall_accuracy:0 })
const filter = reactive({ community_id: null, status: 'unreviewed', page: 1, page_size: 20 })
const expanded = ref(new Set())
const correctForm = ref(new Set())
const forms = reactive({})

const dimensions = [
  { key:'sentiment', label:'情绪', type:'text' },
  { key:'bugs', label:'BUG', type:'json' },
  { key:'suggestions', label:'建议', type:'json' },
  { key:'topics', label:'话题', type:'json' },
  { key:'content_reviews', label:'内容评价', type:'json' },
]

const pendingCount = computed(() => total.value)

const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }
function sentClass(s){ return { positive:'pos', negative:'neg', neutral:'neu' }[s] || 'neu' }
function sentLabel(s){ return { positive:'正面', negative:'负面', neutral:'中性' }[s] || s || '未分析' }
function correctClass(s){ return { correct:'pos', incorrect:'neg', partial:'warn' }[s] || 'aux' }
function correctLabel(s){ return { correct:'正确', incorrect:'错误', partial:'部分错误' }[s] || s }

function toggleExpand(id){
  const s = new Set(expanded.value)
  if (s.has(id)) s.delete(id); else s.add(id)
  expanded.value = s
}
function toggleCorrectForm(id){
  const s = new Set(correctForm.value)
  if (s.has(id)) s.delete(id); else s.add(id)
  correctForm.value = s
}
function getForm(id){
  if (!forms[id]) {
    forms[id] = {
      sentiment_correct:true, bugs_correct:true, suggestions_correct:true, topics_correct:true, content_reviews_correct:true,
      corrected_sentiment:'', corrected_bugs_text:'[]', corrected_suggestions_text:'[]', corrected_topics_text:'[]', corrected_content_reviews_text:'[]',
    }
  }
  return forms[id]
}

async function loadAccuracy(){
  try { acc.value = await getEvaluationAccuracy({ community_id: filter.community_id }) } catch(e) {}
}
async function loadPosts(){
  const data = await listEvaluationPosts({ community_id: filter.community_id, status: filter.status || undefined, page: filter.page, page_size: filter.page_size })
  items.value = data.items || []
  total.value = data.total || 0
  await loadAccuracy()
}

async function submitReview(postId, status, it){
  try {
    if (status === 'correct') {
      await apiSubmitReview(postId, { status:'correct', sentiment_correct:true, bugs_correct:true, suggestions_correct:true, topics_correct:true, content_reviews_correct:true, corrected_sentiment:'', corrected_bugs:[], corrected_suggestions:[], corrected_topics:[], corrected_content_reviews:[] })
    } else {
      const f = getForm(postId)
      const payload = { status, sentiment_correct:f.sentiment_correct, bugs_correct:f.bugs_correct, suggestions_correct:f.suggestions_correct, topics_correct:f.topics_correct, content_reviews_correct:f.content_reviews_correct, corrected_sentiment:f.corrected_sentiment }
      for (const key of ['bugs','suggestions','topics','content_reviews']) {
        try { payload['corrected_'+key] = JSON.parse(f['corrected_'+key+'_text']||'[]') } catch(e) { alert(key+' JSON 格式错误'); return }
      }
      await apiSubmitReview(postId, payload)
    }
    await loadPosts()
  } catch(e){ alert(e.response?.data?.detail || e.message) }
}

onMounted(async () => { try { communities.value = await listCommunities() } catch(e) {}; await loadPosts() })
</script>
<style scoped>
.empty { text-align:center; color:var(--text-light); padding:30px; }
</style>
