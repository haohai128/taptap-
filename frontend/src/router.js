import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Communities from './views/Communities.vue'
import CommunityDetail from './views/CommunityDetail.vue'
import ContentLibrary from './views/ContentLibrary.vue'
import NegativeLibrary from './views/NegativeLibrary.vue'
import CollectorRecords from './views/CollectorRecords.vue'
import Settings from './views/Settings.vue'

const routes = [
  { path: '/', name: 'dashboard', component: Dashboard, meta: { title: '看板' } },
  { path: '/communities', name: 'communities', component: Communities, meta: { title: '社区管理' } },
  { path: '/communities/:id', name: 'community', component: CommunityDetail, props: true, meta: { title: '社区详情' } },
  { path: '/content-library', name: 'content-library', component: ContentLibrary, meta: { title: '内容库' } },
  { path: '/negative-library', name: 'negative-library', component: NegativeLibrary, meta: { title: '负面库' } },
  { path: '/collector-records', name: 'collector-records', component: CollectorRecords, meta: { title: '采集记录' } },
  { path: '/settings', name: 'settings', component: Settings, meta: { title: '系统设置' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
