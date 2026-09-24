import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export { api }

// 系统设置
export const getSettings = () => api.get('/settings').then(r => r.data)

// 看板汇总
export const getDashboardSummary = () => api.get('/dashboard/summary').then(r => r.data)

// 社区
export const listCommunities = () => api.get('/communities').then(r => r.data.items)
export const createCommunity = (p) => api.post('/communities', p).then(r => r.data)
export const deleteCommunity = (id) => api.delete(`/communities/${id}`).then(r => r.data)
export const collectNow = (id) => api.post(`/communities/${id}/collect-now`).then(r => r.data)
export const stopCollection = (id) => api.post(`/communities/${id}/stop-collection`).then(r => r.data)
export const startCollection = (id) => api.post(`/communities/${id}/start-collection`).then(r => r.data)
export const reanalyze = (id, params = {}) => api.post(`/communities/${id}/reanalyze`, null, { params }).then(r => r.data)
export const listRuns = (id) => api.get(`/communities/${id}/runs`).then(r => r.data.items)

// 图表
export const getSentiment = (id, params = {}) => api.get(`/communities/${id}/sentiment`, { params }).then(r => r.data)
export const getSentimentProportion = (id, params = {}) => api.get(`/communities/${id}/sentiment-proportion`, { params }).then(r => r.data.items)
export const getTimeDistribution = (id, params = {}) => api.get(`/communities/${id}/time-distribution`, { params }).then(r => r.data.items)
export const getTopics = (id, params = {}) => api.get(`/communities/${id}/topics`, { params }).then(r => r.data.items)
export const getWordcloud = (id, params = {}) => api.get(`/communities/${id}/wordcloud`, { params }).then(r => r.data.items)
export const getBugsSuggestions = (id, params = {}) => api.get(`/communities/${id}/bugs-suggestions`, { params }).then(r => r.data)
export const getContentReviews = (id, params = {}) => api.get(`/communities/${id}/content-reviews`, { params }).then(r => r.data.items)
export const getPlatformOverview = (params = {}) => api.get('/platform-overview', { params }).then(r => r.data.items)
export const drillPosts = (type, params) => api.get(`/insights/${type}/posts`, { params }).then(r => r.data.items)

// 平台
export const listPlatforms = () => api.get('/platforms').then(r => r.data.items)
export const getPlatformStatus = () => api.get('/platforms/status').then(r => r.data.items)

// 关键词
export const listKeywords = (category) => api.get('/keywords', { params: { category } }).then(r => r.data.items)
export const addKeyword = (p) => api.post('/keywords', p).then(r => r.data)
export const deleteKeyword = (id) => api.delete(`/keywords/${id}`).then(r => r.data)
export const toggleKeyword = (id, enabled) => api.patch(`/keywords/${id}`, null, { params: { enabled } }).then(r => r.data)

// 内容库 / 负面库
export const getContentLibrary = (params = {}) => api.get('/content-library', { params }).then(r => r.data.items)
export const getNegativeLibrary = (params = {}) => api.get('/negative-library', { params }).then(r => r.data.items)

// 预警
export const listAlerts = (params = {}) => api.get('/alerts', { params }).then(r => r.data.items)
export const scanAlerts = () => api.post('/alerts/scan').then(r => r.data)
export const resolveAlert = (id) => api.post(`/alerts/${id}/resolve`).then(r => r.data)

// 简报
export const listBriefings = (params = {}) => api.get('/briefings', { params }).then(r => r.data.items)
export const createBriefing = (p) => api.post('/briefings', p).then(r => r.data)

// AI 分析评估
export const listEvaluationPosts = (params = {}) => api.get('/evaluation/posts', { params }).then(r => r.data)
export const submitReview = (postId, p) => api.post(`/evaluation/posts/${postId}/review`, p).then(r => r.data)
export const getEvaluationAccuracy = (params = {}) => api.get('/evaluation/accuracy', { params }).then(r => r.data)
