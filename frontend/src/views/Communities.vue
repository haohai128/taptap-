<template>
  <div>
    <div class="card">
      <div class="card-head"><h3 class="card-title">社区管理</h3></div>
      <div class="card-body">
        <div class="filter-bar">
          <select class="select" v-model="form.platform">
            <option v-for="p in platforms" :key="p.value" :value="p.value" :disabled="!p.implemented">{{ p.label }}{{ p.implemented?'':' (未实现)' }}</option>
          </select>
          <input class="input" v-model="form.raw_url" placeholder="社区链接" style="flex:2" />
          <input class="input" v-model="form.name" placeholder="名称" />
          <input class="input" v-model.number="form.interval_seconds" type="number" placeholder="间隔(秒)" style="width:100px" />
          <input class="input" v-model.number="form.per_run_limit" type="number" placeholder="每次上限" style="width:100px" />
          <button class="btn" @click="submit">注册</button>
        </div>
        <p v-if="error" class="muted" style="color:var(--danger);font-size:12px">{{ error }}</p>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3 class="card-title">已注册社区 ({{ items.length }})</h3>
        <input class="input" v-model="search" placeholder="搜索社区" style="width:200px" />
      </div>
      <table class="table">
        <thead><tr><th>ID</th><th>平台</th><th>名称</th><th>社区标识</th><th>采集状态</th><th>间隔</th><th>最近采集</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="c in filtered" :key="c.id">
            <td class="muted">{{ c.id }}</td>
            <td>{{ platformLabel(c.platform) }}</td>
            <td><b>{{ c.name||'-' }}</b></td>
            <td class="muted">{{ c.taptap_id }}</td>
            <td><span class="tag" :class="collectClass(c.collect_status)">{{ collectLabel(c.collect_status) }}</span></td>
            <td class="muted">{{ c.interval_seconds }}s</td>
            <td class="muted">{{ c.last_run ? fmt(c.last_run.ended_at) : '尚未采集' }}</td>
            <td>
              <router-link :to="`/communities/${c.id}`" class="muted" style="font-size:12px">详情</router-link>
              <button class="btn aux sm" style="margin-left:6px" @click="collect(c.id)" :disabled="c.collect_status==='stopped'">采集</button>
              <button v-if="c.collect_status!=='stopped'" class="btn danger sm" style="margin-left:4px" @click="stop(c.id)">停止</button>
              <button v-else class="btn sm" style="margin-left:4px" @click="start(c.id)">启用</button>
              <button class="btn danger sm" style="margin-left:4px" @click="remove(c.id)">删除</button>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="9" class="empty">暂无社区</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { listCommunities, createCommunity, collectNow, stopCollection, startCollection, deleteCommunity, listPlatforms } from '../api.js'
const items = ref([]); const platforms = ref([])
const form = ref({ platform:'taptap', raw_url:'', name:'', interval_seconds:3600, per_run_limit:50 })
const error = ref(''); const search = ref('')
const PLATFORM_LABELS = { taptap:'TapTap' }
function platformLabel(p){ return PLATFORM_LABELS[p] || p }
function fmt(s){ return s ? s.replace('T',' ').slice(0,16) : '—' }
function collectClass(s){ return { enabled:'pos', stopped:'aux' }[s] || 'neu' }
function collectLabel(s){ return { enabled:'采集中', stopped:'已停止' }[s] || s }
const filtered = computed(() => {
  if (!search.value) return items.value
  const q = search.value.toLowerCase()
  return items.value.filter(c => (c.name||'').toLowerCase().includes(q) || c.taptap_id.toLowerCase().includes(q))
})
async function load(){ items.value = await listCommunities(); platforms.value = await listPlatforms() }
async function submit(){ error.value=''; try{ await createCommunity(form.value); form.value={platform:'taptap',raw_url:'',name:'',interval_seconds:3600,per_run_limit:50}; await load() }catch(e){ error.value=e.response?.data?.detail||e.message } }
async function collect(id){ try{ await collectNow(id); await load() }catch(e){ alert(e.response?.data?.detail||e.message) } }
async function stop(id){ await stopCollection(id); await load() }
async function start(id){ await startCollection(id); await load() }
async function remove(id){ if(!confirm('确认删除该社区及其所有采集数据？此操作不可恢复。')) return; try{ await deleteCommunity(id); await load() }catch(e){ alert(e.response?.data?.detail||e.message) } }
onMounted(load)
</script>
