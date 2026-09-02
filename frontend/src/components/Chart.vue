<template>
  <div class="chart-wrap">
    <div v-if="loading" class="chart-loading">
      <div class="chart-loading-spinner"></div>
      <span>加载中…</span>
    </div>
    <div v-else-if="empty" class="chart-empty">暂无数据</div>
    <div ref="el" class="chart-canvas" :style="{ height: height }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, default: () => ({}) },
  height: { type: String, default: '320px' },
  loading: { type: Boolean, default: false },
  empty: { type: Boolean, default: false },
})

const el = ref(null)
let chart = null
let ro = null

const PALETTE = [
  '#6366f1', '#22c55e', '#ef4444', '#f59e0b',
  '#06b6d4', '#ec4899', '#8b5cf6', '#14b8a6',
]
const SEMANTIC = {
  positive: '#22c55e', negative: '#ef4444', neutral: '#9ca3af', unknown: '#9ca3af',
}

function applyTheme(opt) {
  if (!opt) return opt
  const o = JSON.parse(JSON.stringify(opt))
  o.color = o.color || PALETTE
  o.textStyle = { fontFamily: 'system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif', ...o.textStyle }
  o.grid = { left: 12, right: 20, top: 36, bottom: 8, containLabel: true, ...(o.grid || {}) }
  o.tooltip = {
    trigger: 'axis',
    backgroundColor: 'rgba(17,24,39,.92)',
    borderWidth: 0,
    textStyle: { color: '#f9fafb', fontSize: 12 },
    axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(99,102,241,.08)' } },
    ...o.tooltip,
  }
  o.legend = { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { fontSize: 12, color: '#6b7280' }, ...o.legend }
  if (o.xAxis) {
    const ax = (x) => ({ axisLine: { lineStyle: { color: '#e5e7eb' } }, axisTick: { show: false }, axisLabel: { color: '#9ca3af', fontSize: 11 }, ...(x || {}) })
    if (Array.isArray(o.xAxis)) o.xAxis = o.xAxis.map(ax); else o.xAxis = ax(o.xAxis)
  }
  if (o.yAxis) {
    const ay = (y) => ({ axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: '#f3f4f6', type: 'dashed' } }, axisLabel: { color: '#9ca3af', fontSize: 11 }, ...(y || {}) })
    if (Array.isArray(o.yAxis)) o.yAxis = o.yAxis.map(ay); else o.yAxis = ay(o.yAxis)
  }
  if (o.series && Array.isArray(o.series)) {
    o.series = o.series.map((s) => {
      if (!s) return s
      const ns = { ...s }
      if (ns.type === 'line') {
        ns.smooth = ns.smooth !== false
        ns.symbol = ns.symbol || 'circle'
        ns.symbolSize = ns.symbolSize || 6
        ns.lineStyle = { width: 2.5, ...(ns.lineStyle || {}) }
        ns.areaStyle = ns.areaStyle || { opacity: 0.12 }
      }
      if (ns.type === 'bar') {
        ns.barWidth = ns.barWidth || '50%'
        ns.itemStyle = { borderRadius: [6, 6, 0, 0], ...(ns.itemStyle || {}) }
      }
      if (ns.type === 'pie') {
        ns.itemStyle = { borderColor: '#fff', borderWidth: 2, borderRadius: 4, ...(ns.itemStyle || {}) }
        ns.label = { color: '#6b7280', fontSize: 11, ...ns.label }
      }
      if (ns.name && SEMANTIC[ns.name]) {
        ns.itemStyle = { color: SEMANTIC[ns.name], ...(ns.itemStyle || {}) }
        if (ns.type === 'line') ns.lineStyle = { color: SEMANTIC[ns.name], width: 2.5, ...(ns.lineStyle || {}) }
      }
      return ns
    })
  }
  return o
}

function render() {
  if (!chart || !el.value) return
  chart.setOption(applyTheme(props.option || {}), props.option ? false : true)
}

function resize() { if (chart) chart.resize() }

onMounted(async () => {
  await nextTick()
  chart = echarts.init(el.value)
  render()
  if (window.ResizeObserver) {
    ro = new ResizeObserver(() => resize())
    ro.observe(el.value)
  }
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  if (ro) ro.disconnect()
  if (chart) { chart.dispose(); chart = null }
})

watch(() => props.option, () => render(), { deep: true })
defineExpose({ resize, getInstance: () => chart })
</script>

<style scoped>
.chart-wrap { position: relative; width: 100%; }
.chart-canvas { width: 100%; }
.chart-loading, .chart-empty {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  gap: 8px; color: #9ca3af; font-size: 13px; z-index: 2;
}
.chart-loading-spinner {
  width: 18px; height: 18px; border: 2px solid #e5e7eb; border-top-color: #6366f1;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
