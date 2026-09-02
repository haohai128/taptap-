<template>
  <div>
    <h2 class="page-title">总览</h2>

    <div class="grid-3" style="margin-bottom:18px">
      <div class="kpi-card">
        <div class="stat-num">{{ stats.communities }}</div>
        <div class="stat-label">已注册社区</div>
      </div>
      <div class="kpi-card success">
        <div class="stat-num">{{ stats.posts }}</div>
        <div class="stat-label">已采集帖子</div>
      </div>
      <div class="kpi-card" :class="{ danger: stats.openAlerts > 0 }">
        <div class="stat-num" :class="{'level-critical': stats.openAlerts > 0}">{{ stats.openAlerts }}</div>
        <div class="stat-label">未处理预警</div>
      </div>
    </div>

    <div class="grid-3" style="margin-bottom:18px">
      <div class="kpi-card">
        <div class="stat-num">{{ stats.analyzed }}</div>
        <div class="stat-label">AI 分析总数</div>
      </div>
      <div class="kpi-card">
        <div class="stat-num">{{ stats.reviewed }}</div>
        <div class="stat-label">已审核数量</div>
      </div>
      <div class="kpi-card" :class="{ warn: stats.reviewed > 0 && stats.accuracy < 60, danger: stats.reviewed > 0 && stats.accuracy < 30 }">
        <div class="stat-num" :class="{'level-warn': stats.reviewed > 0 && stats.accuracy < 60 && stats.accuracy >= 30, 'level-critical': stats.reviewed > 0 && stats.accuracy < 30}">
          {{ stats.reviewed ? stats.accuracy + '%' : '暂无数据' }}
        </div>
        <div class="stat-label">总体准确率</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>多平台采集概览</h3>
        <Chart :option="platformOption" :empty="!platforms.length" height="320px" />
      </div>
      <div class="card">
        <h3>最新预警</h3>
        <table v-if="alerts.length">
          <thead>
            <tr><th>等级</th><th>标题</th><th>时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in alerts.slice(0,5)" :key="a.id">
              <td><span class="tag" :class="alertTagClass(a.level)">{{ a.level }}</span></td>
              <td>{{ a.title }}</td>
              <td class="muted">{{ fmt(a.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="muted" style="padding:24px;text-align:center">暂无预警</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Chart from '../components/Chart.vue'
import { listCommunities, getPlatformOverview, listAlerts, getEvaluationAccuracy } from '../api.js'

const stats = ref({ communities: 0, posts: 0, openAlerts: 0, analyzed: 0, reviewed: 0, accuracy: 0 })
const platforms = ref([])
const alerts = ref([])

const PLATFORM_LABELS = { taptap:'TapTap' }

const platformOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: platforms.value.map(p => PLATFORM_LABELS[p.platform] || p.platform) },
  yAxis: { type: 'value' },
  series: [
    {
      type: 'bar',
      name: '帖子数',
      data: platforms.value.map(p => p.post_count),
      itemStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: '#818cf8' },
            { offset: 1, color: '#6366f1' },
          ],
        },
        borderRadius: [6, 6, 0, 0],
      },
      barWidth: '45%',
      label: { show: true, position: 'top', color: '#6b7280', fontSize: 11 },
    },
  ],
}))

function alertTagClass(l) { return { critical: 'neg', warn: 'neu', info: 'pos' }[l] || 'neu' }
function levelClass(l) { return { critical: 'level-critical', warn: 'level-warn', info: 'level-info' }[l] || '' }
function fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' }

async function load() {
  const cs = await listCommunities()
  stats.value.communities = cs.length
  platforms.value = await getPlatformOverview()
  stats.value.posts = platforms.value.reduce((s, p) => s + p.post_count, 0)
  stats.value.analyzed = platforms.value.reduce((s, p) => s + Object.values(p.sentiments || {}).reduce((a, b) => a + b, 0), 0)
  alerts.value = await listAlerts({ status: 'open', limit: 10 })
  stats.value.openAlerts = alerts.value.length
  try {
    const acc = await getEvaluationAccuracy()
    stats.value.reviewed = acc.total
    stats.value.accuracy = acc.overall_accuracy
  } catch (e) { console.warn('accuracy error', e) }
}
onMounted(load)
</script>
