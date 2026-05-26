<template>
  <div class="agent-view">
    <!-- 顶部标题栏 -->
    <div class="agent-header">
      <button class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen" title="对话历史">
        <span>{{ sidebarOpen ? '◀' : '▶' }}</span>
      </button>
      <div class="agent-title">
        <span class="agent-icon">🧭</span>
        <h1>非遗探索助手</h1>
      </div>
      <div class="header-actions">
        <button class="new-chat-btn" @click="newChat">+ 新对话</button>
      </div>
    </div>

    <!-- 主体：侧边栏 + 对话 + 画布 -->
    <div class="agent-body">
      <!-- 对话历史侧边栏 -->
      <div class="history-sidebar" :class="{ open: sidebarOpen }">
        <div class="history-list">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            :class="['history-item', { active: conv.id === currentId }]"
            @click="switchConversation(conv.id)"
          >
            <div class="history-title">{{ conv.title }}</div>
            <div class="history-time">{{ formatTime(conv.updatedAt) }}</div>
            <button class="history-delete" @click.stop="deleteConversation(conv.id)" title="删除">×</button>
          </div>
          <div v-if="conversations.length === 0" class="history-empty">暂无对话记录</div>
        </div>
      </div>

      <!-- 左侧对话区 -->
      <div class="chat-panel">
        <div class="chat-messages" ref="chatArea">
          <!-- 欢迎页 -->
          <div v-if="messages.length === 0" class="welcome">
            <div class="welcome-icon">🏛</div>
            <h2>{{ greetingText || '你好，我是非遗探索助手' }}</h2>
            <p>我可以帮你搜索非遗项目、查找体验场馆、规划旅行路线</p>
            <div class="quick-tags">
              <button v-for="tag in quickTags" :key="tag" class="quick-tag" @click="sendQuick(tag)">
                {{ tag }}
              </button>
            </div>
          </div>

          <!-- 消息列表 -->
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['msg', msg.role]"
          >
            <div class="msg-avatar">{{ msg.role === 'user' ? '👤' : '🧭' }}</div>
            <div class="msg-bubble">
              <div v-if="msg.role === 'assistant' && msg.loading" class="typing-indicator">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </div>
              <MarkdownRenderer v-else :content="msg.content" />
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="chat-input">
          <textarea
            v-model="inputText"
            placeholder="输入你的需求，例如：广东有什么非遗？"
            rows="1"
            @keydown.enter.exact.prevent="sendMessage"
            @input="autoResize"
            ref="inputEl"
          ></textarea>
          <button class="send-btn" :disabled="!inputText.trim() || sending" @click="sendMessage">
            {{ sending ? '...' : '发送' }}
          </button>
        </div>
      </div>

      <!-- 右侧画布 -->
      <div class="canvas-panel" :class="{ 'has-content': panels.length > 0 }">
        <!-- 无内容时 -->
        <div v-if="panels.length === 0" class="canvas-empty">
          <div class="canvas-empty-icon">🎨</div>
          <p>搜索结果、场馆列表、旅行路线将在这里展示</p>
        </div>

        <!-- 有内容时 -->
        <div v-else class="canvas-content">
          <div v-for="(panel, i) in panels" :key="i" class="canvas-card">
            <!-- 非遗项目列表 -->
            <template v-if="panel.type === 'heritage_list'">
              <div class="canvas-card-header">
                <span class="canvas-card-icon">📜</span>
                <h3>非遗项目</h3>
                <span class="canvas-card-count">{{ panel.data.length }} 项</span>
              </div>
              <div class="heritage-grid">
                <div
                  v-for="item in panel.data"
                  :key="item.name"
                  class="heritage-item"
                  @click="goDetail(item.name)"
                >
                  <div class="heritage-name">
                    {{ item.name }}
                    <span v-if="item.unesco" class="unesco-badge">UNESCO</span>
                  </div>
                  <div class="heritage-meta">
                    <span v-if="item.category" class="heritage-cat">{{ item.category }}</span>
                    <span v-if="item.region" class="heritage-region">{{ item.region }}</span>
                  </div>
                  <div v-if="item.description" class="heritage-desc">{{ item.description }}</div>
                </div>
              </div>
            </template>

            <!-- 场馆列表 -->
            <template v-else-if="panel.type === 'venue_list'">
              <div class="canvas-card-header">
                <span class="canvas-card-icon">📍</span>
                <h3>体验场馆</h3>
                <span class="canvas-card-count">{{ panel.data.length }} 家</span>
              </div>
              <AmapView
                :venues="panel.data"
                height="280px"
                style="margin-bottom: 12px;"
              />
              <div class="venue-list">
                <div v-for="v in panel.data" :key="v.id" class="venue-item" @click="showVenueDetail(v)">
                  <div class="venue-name">{{ v.name }}</div>
                  <div class="venue-address">{{ v.address }}</div>
                  <div class="venue-meta">
                    <span v-if="v.rating" class="venue-rating">★ {{ v.rating }}</span>
                    <span v-if="v.tel" class="venue-tel">{{ v.tel }}</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- 旅行路线 -->
            <template v-else-if="panel.type === 'trip_plan'">
              <div class="canvas-card-header">
                <span class="canvas-card-icon">🗺</span>
                <h3>{{ panel.data.city }} · {{ panel.data.days }}日行程</h3>
                <button
                  class="save-trip-btn"
                  :class="{ saved: savedTripIds.has(panel.data.city + panel.data.days) }"
                  :disabled="savedTripIds.has(panel.data.city + panel.data.days)"
                  @click="saveTrip(panel)"
                >
                  {{ savedTripIds.has(panel.data.city + panel.data.days) ? '已保存' : '保存路线' }}
                </button>
              </div>
              <AmapView
                v-if="panel.data.route_data"
                :venues="panel.data.route_data.venues"
                :routeDays="panel.data.route_data.days"
                height="320px"
                style="margin-bottom: 12px;"
              />
              <div class="trip-content">
                <MarkdownRenderer :content="panel.data.itinerary" />
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- 场馆详情弹窗 -->
    <div v-if="venueDetail" class="venue-modal-overlay" @click.self="venueDetail = null">
      <div class="venue-modal">
        <button class="venue-modal-close" @click="venueDetail = null">×</button>
        <h3 class="venue-modal-name">{{ venueDetail.name }}</h3>
        <div v-if="venueDetail.rating" class="venue-modal-rating">★ {{ venueDetail.rating }}</div>
        <div class="venue-modal-info">
          <div v-if="venueDetail.address" class="venue-modal-row">
            <span class="venue-modal-label">地址</span>
            <span>{{ venueDetail.address }}</span>
          </div>
          <div v-if="venueDetail.tel" class="venue-modal-row">
            <span class="venue-modal-label">电话</span>
            <span>{{ venueDetail.tel }}</span>
          </div>
          <div v-if="venueDetail.business_hours" class="venue-modal-row">
            <span class="venue-modal-label">营业时间</span>
            <span>{{ venueDetail.business_hours }}</span>
          </div>
          <div v-if="venueDetail.type" class="venue-modal-row">
            <span class="venue-modal-label">类型</span>
            <span>{{ venueDetail.type }}</span>
          </div>
          <div v-if="venueDetail.district" class="venue-modal-row">
            <span class="venue-modal-label">区域</span>
            <span>{{ venueDetail.district }}</span>
          </div>
        </div>
        <div v-if="venueDetail.photos && venueDetail.photos.length" class="venue-modal-photos">
          <img v-for="(photo, pi) in venueDetail.photos" :key="pi" :src="photo" alt="场馆照片" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, userAuth } from '../api'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import AmapView from '../components/AmapView.vue'

