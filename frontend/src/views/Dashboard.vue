<template>
  <div>
    <!-- 第一层：6 KPI -->
    <div class="grid grid-6" style="margin-bottom:14px">
      <div class="kpi">
        <div class="kpi-label">总内容</div>
        <div class="kpi-value primary">{{ kpi.total }}</div>
        <div class="kpi-foot">全部已采集帖子</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">待分析</div>
        <div class="kpi-value warn">{{ kpi.pending }}</div>
        <div class="kpi-foot">尚未 AI 分析</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">正面</div>
        <div class="kpi-value" style="color:var(--success)">{{ kpi.positive }}</div>
        <div class="kpi-foot">AI 判定正面</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">负面</div>
        <div class="kpi-value danger">{{ kpi.negative }}</div>
        <div class="kpi-foot">AI 判定负面</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">被删除</div>
        <div class="kpi-value muted">{{ kpi.deleted }}</div>
        <div class="kpi-foot">玩家已删除帖子</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">互动总量</div>
        <div class="kpi-value">{{ kpi.total_likes + kpi.total_replies }}</div>
        <div class="kpi-foot">👍 {{ kpi.total_likes }} · 💬 {{ kpi.total_replies }}</div>
      </div>
    </div>

    <!-- 第二层：情绪占比 + 近7天趋势 + 热点话题 -->
    <div class="grid grid-3" style="margin-bottom:14px">
      <div class="card">
        <div class="card-head"><h3 class="card-title">情绪占比</h3></div>
        <div class="card-body">
          <div class="sent-bar">
            <div class="sent-seg pos" :style="{width: pct('positive') + '%'}" :title="`正面 ${sentCount('positive')}`"></div>
            <div class="sent-seg neu" :style="{width: pct('neutral') + '%'}" :title="`中性 ${sentCount('neutral')}`"></div>
            <div class="sent-seg neg" :style="{width: pct('negative') + '%'}" :title="`负面 ${sentCount('negative')}`"></div>
            <div class="sent-seg unk" :style="{width: pct('unknown') + '%'}" :title="`未知 ${sentCount('unknown')}`"></div>
          </div>
          <div class="sent-legend">
            <span><i class="dot green"></i>正面 {{ sentCount('positive') }}（{{ pct('positive') }}%）</span>
            <span><i class="dot gray"></i>中性 {{ sentCount('neutral') }}（{{ pct('neutral') }}%）</span>
            <span><i class="dot red"></i>负面 {{ sentCount('negative') }}（{{ pct('negative') }}%）</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h3 class="card-title">近 7 天情绪趋势</h3></div>
        <div class="card-body trend-body">
          <div v-if="trendDays.length" class="trend-chart">
            <div class="trend-cols">
              <div v-for="d in trendDays" :key="d" class="trend-col" :title="`${d}: 正${trendCount('positive',d)} 中${trendCount('neutral',d)} 负${trendCount('negative',d)}`">
                <div class="trend-stack">
                  <div class="tseg pos" :style="{height: trendPct('positive',d) + '%'}"></div>
                  <div class="tseg neu" :style="{height: trendPct('neutral',d) + '%'}"></div>
                  <div class="tseg neg" :style="{height: trendPct('negative',d) + '%'}"></div>
                </div>
                <div class="trend-day">{{ d.slice(5) }}</div>
              </div>
            </div>
          </div>
          <div v-else class="empty">近 7 天暂无数据</div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h3 class="card-title">热点话题</h3><router-link to="/content-library" class="muted" style="font-size:12px">内容库 →</router-link></div>
        <div class="card-body">
          <div v-if="hotTopics.length" class="topic-list">
            <div v-for="(t,i) in hotTopics" :key="i" class="topic-row">
              <span class="topic-rank" :class="{ hot: i < 3 }">{{ i+1 }}</span>
              <span class="topic-name">{{ t.name }}</span>
              <span class="topic-count muted">{{ t.count }} 帖</span>
            </div>
          </div>
          <div v-else class="empty">暂无话题数据</div>
        </div>
      </div>
    </div>

    <!-- 第三层：最新预警 + 最近采集 + 最近负面 -->
    <div class="grid grid-3">
      <div class="card">
        <div class="card-head"><h3 class="card-title">最新预警</h3></div>
        <table class="table">
          <thead><tr><th>标题</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="a in alerts" :key="a.id">
              <td class="ellipsis">{{ a.title }}</td>
              <td class="muted">{{ fmt(a.created_at) }}</td>
            </tr>
            <tr v-if="!alerts.length"><td colspan="2" class="empty">暂无预警</td></tr>
          </tbody>
        </table>
      </div>

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

      <div class="card">
        <div class="card-head"><h3 class="card-title">最近负面内容</h3><router-link to="/negative-library" class="muted" style="font-size:12px">全部 →</router-link></div>
        <table class="table">
          <thead><tr><th>标题</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(p,i) in recentNegative" :key="i">
              <td class="ellipsis">{{ p.title || '(无标题)' }}</td>
              <td class="muted">{{ fmt(p.published_at) }}</td>
            </tr>
            <tr v-if="!recentNegative.length"><td colspan="2" class="empty">暂无负面内容</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDashboardSummary, getNegativeLibrary, listCommunities } from '../api.js'

