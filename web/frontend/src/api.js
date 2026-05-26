import axios from 'axios'

export const http = axios.create({ baseURL: '/api', timeout: 30000 })

// 用户身份管理（localStorage 持久化）
export const userAuth = {
  getUserId: () => localStorage.getItem('heritage_user_id') || '',
  getNickname: () => localStorage.getItem('heritage_nickname') || '',
  isLoggedIn: () => !!localStorage.getItem('heritage_user_id'),
  save: (userId, nickname) => {
    localStorage.setItem('heritage_user_id', userId)
    localStorage.setItem('heritage_nickname', nickname)
  },
  clear: () => {
    localStorage.removeItem('heritage_user_id')
    localStorage.removeItem('heritage_nickname')
  },
}

export const api = {
  // 类别
  getCategories: () => http.get('/categories').then(r => r.data),

  // 搜索
  search: (params) => http.get('/search', { params }).then(r => r.data),
  searchEnriched: (params) => http.get('/search/enriched', { params }).then(r => r.data),

  // 活动/事件
  getEvents: (params) => http.get('/events', { params }).then(r => r.data),

  // 项目详情
  getProject: (name) => http.get(`/project/${encodeURIComponent(name)}`).then(r => r.data),

  // 场馆
  getVenues: (params) => http.get('/venues', { params }).then(r => r.data),
  getVenueDetail: (poiId) => http.get('/venue/detail', { params: { poi_id: poiId } }).then(r => r.data),

  // 大师列表
  getMasters: () => http.get('/masters').then(r => r.data),

  // 问答（支持用户感知）
  ask: (question, masterId, userId, sessionId) => http.post('/ask', {
    question,
    master_id: masterId || '',
    user_id: userId || '',
    session_id: sessionId || '',
  }).then(r => r.data),

  // 知识
  getKnowledge: (params) => http.get('/knowledge', { params }).then(r => r.data),

  // 百科
  getBaike: (keyword) => http.get(`/baike/${encodeURIComponent(keyword)}`).then(r => r.data),

  // 论坛
  getForumPosts: (params) => http.get('/forum/posts', { params }).then(r => r.data),
  getForumPost: (postId, viewerId) => http.get(`/forum/posts/${postId}`, { params: { viewer_id: viewerId } }).then(r => r.data),
  createForumPost: (data) => http.post('/forum/posts', data).then(r => r.data),
  deleteForumPost: (postId, userId) => http.delete(`/forum/posts/${postId}`, { params: { user_id: userId } }).then(r => r.data),
  toggleForumLike: (postId, userId) => http.post(`/forum/posts/${postId}/like`, { user_id: userId }).then(r => r.data),
  getForumComments: (postId, limit) => http.get(`/forum/posts/${postId}/comments`, { params: { limit } }).then(r => r.data),
  addForumComment: (postId, data) => http.post(`/forum/posts/${postId}/comments`, data).then(r => r.data),
  deleteForumComment: (commentId, userId) => http.delete(`/forum/comments/${commentId}`, { params: { user_id: userId } }).then(r => r.data),
  searchForumPosts: (params) => http.get('/forum/search', { params }).then(r => r.data),

  // 旅行
  planTrip: (data) => http.post('/trip', data).then(r => r.data),

  // 图片上传
  uploadImage: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },

  // 路线保存
  saveTrip: (data) => http.post('/trips/save', data).then(r => r.data),
  getSavedTrips: (userId) => http.get('/trips', { params: { user_id: userId } }).then(r => r.data),
  getSavedTrip: (routeId) => http.get(`/trips/${routeId}`).then(r => r.data),
  deleteSavedTrip: (routeId, userId) => http.delete(`/trips/${routeId}`, { params: { user_id: userId } }).then(r => r.data),

  // 探索助手 Agent
  agentChat: (message, history = [], userId = '', sessionId = '') =>
    http.post('/agent', { message, history, user_id: userId, session_id: sessionId }).then(r => r.data),

  // 探索助手：个性化问候
  getAgentGreeting: (userId) =>
    http.get('/agent/greeting', { params: { user_id: userId } }).then(r => r.data),

  // 探索助手：获取对话历史列表
  getAgentConversations: (userId) =>
    http.get('/agent/conversations', { params: { user_id: userId } }).then(r => r.data),

  // 探索助手：获取单个会话详情
  getAgentConversation: (sessionId) =>
    http.get(`/agent/conversations/${sessionId}`).then(r => r.data),

  // 地图配置
  getMapConfig: () => http.get('/map-config').then(r => r.data),

  // 用户系统
  userRegister: (nickname, password) => http.post('/user/register', { nickname, password }).then(r => r.data),
  userLogin: (nickname, password) => http.post('/user/login', { nickname, password }).then(r => r.data),
  getUser: (userId) => http.get(`/user/${userId}`).then(r => r.data),
  startSession: (userId, masterId) => http.post('/user/session/start', { user_id: userId, master_id: masterId }).then(r => r.data),
  endSession: (sessionId) => http.post('/user/session/end', null, { params: { session_id: sessionId } }).then(r => r.data),
  getUserHistory: (userId, masterId, limit) => http.get(`/user/${userId}/history`, { params: { master_id: masterId, limit } }).then(r => r.data),
  getUserSessions: (userId, masterId, limit) => http.get(`/user/${userId}/sessions`, { params: { master_id: masterId, limit } }).then(r => r.data),
  getSessionMessages: (sessionId, limit) => http.get(`/session/${sessionId}/messages`, { params: { limit } }).then(r => r.data),
  deleteSession: (sessionId) => http.delete(`/session/${sessionId}`).then(r => r.data),
  getUserProfile: (userId, masterId) => http.get(`/user/${userId}/profile/${masterId}`).then(r => r.data),
  getUserProfiles: (userId) => http.get(`/user/${userId}/profiles`).then(r => r.data),

  // 修行系统
  assignPractice: (userId, masterId) => http.post('/cultivation/practice/assign', { user_id: userId, master_id: masterId }).then(r => r.data),
  submitPractice: (userId, masterId, content) => http.post('/cultivation/practice/submit', { user_id: userId, master_id: masterId, content }).then(r => r.data),
  getPracticeHistory: (userId, masterId, limit) => http.get('/cultivation/practice/history', { params: { user_id: userId, master_id: masterId, limit } }).then(r => r.data),
  getCultivationMap: (userId, masterId) => http.get('/cultivation/map', { params: { user_id: userId, master_id: masterId } }).then(r => r.data),
  getCultivationStage: (userId, masterId) => http.get('/cultivation/stage', { params: { user_id: userId, master_id: masterId } }).then(r => r.data),
  doStageTransition: (userId, masterId) => http.post('/cultivation/stage/transition', { user_id: userId, master_id: masterId }).then(r => r.data),

  // 知识图谱
  graphSearch: (q, type, limit) => http.get('/graph/search', { params: { q, type, limit } }).then(r => r.data),
  graphNode: (nodeId) => http.get(`/graph/node/${encodeURIComponent(nodeId)}`).then(r => r.data),
  graphPath: (fromId, toId) => http.get('/graph/path', { params: { from_id: fromId, to_id: toId } }).then(r => r.data),
  graphChain: (person) => http.get('/graph/chain', { params: { person } }).then(r => r.data),
  graphStats: () => http.get('/graph/stats').then(r => r.data),
  graphExplore: (nodeId, depth) => http.get('/graph/explore', { params: { node_id: nodeId, depth } }).then(r => r.data),
  graphByType: (type, limit) => http.get('/graph/by-type', { params: { type, limit } }).then(r => r.data),
}