const getStorageKey = () => {
  const uid = userAuth.getUserId()
  return uid ? `heritage_agent_conversations_${uid}` : 'heritage_agent_conversations_guest'
}

const router = useRouter()
const chatArea = ref(null)
const inputEl = ref(null)
const inputText = ref('')
const sending = ref(false)
const messages = ref([])
const panels = ref([])
const sidebarOpen = ref(false)
const venueDetail = ref(null)
const sessionId = ref('')
const userInterests = ref([])
const greetingText = ref('')
const savedTripIds = ref(new Set())

// ── 对话历史管理 ──
const conversations = ref([])
const currentId = ref('')

const genId = () => 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6)

const loadConversations = async () => {
  const userId = userAuth.getUserId()
  if (userId) {
    // 登录用户：从服务端加载
    try {
      const data = await api.getAgentConversations(userId)
      const serverConvs = (data.conversations || []).map(s => ({
        id: s.session_id,
        title: s.topic_summary || '对话',
        messages: [],
        panels: [],
        createdAt: s.started_at ? new Date(s.started_at).getTime() : Date.now(),
        updatedAt: s.started_at ? new Date(s.started_at).getTime() : Date.now(),
        _serverSession: true,
      }))
      // 合并本地未同步的对话
      let localConvs = []
      try {
        const raw = localStorage.getItem(getStorageKey())
        if (raw) localConvs = JSON.parse(raw)
      } catch {}
      const serverIds = new Set(serverConvs.map(c => c.id))
      const unsynced = localConvs.filter(c => !c.id.startsWith('conv_') || !serverIds.has(c.id))
      conversations.value = [...serverConvs, ...unsynced]
    } catch (e) {
      console.warn('加载服务端对话失败，回退本地:', e)
      _loadLocalConversations()
    }
  } else {
    _loadLocalConversations()
  }
}

