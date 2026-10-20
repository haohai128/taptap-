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
        <div class="card-head">
          <h3 class="card-title">近 7 天情绪趋势</h3>
          <div class="trend-legend">
            <span><i class="tl-dot pos"></i>正面</span>
            <span><i class="tl-dot neu"></i>中性</span>
            <span><i class="tl-dot neg"></i>负面</span>
          </div>
        </div>
        <div class="card-body trend-body">
          <div v-if="trendDays.length" class="trend-chart">
            <div class="trend-cols">
              <div v-for="d in trendDays" :key="d" class="trend-col">
                <div class="trend-count" :title="`共 ${trendTotal(d)} 帖`">{{ trendTotal(d) }}</div>
                <div class="trend-stack" :title="`${d}: 正${trendCount('positive',d)} 中${trendCount('neutral',d)} 负${trendCount('negative',d)}`">
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

    <!-- 第三层：近 7 日负面趋势 top 社区 + 最近负面内容 -->
    <div class="grid grid-2">
      <div class="card">
        <div class="card-head"><h3 class="card-title">社区负面排行</h3><router-link to="/communities" class="muted" style="font-size:12px">社区管理 →</router-link></div>
        <div class="card-body">
          <div v-if="negRanking.length" class="rank-list">
            <div v-for="(r,i) in negRanking" :key="r.id" class="rank-row">
              <span class="rank-no" :class="{ hot: i<3 }">{{ i+1 }}</span>
              <span class="rank-name">{{ r.name }}</span>
              <div class="rank-bar-wrap">
                <div class="rank-bar" :style="{width: r.pct + '%'}"></div>
              </div>
              <span class="rank-val danger">{{ r.negative }}</span>
              <span class="rank-sub muted">/ {{ r.total }}</span>
            </div>
          </div>
          <div v-else class="empty">暂无分析数据</div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h3 class="card-title">最近负面内容</h3><router-link to="/negative-library" class="muted" style="font-size:12px">全部 →</router-link></div>
        <table class="table">
          <thead><tr><th>标题</th><th>社区</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(p,i) in recentNegative" :key="i">
              <td class="ellipsis">{{ p.title || '(无标题)' }}</td>
              <td class="muted">{{ p.community_name || '—' }}</td>
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
import { getDashboardSummary, getNegativeLibrary, listCommunities } from '../api.js'

const summary = ref({ kpi: {}, sentiment_proportion: {}, trend: { days: [], series: {} }, hot_topics: [], alerts: [] })
const negative = ref([])
const communities = ref([])
const recentRuns = ref([])

const kpi = computed(() => summary.value.kpi || {})
const hotTopics = computed(() => summary.value.hot_topics || [])
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
function trendTotal(day){
  return ['positive','negative','neutral'].reduce((a,k)=>a+trendCount(k,day),0)
}

const recentNegative = computed(() => negative.value.slice(0,8))

function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }

async function load() {
  try { summary.value = await getDashboardSummary() } catch(e) {}
  try { communities.value = await listCommunities() } catch(e) {}
  try { negative.value = await getNegativeLibrary() } catch(e) {}
}

// 社区负面排行：负面数 / 已分析数，取前 6
const negRanking = computed(() => {
  const rows = communities.value.map(c => ({
    id: c.id,
    name: c.name,
    negative: c.negative_count || 0,
    total: (c.positive_count || 0) + (c.negative_count || 0) + (c.neutral_count || 0),
  })).filter(r => r.total > 0)
  const max = Math.max(...rows.map(r => r.negative), 1)
  rows.forEach(r => { r.pct = Math.round(r.negative / max * 100) })
  return rows.sort((a,b) => b.negative - a.negative).slice(0, 6)
})
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
.trend-legend { display: flex; gap: 10px; font-size: 11px; color: var(--text-muted); align-items: center; }
.tl-dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.tl-dot.pos { background: #4ADE80; }
.tl-dot.neu { background: #CBD5E1; }
.tl-dot.neg { background: #F87171; }
.trend-body { padding: 10px 12px; }
.trend-chart { height: 200px; display: flex; align-items: flex-end; }
.trend-cols { display: flex; gap: 10px; flex: 1; align-items: stretch; height: 100%; }
.trend-col { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; min-width: 0; height: 100%; }
.trend-count { text-align: center; font-size: 10px; color: var(--text-light); font-variant-numeric: tabular-nums; margin-bottom: 3px; }
.trend-stack { display: flex; flex-direction: column-reverse; border-radius: 4px 4px 0 0; overflow: hidden; min-height: 3px; flex: 1; }
.trend-stack:has(.tseg[style*="height: 0%"]) { min-height: 0; }
.tseg { width: 100%; }
.tseg.pos { background: #4ADE80; }
.tseg.neu { background: #CBD5E1; }
.tseg.neg { background: #F87171; }
.tseg + .tseg { border-top: 1px solid rgba(255,255,255,.55); }
.trend-day { text-align: center; font-size: 10px; color: var(--text-light); margin-top: 5px; white-space: nowrap; }

/* 热点话题 */
.topic-list { display: flex; flex-direction: column; gap: 7px; }
.topic-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.topic-rank { width: 18px; height: 18px; border-radius: 4px; background: var(--border-light); color: var(--text-muted); font-size: 11px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.topic-rank.hot { background: #FEF2F2; color: var(--danger); font-weight: 600; }
.topic-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topic-count { flex-shrink: 0; font-size: 11px; }

/* 社区负面排行 */
.rank-list { display: flex; flex-direction: column; gap: 10px; }
.rank-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.rank-no { width: 18px; height: 18px; border-radius: 4px; background: var(--border-light); color: var(--text-muted); font-size: 11px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rank-no.hot { background: #FEF2F2; color: var(--danger); font-weight: 600; }
.rank-name { width: 96px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex-shrink: 0; }
.rank-bar-wrap { flex: 1; height: 8px; background: var(--border-light); border-radius: 4px; overflow: hidden; }
.rank-bar { height: 100%; background: linear-gradient(90deg, #FCA5A5, #F87171); border-radius: 4px; }
.rank-val { font-variant-numeric: tabular-nums; font-weight: 600; flex-shrink: 0; min-width: 28px; text-align: right; }
.rank-val.danger { color: var(--danger); }
.rank-sub { flex-shrink: 0; font-size: 11px; }
</style>