const summary = ref({ kpi: {}, sentiment_proportion: {}, trend: { days: [], series: {} }, hot_topics: [], alerts: [] })
const negative = ref([])
const communities = ref([])
const recentRuns = ref([])

const kpi = computed(() => summary.value.kpi || {})
const hotTopics = computed(() => summary.value.hot_topics || [])
const alerts = computed(() => summary.value.alerts || [])
const trendDays = computed(() => (summary.value.trend && summary.value.trend.days) || [])

function sentCount(s){ return (summary.value.sentiment_proportion || {})[s] || 0 }
function pct(s){
  const total = Object.values(summary.value.sentiment_proportion || {}).reduce((a,b)=>a+b,0)
  if (!total) return 0
  return Math.round(sentCount(s) / total * 1000) / 10
}
function trendCount(s, day){
  const series = (summary.value.trend && summary.value.trend.series) || {}
  const arr = series[s] || []
  const item = arr.find(x => x.date === day)
  return item ? item.count : 0
}
function trendPct(s, day){
  const total = ['positive','negative','neutral'].reduce((a,k)=>a+trendCount(k,day),0)
  if (!total) return 0
  return Math.round(trendCount(s,day)/total*100)
}

const recentNegative = computed(() => negative.value.slice(0,6))

function runClass(s){ return { success:'pos', blocked:'neg', partial:'warn', failed:'neg', stopped:'aux', running:'info' }[s] || 'neu' }
function runLabel(s){ return { success:'成功', blocked:'风控阻断', partial:'部分成功', failed:'失败', stopped:'已停止', running:'采集中' }[s] || s }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }

async function load() {
  try { summary.value = await getDashboardSummary() } catch(e) {}
  try { communities.value = await listCommunities() } catch(e) {}
  const runs = []
  communities.value.forEach(c => { if (c.last_run) runs.push({ ...c.last_run, community_id: c.id, community_name: c.name }) })
  runs.sort((a,b) => (b.started_at||'').localeCompare(a.started_at||''))
  recentRuns.value = runs.slice(0,6)
  try { negative.value = await getNegativeLibrary() } catch(e) {}
}
onMounted(load)
</script>

<style scoped>
.text-danger { color: var(--danger); }
.ellipsis { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.num { font-variant-numeric: tabular-nums; text-align: right; }
.kpi-value.muted { color: var(--text-muted); }
.kpi-value.warn { color: var(--warn); }

/* 情绪占比条 */
.sent-bar { display: flex; height: 26px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border); }
.sent-seg { transition: width .3s; }
.sent-seg.pos { background: #4ADE80; }
.sent-seg.neu { background: #CBD5E1; }
.sent-seg.neg { background: #F87171; }
.sent-seg.unk { background: #E2E8F0; }
.sent-legend { display: flex; flex-direction: column; gap: 5px; margin-top: 12px; font-size: 12px; color: var(--text-muted); }

/* 趋势图 */
.trend-body { padding: 10px 12px; }
.trend-chart { height: 180px; display: flex; align-items: flex-end; }
.trend-cols { display: flex; gap: 8px; flex: 1; align-items: stretch; height: 100%; }
.trend-col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; min-width: 0; }
.trend-stack { display: flex; flex-direction: column; border-radius: 4px 4px 0 0; overflow: hidden; min-height: 2px; }
.tseg.pos { background: #4ADE80; }
.tseg.neu { background: #CBD5E1; }
.tseg.neg { background: #F87171; }
.trend-day { text-align: center; font-size: 10px; color: var(--text-light); margin-top: 5px; white-space: nowrap; }

/* 热点话题 */
.topic-list { display: flex; flex-direction: column; gap: 7px; }
.topic-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.topic-rank { width: 18px; height: 18px; border-radius: 4px; background: var(--border-light); color: var(--text-muted); font-size: 11px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.topic-rank.hot { background: #FEF2F2; color: var(--danger); font-weight: 600; }
.topic-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topic-count { flex-shrink: 0; font-size: 11px; }
</style>