const _loadLocalConversations = () => {
  try {
    const raw = localStorage.getItem(getStorageKey())
    if (raw) conversations.value = JSON.parse(raw)
    else conversations.value = []
  } catch { conversations.value = [] }
}

const saveConversations = () => {
  localStorage.setItem(getStorageKey(), JSON.stringify(conversations.value))
}

const getTitle = (msgs) => {
  const first = msgs.find(m => m.role === 'user')
  return first ? first.content.slice(0, 30) : '新对话'
}

const persistCurrent = () => {
  if (!currentId.value) return
  const idx = conversations.value.findIndex(c => c.id === currentId.value)
  if (idx === -1) return
  conversations.value[idx].messages = messages.value.map(m => ({
    role: m.role,
    content: m.content,
  }))
  conversations.value[idx].panels = panels.value
  conversations.value[idx].title = getTitle(messages.value)
  conversations.value[idx].updatedAt = Date.now()
  // 登录用户：对话已通过 agent 端点自动存服务端，只更新本地缓存
  // 未登录用户：存 localStorage
  if (!userAuth.isLoggedIn()) {
    saveConversations()
  } else {
    // 也存一份到 localStorage 作为快速缓存
    try { localStorage.setItem(getStorageKey(), JSON.stringify(conversations.value)) } catch {}
  }
}

const endCurrentSession = () => {
  if (sessionId.value) {
    api.endSession(sessionId.value).catch(() => {})
    sessionId.value = ''
  }
}

const newChat = () => {
  // 结束当前会话
  endCurrentSession()
  // 保存当前对话
  if (currentId.value && messages.value.length > 0) {
    persistCurrent()
  }
  const id = genId()
  conversations.value.unshift({
    id,
    title: '新对话',
    messages: [],
    panels: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  })
  currentId.value = id
  messages.value = []
  panels.value = []
  saveConversations()
}

const switchConversation = async (id) => {
  // 保存当前
  if (currentId.value && messages.value.length > 0) {
    persistCurrent()
  }
  const conv = conversations.value.find(c => c.id === id)
  if (!conv) return
  currentId.value = id

  // 如果是服务端会话且本地无消息，从服务端加载
  if (conv._serverSession && conv.messages.length === 0) {
    try {
      const data = await api.getAgentConversation(id)
      conv.messages = (data.messages || []).map(m => ({ role: m.role, content: m.content }))
    } catch (e) {
      console.warn('加载会话详情失败:', e)
    }
  }

  messages.value = (conv.messages || []).map(m => ({ ...m }))
  panels.value = conv.panels || []
  sidebarOpen.value = false
  scrollToBottom()
}

const deleteConversation = (id) => {
  conversations.value = conversations.value.filter(c => c.id !== id)
  saveConversations()
  if (currentId.value === id) {
    if (conversations.value.length > 0) {
      switchConversation(conversations.value[0].id)
    } else {
      newChat()
    }
  }
}

const formatTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

// ── 快捷标签 ──
const defaultQuickTags = [
  '广东有什么非遗',
  '广州有什么场馆',
  '规划广州一日游',
  '传统戏剧有哪些',
  '苏州有什么非遗',
]

const quickTags = computed(() => {
  if (userInterests.value.length > 0) {
    return userInterests.value.slice(0, 5).map(i => `给我讲讲${i}`)
  }
  return defaultQuickTags
})

const sendQuick = (tag) => {
  inputText.value = tag
  sendMessage()
}

const autoResize = () => {
  const el = inputEl.value
  if (el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatArea.value) {
      chatArea.value.scrollTop = chatArea.value.scrollHeight
    }
  })
}

const ensureSession = async () => {
  if (!userAuth.isLoggedIn()) return
  if (sessionId.value) return
  try {
    const userId = userAuth.getUserId()
    const res = await api.startSession(userId, 'explorer')
    sessionId.value = res.session_id
    // 同步本地对话 ID 与服务端 session ID
    if (currentId.value && currentId.value.startsWith('conv_')) {
      const idx = conversations.value.findIndex(c => c.id === currentId.value)
      if (idx !== -1) {
        conversations.value[idx].id = res.session_id
        currentId.value = res.session_id
      }
    }
  } catch (e) {
    console.warn('创建会话失败:', e)
  }
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  // 确保有当前对话
  if (!currentId.value) {
    newChat()
  }

  // 确保有会话（登录用户）
  await ensureSession()

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  autoResize()
  scrollToBottom()

  // 添加 assistant 占位
  const assistantIdx = messages.value.length
  messages.value.push({ role: 'assistant', content: '', loading: true })
  sending.value = true
  scrollToBottom()

  try {
    // 构建 history（不含最后一条空的 assistant）
    const history = messages.value
      .slice(0, -1)
      .filter(m => m.content)
      .map(m => ({ role: m.role, content: m.content }))

    const userId = userAuth.getUserId()
    const resp = await api.agentChat(text, history, userId, sessionId.value)

    // 更新 assistant 消息
    messages.value[assistantIdx].content = resp.reply || '暂无回复'
    messages.value[assistantIdx].loading = false

    // 更新画布面板
    if (resp.panels && resp.panels.length > 0) {
      panels.value = resp.panels
    }

    // 持久化
    persistCurrent()
  } catch (e) {
    messages.value[assistantIdx].content = '抱歉，发生了错误，请稍后重试。'
    messages.value[assistantIdx].loading = false
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

const goDetail = (name) => {
  router.push(`/project/${encodeURIComponent(name)}`)
}

const showVenueDetail = (venue) => {
  venueDetail.value = venue
}

const saveTrip = async (panel) => {
  if (!userAuth.isLoggedIn()) {
    window.location.href = '/login'
    return
  }
  const data = panel.data
  try {
    await api.saveTrip({
      user_id: userAuth.getUserId(),
      name: `${data.city} ${data.days}日游`,
      city: data.city || '',
      days: data.days || 1,
      itinerary: data.itinerary || '',
      route_data: data.route_data || {},
    })
    savedTripIds.value.add(panel.data.city + panel.data.days)
  } catch (e) {
    alert('保存失败')
  }
}

// 监听用户登录状态变化，切换时重新加载对应用户的对话
watch(() => userAuth.getUserId(), (newId, oldId) => {
  if (newId !== oldId) {
    endCurrentSession()
    persistCurrent()  // 保存旧用户对话
    loadConversations()  // 加载新用户对话
    // 恢复最新对话或创建新对话
    if (conversations.value.length > 0) {
      const latest = conversations.value[0]
      currentId.value = latest.id
      messages.value = (latest.messages || []).map(m => ({ ...m }))
      panels.value = latest.panels || []
    } else {
      currentId.value = ''
      messages.value = []
      panels.value = []
    }
  }
})

onMounted(async () => {
  // 登录用户：获取个性化问候
  const userId = userAuth.getUserId()
  if (userId) {
    try {
      const greetData = await api.getAgentGreeting(userId)
      greetingText.value = greetData.greeting || ''
      userInterests.value = greetData.interests || []
    } catch (e) {
      console.warn('获取问候失败:', e)
    }
  }

  await loadConversations()
  // 恢复最近一次对话
  if (conversations.value.length > 0) {
    const latest = conversations.value[0]
    currentId.value = latest.id
    // 如果是服务端会话，加载消息
    if (latest._serverSession && latest.messages.length === 0) {
      try {
        const data = await api.getAgentConversation(latest.id)
        latest.messages = (data.messages || []).map(m => ({ role: m.role, content: m.content }))
      } catch {}
    }
    messages.value = (latest.messages || []).map(m => ({ ...m }))
    panels.value = latest.panels || []
  }
  inputEl.value?.focus()
})

onUnmounted(() => {
  endCurrentSession()
})
</script>

<style scoped>
.agent-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px);
  background: #f5f5f5;
}

