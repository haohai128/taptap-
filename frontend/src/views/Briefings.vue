<template>
  <div>
    <div class="card">
      <div class="card-head"><h3 class="card-title">生成简报</h3></div>
      <div class="card-body">
        <div class="filter-bar">
          <input class="input" v-model="form.title" placeholder="简报标题" style="flex:1;min-width:200px" />
          <label style="font-size:12px;color:var(--text-muted)">开始 <input type="date" v-model="form.period_start" class="input" style="display:block;margin-top:2px" /></label>
          <label style="font-size:12px;color:var(--text-muted)">结束 <input type="date" v-model="form.period_end" class="input" style="display:block;margin-top:2px" /></label>
          <button class="btn sm" @click="create">生成</button>
        </div>
        <textarea class="textarea" v-model="form.summary" placeholder="摘要（可空）" style="width:100%;margin-top:10px;min-height:60px"></textarea>
      </div>
    </div>

    <div class="card">
      <div class="card-head"><h3 class="card-title">历史简报 ({{ items.length }})</h3></div>
      <table class="table">
        <thead><tr><th>标题</th><th>周期</th><th>摘要</th><th>生成时间</th></tr></thead>
        <tbody>
          <tr v-for="b in items" :key="b.id">
            <td><b>{{ b.title }}</b></td>
            <td class="muted">{{ fmt(b.period_start) }} ~ {{ fmt(b.period_end) }}</td>
            <td class="muted ellipsis">{{ b.summary || '—' }}</td>
            <td class="muted">{{ fmt(b.created_at) }}</td>
          </tr>
          <tr v-if="!items.length"><td colspan="4" class="empty">暂无简报</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { listBriefings, createBriefing } from '../api.js'
const items = ref([])
const form = ref({ title:'', period_start:'', period_end:'', summary:'' })
function fmt(s){ return s ? s.replace('T',' ').slice(0,10) : '—' }
async function load(){ items.value = await listBriefings() }
async function create(){
  if(!form.value.title||!form.value.period_start||!form.value.period_end) return
  await createBriefing({ ...form.value, period_start:`${form.value.period_start}T00:00:00`, period_end:`${form.value.period_end}T23:59:59` })
  form.value = { title:'', period_start:'', period_end:'', summary:'' }
  await load()
}
onMounted(load)
</script>
<style scoped>
.ellipsis { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
