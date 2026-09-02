<template>
  <div>
    <div class="row" style="align-items:center;margin-bottom:18px">
      <h2 class="page-title" style="margin:0">情感分析看板</h2>
      <select v-model="cid" @change="loadAll" style="margin-left:12px;min-width:180px">
        <option v-for="c in communities" :key="c.id" :value="c.id">{{ c.name || c.taptap_id }}</option>
      </select>
      <DateRangeFilter @apply="onFilter" />
    </div>

    <div class="grid-2">
      <div class="card"><h3>情绪趋势</h3><Chart :option="trendOption" :loading="loading" :empty="!cid || !hasTrend" height="340px" v-if="cid" /></div>
      <div class="card"><h3>情感占比</h3><Chart :option="proportionOption" :loading="loading" :empty="!cid || !proportion.length" height="340px" v-if="cid" /></div>
    </div>
    <div class="grid-2">
      <div class="card"><h3>热词云</h3><Chart :option="wordcloudOption" :loading="loading" :empty="!cid || !words.length" height="340px" v-if="cid" /></div>
      <div class="card"><h3>时间分布</h3><Chart :option="timeOption" :loading="loading" :empty="!cid || !time.length" height="340px" v-if="cid" /></div>
    </div>
    <div class="grid-2">
      <div class="card"><h3>话题热度</h3><Chart :option="topicOption" :loading="loading" :empty="!cid || !topics.length" height="340px" v-if="cid" /></div>
      <div class="card">
        <h3>内容评价</h3>
        <table v-if="reviews.length">
          <thead><tr><th>对象</th><th>正面</th><th>负面</th><th>中性</th></tr></thead>
          <tbody>
            <tr v-for="(r,i) in reviews" :key="i">
              <td><b>{{ r.subject }}</b></td>
              <td><span class="tag pos">{{ r.positive }}</span></td>
              <td><span class="tag neg">{{ r.negative }}</span></td>
              <td><span class="tag neu">{{ r.neutral }}</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="muted" style="padding:24px;text-align:center">暂无</div>
      </div>
    </div>
    <div v-if="!cid" class="card muted" style="text-align:center;padding:40px">请先选择社区</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Chart from '../components/Chart.vue'
import DateRangeFilter from '../components/DateRangeFilter.vue'
import { listCommunities, getSentiment, getSentimentProportion, getTimeDistribution, getWordcloud, getTopics, getContentReviews } from '../api.js'

const communities = ref([]); const cid = ref(''); const since = ref(''); const until = ref('')
const sentiment = ref({ days: [], series: {} }); const proportion = ref([]); const time = ref([]); const words = ref([]); const topics = ref([]); const reviews = ref([])
const loading = ref(false)

const SENT_COLORS = { positive: '#22c55e', negative: '#ef4444', neutral: '#9ca3af', unknown: '#d1d5db' }
const SENT_LABELS = { positive: '正面', negative: '负面', neutral: '中性', unknown: '未知' }

function params() { const p = {}; if (since.value) p.since = since.value; if (until.value) p.until = until.value; return p }

async function loadAll() {
  if (!cid.value) return
  loading.value = true
  try {
    const p = params()
    sentiment.value = await getSentiment(cid.value, p)
    proportion.value = await getSentimentProportion(cid.value, p)
    time.value = await getTimeDistribution(cid.value, p)
    words.value = await getWordcloud(cid.value, p)
    topics.value = await getTopics(cid.value, p)
    reviews.value = await getContentReviews(cid.value, p)
  } finally { loading.value = false }
}

function onFilter({ since: s, until: u }) { since.value = s ? `${s}T00:00:00` : ''; until.value = u ? `${u}T23:59:59` : ''; loadAll() }

const hasTrend = computed(() => (sentiment.value.days || []).length > 0)

const trendOption = computed(() => {
  const s = sentiment.value.series || {}
  const days = sentiment.value.days || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['positive', 'negative', 'neutral', 'unknown'] },
    xAxis: { type: 'category', boundaryGap: false, data: days },
    yAxis: { type: 'value' },
    series: ['positive', 'negative', 'neutral', 'unknown'].map(k => ({
      name: k,
      type: 'line',
      stack: 'a',
      areaStyle: { opacity: 0.18 },
      emphasis: { focus: 'series' },
      data: (s[k] || []).map(d => d.count),
      itemStyle: { color: SENT_COLORS[k] },
      lineStyle: { color: SENT_COLORS[k] },
    })),
  }
})

const proportionOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, icon: 'circle' },
  series: [{
    type: 'pie',
    radius: ['42%', '70%'],
    avoidLabelOverlap: true,
    itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
    label: { show: true, formatter: '{b}\n{d}%', fontSize: 11 },
    data: proportion.value.map(p => ({
      name: SENT_LABELS[p.sentiment] || p.sentiment,
      value: p.count,
      itemStyle: { color: SENT_COLORS[p.sentiment] },
    })),
  }],
}))

const timeOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: time.value.map(t => t.date) },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar',
    data: time.value.map(t => t.count),
    itemStyle: {
      color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#818cf8' }, { offset: 1, color: '#6366f1' }] },
      borderRadius: [6, 6, 0, 0],
    },
    barWidth: '50%',
  }],
}))

const wordcloudOption = computed(() => ({
  tooltip: { formatter: '{b}: {c}' },
  series: [{
    type: 'graph',
    layout: 'force',
    roam: true,
    force: { repulsion: 140, edgeLength: 80 },
    data: words.value.slice(0, 50).map((w, i) => ({
      name: w.name,
      value: w.value,
      symbolSize: Math.min(64, 12 + w.value * 2.2),
      label: { show: true, color: '#fff', fontSize: Math.max(10, Math.min(18, 8 + w.value)) },
      itemStyle: { color: PALETTE[i % PALETTE.length] },
    })),
  }],
}))
const PALETTE = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#8b5cf6', '#14b8a6']

const topicOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: topics.value.map(t => t.topic), axisLabel: { rotate: 30, interval: 0 } },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar',
    data: topics.value.map(t => t.count),
    itemStyle: {
      color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#34d399' }, { offset: 1, color: '#10b981' }] },
      borderRadius: [6, 6, 0, 0],
    },
    label: { show: true, position: 'top', color: '#6b7280', fontSize: 11 },
  }],
}))

onMounted(async () => {
  communities.value = await listCommunities()
  if (communities.value.length) cid.value = communities.value[0].id
  await loadAll()
})
</script>