/* ─── 顶部 ─── */
.agent-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.sidebar-toggle {
  background: none;
  border: 1px solid #ddd;
  border-radius: 6px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 12px;
  color: #666;
  transition: all 0.2s;
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  border-color: #999;
  color: #333;
}

.agent-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-title h1 {
  font-size: 18px;
  margin: 0;
  color: #333;
}

.agent-icon {
  font-size: 22px;
}

.header-actions {
  margin-left: auto;
}

.new-chat-btn {
  background: var(--primary, #8B4513);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.new-chat-btn:hover {
  opacity: 0.9;
}

/* ─── 主体布局 ─── */
.agent-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ─── 历史侧边栏 ─── */
.history-sidebar {
  width: 0;
  overflow: hidden;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  transition: width 0.25s ease;
  flex-shrink: 0;
}

.history-sidebar.open {
  width: 240px;
}

.history-list {
  width: 240px;
  height: 100%;
  overflow-y: auto;
  padding: 8px;
}

.history-item {
  position: relative;
  padding: 10px 28px 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.history-item:hover {
  background: #f5f5f5;
}

.history-item.active {
  background: #eef2f7;
}

.history-title {
  font-size: 13px;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.history-time {
  font-size: 11px;
  color: #aaa;
  margin-top: 2px;
}

.history-delete {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #ccc;
  font-size: 16px;
  cursor: pointer;
  padding: 2px 4px;
  line-height: 1;
  opacity: 0;
  transition: all 0.15s;
}

.history-item:hover .history-delete {
  opacity: 1;
}

.history-delete:hover {
  color: #e74c3c;
}

.history-empty {
  text-align: center;
  color: #bbb;
  font-size: 13px;
  padding: 40px 10px;
}

/* ─── 左侧对话区 ─── */
.chat-panel {
  flex: 0 0 42%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e8e8e8;
  background: #fff;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

/* ─── 欢迎页 ─── */
.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: #888;
}

.welcome-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.welcome h2 {
  font-size: 20px;
  color: #333;
  margin: 0 0 8px;
}

.welcome p {
  font-size: 14px;
  margin: 0 0 24px;
}

.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 400px;
}

.quick-tag {
  background: #f0f0f0;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  padding: 6px 14px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-tag:hover {
  background: var(--primary, #8B4513);
  color: #fff;
  border-color: var(--primary, #8B4513);
}

/* ─── 消息 ─── */
.msg {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  animation: msgIn 0.3s ease;
}

@keyframes msgIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.msg.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  background: #f0f0f0;
}

.msg.user .msg-avatar {
  background: var(--primary, #8B4513);
  color: #fff;
  font-size: 14px;
}

.msg-bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.msg.assistant .msg-bubble {
  background: #f7f7f7;
  color: #333;
  border-top-left-radius: 4px;
}

.msg.user .msg-bubble {
  background: var(--primary, #8B4513);
  color: #fff;
  border-top-right-radius: 4px;
}

/* ─── 打字动画 ─── */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #999;
  animation: typingBounce 1.4s infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* ─── 输入框 ─── */
.chat-input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e8e8e8;
  background: #fff;
}

.chat-input textarea {
  flex: 1;
  resize: none;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
  line-height: 1.5;
}

.chat-input textarea:focus {
  border-color: var(--primary, #8B4513);
}

.send-btn {
  align-self: flex-end;
  background: var(--primary, #8B4513);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s;
  white-space: nowrap;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ─── 右侧画布 ─── */
.canvas-panel {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #fafafa;
}

.canvas-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #bbb;
  text-align: center;
}

.canvas-empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.canvas-empty p {
  font-size: 14px;
}

/* ─── 画布卡片 ─── */
.canvas-card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 16px;
  margin-bottom: 16px;
  animation: cardIn 0.3s ease;
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.canvas-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.canvas-card-icon {
  font-size: 18px;
}

.canvas-card-header h3 {
  font-size: 15px;
  margin: 0;
  color: #333;
}

.canvas-card-count {
  margin-left: auto;
  font-size: 12px;
  color: #999;
}

/* ─── 非遗项目网格 ─── */
.heritage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}

.heritage-item {
  padding: 10px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.heritage-item:hover {
  border-color: var(--primary, #8B4513);
  box-shadow: 0 2px 8px rgba(139, 69, 19, 0.1);
}

.heritage-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.unesco-badge {
  display: inline-block;
  background: #f39c12;
  color: #fff;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 4px;
  font-weight: 500;
  vertical-align: middle;
}

.heritage-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 4px;
}

.heritage-cat {
  font-size: 11px;
  color: var(--primary, #8B4513);
  background: rgba(139, 69, 19, 0.08);
  padding: 1px 6px;
  border-radius: 3px;
}

.heritage-region {
  font-size: 11px;
  color: #888;
}

.heritage-desc {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ─── 场馆列表 ─── */
.venue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.venue-item {
  padding: 10px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  transition: border-color 0.2s;
}

.venue-item:hover {
  border-color: #ddd;
}

.venue-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.venue-address {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.venue-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
}

.venue-rating {
  color: #f39c12;
}

.venue-tel {
  color: #666;
}

/* ─── 场馆卡片可点击 ─── */
.venue-item {
  cursor: pointer;
}

.venue-item:hover {
  border-color: var(--primary, #8B4513);
  box-shadow: 0 2px 8px rgba(139, 69, 19, 0.1);
}

/* ─── 场馆详情弹窗 ─── */
.venue-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.venue-modal {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  max-width: 420px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  animation: slideUp 0.25s ease;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.venue-modal-close {
  position: absolute;
  top: 12px;
  right: 16px;
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  line-height: 1;
}

.venue-modal-close:hover {
  color: #333;
}

.venue-modal-name {
  font-size: 18px;
  font-weight: 700;
  color: #333;
  margin: 0 0 8px;
  padding-right: 30px;
}

.venue-modal-rating {
  color: #f39c12;
  font-size: 14px;
  margin-bottom: 16px;
}

.venue-modal-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.venue-modal-row {
  display: flex;
  gap: 12px;
  font-size: 14px;
  line-height: 1.5;
}

.venue-modal-label {
  flex-shrink: 0;
  width: 70px;
  color: #999;
  font-size: 13px;
}

.venue-modal-photos {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  overflow-x: auto;
}

.venue-modal-photos img {
  width: 120px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
}

/* ─── 旅行路线 ─── */
.trip-content {
  font-size: 14px;
  line-height: 1.7;
  color: #444;
}

.save-trip-btn {
  margin-left: auto;
  padding: 4px 12px;
  font-size: 12px;
  background: var(--primary, #8B4513);
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.save-trip-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.save-trip-btn.saved,
.save-trip-btn:disabled {
  background: #aaa;
  cursor: default;
}

/* ─── 响应式 ─── */
@media (max-width: 768px) {
  .agent-body {
    flex-direction: column;
  }

  .history-sidebar.open {
    position: absolute;
    z-index: 10;
    top: 56px;
    left: 0;
    bottom: 0;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1);
  }

  .chat-panel {
    flex: 1;
    border-right: none;
    border-bottom: 1px solid #e8e8e8;
  }

  .canvas-panel {
    max-height: 40vh;
  }

  .heritage-grid {
    grid-template-columns: 1fr;
  }
}
</style>
