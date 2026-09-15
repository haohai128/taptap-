<template>
  <div>
    <div class="card">
      <div class="card-head"><h3 class="card-title">采集记录</h3><button class="btn aux sm" @click="load">刷新</button></div>
      <div class="filter-bar" style="padding:12px 16px">
        <select class="select" v-model="f.community_id" @change="load"><option :value="''">全部社区</option><option v-for="c in communities" :key="c.id" :value="c.id">{{ c.name }}</option></select>
        <select class="select" v-model="f.status" @change="load">
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="blocked">风控阻断</option>
          <option value="partial">部分成功</option>
          <option value="failed">失败</option>
          <option value="stopped">已停止</option>
        </select>
      </div>
      <table class="table">
        <thead><tr><th>ID</th><th>社区</th><th>开始</th><th>结束</th><th>状态</th><th>抓取</th><th>新增</th><th>失败</th><th>错误</th></tr></thead>
        <tbody>
          <tr v-for="r in runs" :key="r.id">
            <td class="muted">{{ r.id }}</td>
            <td>{{ communityName(r.community_id) }}</td>
            <td class="muted">{{ fmt(r.started_at) }}</td>
            <td class="muted">{{ fmt(r.ended_at) }}</td>
            <td><span class="tag" :class="runClass(r.status)">{{ runLabel(r.status) }}</span></td>
            <td class="num">{{ r.fetched_count }}</td>
            <td class="num">{{ r.new_count }}</td>
            <td class="num">{{ r.failed_count }}</td>
            <td class="muted ellipsis">{{ r.error || '—' }}</td>
          </tr>
          <tr v-if="!runs.length"><td colspan="9" class="empty">暂无采集记录</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { listCommunities, listRuns } from '../api.js'
const communities = ref([])
const runs = ref([])
const f = ref({ community_id: '', status: '' })
function communityName(id){ const c = communities.value.find(x=>x.id===id); return c ? c.name : '#'+id }
function fmt(s){ return s ? s.replace('T',' ').slice(0,19) : '—' }
function runClass(s){ return { success:'pos', blocked:'neg', partial:'warn', failed:'neg', stopped:'aux', running:'info' }[s] || 'neu' }
function runLabel(s){ return { success:'成功', blocked:'风控阻断', partial:'部分成功', failed:'失败', stopped:'已停止', running:'采集中' }[s] || s }
async function load(){
  communities.value = await listCommunities()
  if (f.value.community_id) {
    runs.value = (await listRuns(f.value.community_id)).map(r => ({ ...r, community_id: f.value.community_id }))
    if (f.value.status) runs.value = runs.value.filter(r => r.status === f.value.status)
  } else {
    const all = []
    for (const c of communities.value) {
      try { const rs = await listRuns(c.id); rs.forEach(r => all.push({ ...r, community_id: c.id })) } catch(e) {}
    }
    all.sort((a,b) => (b.started_at||'').localeCompare(a.started_at||''))
    runs.value = f.value.status ? all.filter(r => r.status === f.value.status) : all
  }
}
onMounted(load)
</script>
<style scoped>
.ellipsis { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.num { font-variant-numeric: tabular-nums; text-align: right; }
</style>
