<template>
  <div>
    <h2 class="page-title">多平台采集概览</h2>
    <div class="grid-3" style="margin-bottom:18px">
      <div class="kpi-card" v-for="(p, i) in items" :key="p.platform" :class="kpiClass(i)">
        <div class="stat-num">{{ p.post_count }}</div>
        <div class="stat-label">{{ label(p.platform) }}</div>
        <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">
          <span class="tag pos" v-if="p.sentiments.positive">正面 {{ p.sentiments.positive }}</span>
          <span class="tag neg" v-if="p.sentiments.negative">负面 {{ p.sentiments.negative }}</span>
          <span class="tag neu" v-if="p.sentiments.neutral">中性 {{ p.sentiments.neutral }}</span>
        </div>
      </div>
    </div>
    <div class="card">
      <h3>各平台帖子数对比</h3>
      <Chart :option="option" :empty="!items.length" height="340px" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Chart from '../components/Chart.vue'
import { getPlatformOverview } from '../api.js'

const items = ref([])
const labels = { taptap:'TapTap' }
function label(p) { return labels[p] || p }
function kpiClass(i) { return ['', 'success', 'warn', 'danger', ''][i % 5] }

const option = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  xAxis: { type: 'category', data: items.value.map(p => label(p.platform)) },
  yAxis: { type: 'value' },
  series: [{
    type: 'bar',
    data: items.value.map(p => p.post_count),
    itemStyle: {
      color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#818cf8' }, { offset: 1, color: '#6366f1' }] },
      borderRadius: [6, 6, 0, 0],
    },
    barWidth: '45%',
    label: { show: true, position: 'top', color: '#6b7280', fontSize: 11 },
  }],
}))

onMounted(async () => { items.value = await getPlatformOverview() })
</script>
