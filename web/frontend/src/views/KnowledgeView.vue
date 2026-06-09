<template>
  <div class="knowledge-view">
    <!-- ========== 阶段一：选择大师 ========== -->
    <div v-if="!enteredMaster" class="entrance">
      <div class="entrance-header">
        <h1>拜访非遗大师</h1>
        <p class="entrance-subtitle">推开一扇门，坐下来，听大师聊聊天</p>
      </div>

      <div class="master-gates">
        <div
          v-for="m in masters"
          :key="m.id"
          class="gate-card"
          @click="enterMaster(m)"
        >
          <div class="gate-scene">
            <div class="gate-avatar">{{ m.avatar }}</div>
            <div class="gate-name">{{ m.name }}</div>
            <div class="gate-title">{{ m.title }}</div>
          </div>
          <div class="gate-door">
            <div class="door-frame">
              <span class="door-text">推门进入</span>
            </div>
          </div>
          <div class="gate-scene-text">{{ m.scene }}</div>
        </div>
      </div>
    </div>

    <!-- ========== 阶段二：大师对话 ========== -->
    <transition name="studio-fade">
      <div v-if="enteredMaster" class="studio">
        <!-- 返回按钮 + 侧边栏开关 -->
        <div class="top-bar">
          <button class="back-btn" @click="leaveMaster">
            ← 离开{{ currentMaster.name }}的{{ currentMaster.id === 'wushishizi' ? '武馆' : '茶室' }}
          </button>
          <div class="top-bar-right">
            <button v-if="userId" class="new-conversation-btn" @click="startNewSession" title="新建对话">
              + 新对话
            </button>
            <button v-if="userId" class="sidebar-toggle" @click="historySidebarOpen = !historySidebarOpen" title="历史对话">
              {{ historySidebarOpen ? '✕' : '🕑' }} 历史
            </button>
            <button v-if="userId" class="sidebar-toggle" @click="showSidebar = !showSidebar" title="修行档案">
              {{ showSidebar ? '✕' : '☰' }} 修行
            </button>
          </div>
        </div>

        <!-- 修行侧边栏 -->
        <transition name="sidebar-slide">
          <div v-if="showSidebar && userProfile" class="sidebar">
            <div class="sidebar-section">
              <div class="sidebar-label">当前阶段</div>
              <div class="sidebar-stage">{{ userProfile.relationship_stage || '试探期' }}</div>
            </div>
            <div class="sidebar-section" v-if="parseTags(userProfile.interest_tags).length > 0">
              <div class="sidebar-label">兴趣标签</div>
              <div class="sidebar-tags">
                <span v-for="tag in parseTags(userProfile.interest_tags)" :key="tag" class="sidebar-tag">{{ tag }}</span>
              </div>
            </div>
            <div class="sidebar-section">
              <div class="sidebar-label">提问次数</div>
              <div class="sidebar-value">{{ userProfile.question_count || 0 }}</div>
            </div>
            <div class="sidebar-actions">
              <router-link to="/cultivation" class="sidebar-link">每日功课</router-link>
              <router-link to="/cultivation-map" class="sidebar-link">修行地图</router-link>
              <router-link to="/profile" class="sidebar-link">我的档案</router-link>
            </div>
          </div>
        </transition>

        <!-- 历史对话侧边栏 -->
        <transition name="sidebar-slide-left">
          <div v-if="historySidebarOpen" class="history-sidebar">
            <div class="history-header">
              <span>历史对话</span>
            </div>
            <div class="history-list">
              <template v-for="group in groupedSessions" :key="group.date">
                <div class="history-date-header">{{ group.date }}</div>
                <div
                  v-for="session in group.sessions"
                  :key="session.id"
                  :class="['history-item', { active: session.id === currentSessionId }]"
                  @click="switchSession(session)"
                >
                  <div class="history-title">{{ sessionTitle(session) }}</div>
                  <div class="history-meta">
                    <span class="history-time">{{ formatSessionTime(session.started_at) }}</span>
                    <span class="history-count">{{ session.msg_count || 0 }}条</span>
                  </div>
                  <button class="history-delete" @click.stop="deleteSession(session)" title="删除对话">×</button>
                </div>
              </template>
              <div v-if="sessions.length === 0" class="history-empty">暂无历史对话</div>
            </div>
          </div>
        </transition>

        <!-- 场景描述 -->
        <div class="scene-bar">
          <span class="scene-icon">{{ currentMaster.avatar }}</span>
          <div class="scene-text">{{ currentMaster.scene }}</div>
        </div>

        <!-- 聊天区 -->
        <div class="chat-area" ref="chatArea">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            :class="['chat-msg', msg.role, { 'msg-enter': i === messages.length - 1 }]"
          >
            <div class="msg-avatar">
              {{ msg.role === 'user' ? '👤' : currentMaster.avatar }}
            </div>
            <div class="msg-bubble">
              <MarkdownRenderer :content="msg.text" />
            </div>
          </div>

          <!-- 打字中 -->
          <div v-if="asking" class="chat-msg assistant msg-enter">
            <div class="msg-avatar">{{ currentMaster.avatar }}</div>
            <div class="msg-bubble typing">
              <span class="typing-text">{{ typingText }}</span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
              <span class="typing-dot"></span>
            </div>
          </div>
        </div>

        <!-- 快捷问题（首次进入或对话为空时显示） -->
        <div v-if="showQuickQuestions" class="quick-section">
          <div class="quick-label">你可以问：</div>
          <div class="quick-list">
            <button
              v-for="q in quickQuestions"
              :key="q"
              class="quick-btn"
              @click="ask(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-bar">
          <input
            v-model="question"
            :placeholder="inputPlaceholder"
            @keyup.enter="ask()"
            @focus="showQuickQuestions = false"
          />
          <button class="send-btn" :disabled="asking || !question.trim()" @click="ask()">
            发送
          </button>
        </div>
      </div>
    </transition>

    <!-- 告别弹窗 -->
    <transition name="farewell-fade">
      <div v-if="showFarewell" class="farewell-overlay" @click="confirmLeave">
        <div class="farewell-card" @click.stop>
          <div class="farewell-avatar">{{ currentMaster?.avatar }}</div>
          <div class="farewell-text">{{ farewellMessage }}</div>
          <button class="farewell-btn" @click="confirmLeave">下次再来</button>
        </div>
      </div>
    </transition>

    <!-- 注册/登录弹窗 -->
    <transition name="farewell-fade">
      <div v-if="showAuth" class="farewell-overlay">
        <div class="register-card" @click.stop>
          <div class="register-title">{{ authMode === 'login' ? '欢迎回来' : '拜师之前' }}</div>
          <div class="register-subtitle">{{ authMode === 'login' ? '大师在等你' : '大师想知道怎么称呼你' }}</div>
          <input
            v-model="authNickname"
            class="register-input"
            placeholder="请输入你的名字..."
            maxlength="20"
          />
          <input
            v-model="authPassword"
            class="register-input"
            type="password"
            placeholder="请输入密码（至少4位）..."
            minlength="4"
            @keyup.enter="doAuth"
          />
          <div v-if="authError" class="auth-error">{{ authError }}</div>
          <button class="register-btn" @click="doAuth" :disabled="!authNickname.trim() || authPassword.length < 4">
            {{ authMode === 'login' ? '登 录' : '拜见大师' }}
          </button>
          <div class="auth-switch">
            <span v-if="authMode === 'login'">还没有账号？</span>
            <span v-else>已有账号？</span>
            <a href="#" @click.prevent="authMode = authMode === 'login' ? 'register' : 'login'; authError = ''">
              {{ authMode === 'login' ? '立即注册' : '去登录' }}
            </a>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { api, userAuth, http } from '../api.js'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'

const question = ref('')
const messages = ref([])
const asking = ref(false)
const masters = ref([])
const currentMaster = ref(null)
const enteredMaster = ref(false)
const showQuickQuestions = ref(true)
const showFarewell = ref(false)
const chatArea = ref(null)

// 用户系统
const showAuth = ref(false)
const authMode = ref('login')  // 'login' or 'register'
const authNickname = ref('')
const authPassword = ref('')
const authError = ref('')
const currentSessionId = ref('')
const showSidebar = ref(false)
const userProfile = ref(null)

// 历史对话
const historySidebarOpen = ref(false)
const sessions = ref([])

const userId = computed(() => userAuth.getUserId())
const nickname = computed(() => userAuth.getNickname())

const parseTags = (tags) => {
  if (!tags) return []
  try {
    const parsed = JSON.parse(tags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

// 历史会话管理
const sessionTitle = (session) => {
  if (session.topic_summary) return session.topic_summary
  if (session.first_msg) {
    const text = session.first_msg
    return text.length > 20 ? text.slice(0, 20) + '...' : text
  }
  return '新对话'
}

const formatSessionTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts + (ts.includes('Z') ? '' : 'Z'))
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}天前`
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const formatDateHeader = (dateStr) => {
  if (!dateStr) return '未知日期'
  // dateStr 格式: "2026-06-08"
  const parts = dateStr.split('-')
  if (parts.length === 3) {
    return `${parseInt(parts[0])}/${parseInt(parts[1])}/${parseInt(parts[2])}`
  }
  return dateStr
}

// 按日期分组的会话列表
const groupedSessions = computed(() => {
  const groups = []
  const dateMap = {}
  for (const s of sessions.value) {
    const date = s.talk_date || (s.started_at ? s.started_at.split('T')[0] : 'unknown')
    if (!dateMap[date]) {
      dateMap[date] = { date: formatDateHeader(date), sessions: [] }
      groups.push(dateMap[date])
    }
    dateMap[date].sessions.push(s)
  }
  return groups
})

const loadSessions = async () => {
  if (!userId.value || !currentMaster.value) return
  try {
    const data = await api.getUserSessions(userId.value, currentMaster.value.id, 20)
    sessions.value = data.sessions || []
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

const switchSession = async (session) => {
  if (session.id === currentSessionId.value) {
    historySidebarOpen.value = false
    return
  }
  // 切换到选中的会话
  currentSessionId.value = session.id
  messages.value = []
  showQuickQuestions.value = false
  // 加载该会话的消息
  try {
    const data = await api.getSessionMessages(session.id, 50)
    const msgs = data.messages || []
    messages.value = msgs.map(m => ({ role: m.role, text: m.content }))
  } catch (e) {
    console.error('加载会话消息失败', e)
  }
  historySidebarOpen.value = false
  scrollToBottom()
}

const startNewSession = async () => {
  // 开始新会话（按日模式下，同一天不会创建新的，除非手动新建）
  try {
    const session = await api.startSession(userId.value, currentMaster.value.id)
    currentSessionId.value = session.session_id
    messages.value = []
    showQuickQuestions.value = true
    await loadSessions()
    // 获取问候语
    let greeting = currentMaster.value.greeting || '来了？坐吧。想聊什么？'
    try {
      const greetData = await http.get(`/masters/${currentMaster.value.id}/greeting`, { params: { user_id: userId.value } }).then(r => r.data)
      greeting = greetData.greeting || greeting
    } catch (e) { /* use default */ }
    messages.value.push({ role: 'assistant', text: greeting })
    scrollToBottom()
  } catch (e) {
    console.error('新建会话失败', e)
  }
}

const deleteSession = async (session) => {
  try {
    await api.deleteSession(session.id)
  } catch (e) {
    console.error('删除会话失败', e)
  }
  // 从列表中移除
  sessions.value = sessions.value.filter(s => s.id !== session.id)
  // 如果删除的是当前会话，切换到其他会话或创建新的
  if (session.id === currentSessionId.value) {
    if (sessions.value.length > 0) {
      await switchSession(sessions.value[0])
    } else {
      await startNewSession()
    }
  }
}

const doAuth = async () => {
  const name = authNickname.value.trim()
  if (!name || authPassword.value.length < 4) return
  authError.value = ''
  try {
    let user
    if (authMode.value === 'login') {
      user = await api.userLogin(name, authPassword.value)
    } else {
      user = await api.userRegister(name, authPassword.value)
    }
    userAuth.save(user.id, user.nickname)
    showAuth.value = false
    authNickname.value = ''
    authPassword.value = ''
  } catch (e) {
    authError.value = e.response?.data?.error || (authMode.value === 'login' ? '登录失败' : '注册失败')
  }
}

// 打字时显示大师的动作
const typingTexts = {
  chagongfu: ['拿起砂铫', '注了点水', '闻了闻茶香', '轻轻点头'],
  wushishizi: ['扎了个马步', '敲了敲鼓', '比划了两下', '嘿了一声'],
}
const typingText = ref('')
let typingInterval = null

const startTypingAnimation = (masterId) => {
  const texts = typingTexts[masterId] || ['想了想']
  let idx = 0
  typingText.value = texts[0]
  typingInterval = setInterval(() => {
    idx = (idx + 1) % texts.length
    typingText.value = texts[idx]
  }, 2000)
}

const stopTypingAnimation = () => {
  if (typingInterval) {
    clearInterval(typingInterval)
    typingInterval = null
  }
}

// 告别语
const farewellMessages = {
  chagongfu: [
    '慢走啊。改天再来茶室，我泡壶好茶等你。',
    '走了？下次来我给你泡一泡老丛，保证你喝了忘不了。',
    '去吧去吧。茶这东西，得慢慢品。下次再来。',
  ],
  wushishizi: [
    '走好！下次来武馆，我教你扎马步。',
    '慢走啊。醒狮这东西，得自己上手才知道门道。下次来试试。',
    '去吧。记住，老祖宗的东西，不能丢。',
  ],
}
const farewellMessage = ref('')

const quickQuestions = computed(() => {
  if (!currentMaster.value) return []
  const id = currentMaster.value.id
  if (id === 'chagongfu') {
    return [
      '潮州工夫茶和其他茶艺有什么区别？',
      '凤凰单丛的鸭屎香是什么味道？',
      '您祖父是怎么教您学茶的？',
      '泡茶最讲究的是什么？',
    ]
  }
  if (id === 'wushishizi') {
    return [
      '醒狮和舞狮有什么区别？',
      '采青是怎么回事？',
      '您父亲是怎么教您学狮的？',
      '不同颜色的狮头代表什么？',
    ]
  }
  return []
})

const inputPlaceholder = computed(() => {
  if (!currentMaster.value) return '输入你的问题...'
  const name = currentMaster.value.name
  const tips = {
    chagongfu: '问问工夫茶、凤凰单丛、冲泡...',
    wushishizi: '问问醒狮、采青、步法...',
  }
  return `向${name}提问 · ${tips[currentMaster.value.id] || '想聊什么就说什么'}`
})

onMounted(async () => {
  try {
    const data = await api.getMasters()
    masters.value = data.masters || []
  } catch (e) {
    console.error('加载大师列表失败', e)
  }
})

const enterMaster = async (m) => {
  // 检查用户是否已登录
  if (!userAuth.isLoggedIn()) {
    showAuth.value = true
    return
  }

  currentMaster.value = m
  enteredMaster.value = true
  messages.value = []
  showQuickQuestions.value = true

  // 加载用户画像（用于侧边栏）
  try {
    const profileData = await api.getUserProfile(userId.value, m.id)
    userProfile.value = profileData
  } catch (e) {
    userProfile.value = null
  }

  // 加载历史会话列表
  await loadSessions()

  // 获取或创建今天的会话（后端按日复用）
  try {
    const session = await api.startSession(userId.value, m.id)
    currentSessionId.value = session.session_id
    await loadSessions()

    // 加载该会话的消息
    const data = await api.getSessionMessages(session.session_id, 50)
    const msgs = data.messages || []
    if (msgs.length > 0) {
      // 今天已有对话，恢复消息
      messages.value = msgs.map(msg => ({ role: msg.role, text: msg.content }))
      showQuickQuestions.value = false
      scrollToBottom()
      return
    }
  } catch (e) {
    console.error('开始会话失败', e)
  }

  // 今天第一次对话 — 获取每日功课问候语
  let greeting = m.greeting || '来了？坐吧。想聊什么？'
  try {
    const greetData = await http.get(`/masters/${m.id}/greeting`, { params: { user_id: userId.value } }).then(r => r.data)
    greeting = greetData.greeting || greeting
  } catch (e) {
    // 使用默认问候语
  }

  // 大师开场白
  messages.value.push({
    role: 'assistant',
    text: greeting,
  })
}

const leaveMaster = () => {
  // 显示告别弹窗
  const id = currentMaster.value?.id
  const msgs = farewellMessages[id] || ['下次再来。']
  farewellMessage.value = msgs[Math.floor(Math.random() * msgs.length)]
  showFarewell.value = true
}

const confirmLeave = async () => {
  showFarewell.value = false
  enteredMaster.value = false
  currentMaster.value = null
  messages.value = []
  question.value = ''
  sessions.value = []
  historySidebarOpen.value = false
  stopTypingAnimation()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatArea.value) {
      chatArea.value.scrollTop = chatArea.value.scrollHeight
    }
  })
}

const ask = async (q) => {
  const text = q || question.value.trim()
  if (!text || !currentMaster.value) return
  question.value = ''
  showQuickQuestions.value = false

  messages.value.push({ role: 'user', text })
  asking.value = true
  startTypingAnimation(currentMaster.value.id)
  scrollToBottom()

  try {
    const data = await api.ask(text, currentMaster.value.id, userId.value, currentSessionId.value)
    messages.value.push({
      role: 'assistant',
      text: data.answer || '……（沉默了一会儿）这个我得想想。',
    })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      text: '哎呀，我这脑子一时没转过来。你再说一遍？',
    })
  } finally {
    asking.value = false
    stopTypingAnimation()
    scrollToBottom()
  }
}
</script>

<style scoped>
/* ====== 入口：选择大师 ====== */
.entrance {
  min-height: 70vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.entrance-header {
  text-align: center;
  margin-bottom: 40px;
}

.entrance-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.entrance-subtitle {
  color: var(--text-light);
  font-size: 15px;
}

.master-gates {
  display: flex;
  gap: 24px;
  justify-content: center;
  flex-wrap: wrap;
}

.gate-card {
  width: 300px;
  border: 2px solid #e0d6cc;
  border-radius: 16px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  background: #fff;
}

.gate-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.12);
  border-color: var(--primary);
}

.gate-scene {
  padding: 32px 24px 20px;
  text-align: center;
  background: linear-gradient(180deg, #f8f0e6 0%, #fff 100%);
}

.gate-avatar {
  font-size: 56px;
  margin-bottom: 12px;
}

.gate-name {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 4px;
}

.gate-title {
  font-size: 14px;
  color: var(--primary);
  font-weight: 500;
}

.gate-door {
  padding: 0 24px;
}

.door-frame {
  border: 2px dashed #d0c4b8;
  border-radius: 10px;
  padding: 14px;
  text-align: center;
  transition: all 0.2s;
}

.gate-card:hover .door-frame {
  border-color: var(--primary);
  border-style: solid;
  background: rgba(184, 56, 59, 0.04);
}

.door-text {
  font-size: 14px;
  color: var(--text-light);
  font-weight: 500;
}

.gate-card:hover .door-text {
  color: var(--primary);
}

.gate-scene-text {
  padding: 16px 24px 24px;
  font-size: 13px;
  color: var(--text-light);
  line-height: 1.7;
}

/* ====== 工作室：对话界面 ====== */
.studio {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  min-height: 500px;
  position: relative;
  overflow: hidden;
}

.back-btn {
  align-self: flex-start;
  background: none;
  border: none;
  color: var(--text-light);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 0;
  margin-bottom: 8px;
  transition: color 0.2s;
}

.back-btn:hover {
  color: var(--primary);
}

/* 顶栏 */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  margin-bottom: 8px;
}

.sidebar-toggle {
  background: none;
  border: 1px solid #e0d6cc;
  border-radius: 16px;
  color: var(--text-light);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.sidebar-toggle:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.top-bar-right {
  display: flex;
  gap: 8px;
  align-items: center;
}

.new-conversation-btn {
  background: none;
  border: 1px solid var(--primary);
  border-radius: 16px;
  color: var(--primary);
  font-size: 12px;
  padding: 4px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-conversation-btn:hover {
  background: var(--primary);
  color: #fff;
}

/* 历史对话侧边栏 */
.history-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  width: 240px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #eee;
  z-index: 10;
  display: flex;
  flex-direction: column;
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.06);
  border-radius: 12px 0 0 12px;
}

.history-header {
  padding: 16px;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 1px solid #eee;
  color: var(--text);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.history-item {
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
  position: relative;
}

.history-delete {
  display: none;
  position: absolute;
  right: 8px;
  top: 8px;
  background: none;
  border: none;
  color: #999;
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1;
}

.history-item:hover .history-delete {
  display: block;
}

.history-delete:hover {
  background: #fee;
  color: #e74c3c;
}

.history-item:hover {
  background: #f5f0eb;
}

.history-item.active {
  background: #f0e8da;
  border-left: 3px solid var(--primary);
}

.history-title {
  font-size: 13px;
  color: var(--text);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-light);
}

.history-date-header {
  padding: 10px 16px 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  border-bottom: 1px solid #f0e8df;
  background: #faf6f1;
  position: sticky;
  top: 0;
  z-index: 1;
}

.history-empty {
  text-align: center;
  padding: 24px 16px;
  color: var(--text-light);
  font-size: 13px;
}

.sidebar-slide-left-enter-active {
  transition: transform 0.3s ease;
}

.sidebar-slide-left-leave-active {
  transition: transform 0.2s ease;
}

.sidebar-slide-left-enter-from,
.sidebar-slide-left-leave-to {
  transform: translateX(-100%);
}

/* 侧边栏 */
.sidebar {
  position: absolute;
  right: 0;
  top: 0;
  width: 220px;
  height: 100%;
  background: #fff;
  border-left: 1px solid #eee;
  padding: 16px;
  z-index: 10;
  overflow-y: auto;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.06);
  border-radius: 0 12px 12px 0;
}

.sidebar-section {
  margin-bottom: 16px;
}

.sidebar-label {
  font-size: 11px;
  color: var(--text-light);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.sidebar-stage {
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
}

.sidebar-value {
  font-size: 16px;
  font-weight: 600;
}

.sidebar-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sidebar-tag {
  padding: 2px 8px;
  background: #f5f0eb;
  border-radius: 10px;
  font-size: 11px;
  color: #666;
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.sidebar-link {
  display: block;
  padding: 8px 12px;
  background: #f8f5f0;
  border-radius: 8px;
  color: var(--text);
  text-decoration: none;
  font-size: 13px;
  transition: background 0.2s;
}

.sidebar-link:hover {
  background: #f0ebe5;
}

.sidebar-slide-enter-active {
  transition: transform 0.3s ease;
}

.sidebar-slide-leave-active {
  transition: transform 0.2s ease;
}

.sidebar-slide-enter-from,
.sidebar-slide-leave-to {
  transform: translateX(100%);
}

/* 场景描述栏 */
.scene-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f8f0e6 0%, #f0e8da 100%);
  border-radius: 12px;
  margin-bottom: 16px;
}

.scene-icon {
  font-size: 24px;
  flex-shrink: 0;
  margin-top: 2px;
}

.scene-text {
  font-size: 13px;
  color: #7a6e62;
  line-height: 1.7;
  font-style: italic;
}

/* 聊天区 */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
  margin-bottom: 12px;
}

.chat-msg {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  align-items: flex-start;
}

.chat-msg.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  font-size: 28px;
  flex-shrink: 0;
  width: 36px;
  text-align: center;
}

.msg-bubble {
  max-width: 75%;
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.7;
  font-size: 15px;
}

.chat-msg.assistant .msg-bubble {
  background: #fff;
  border: 1px solid #e8e0d8;
  border-top-left-radius: 4px;
}

.chat-msg.user .msg-bubble {
  background: var(--primary);
  color: #fff;
  border-top-right-radius: 4px;
}

.chat-msg.user .msg-bubble :deep(a) {
  color: #ffd;
}

/* 消息入场动画 */
.msg-enter {
  animation: msgSlideIn 0.3s ease-out;
}

@keyframes msgSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 打字动画 */
.typing {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
}

.typing-text {
  font-size: 13px;
  color: #b8a898;
  font-style: italic;
  margin-right: 4px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #b8a898;
  animation: typingBounce 1.4s infinite ease-in-out;
}

.typing-dot:nth-child(2) { animation-delay: 0s; }
.typing-dot:nth-child(3) { animation-delay: 0.2s; }
.typing-dot:nth-child(4) { animation-delay: 0.4s; }

@keyframes typingBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* 工作室过渡 */
.studio-fade-enter-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}

.studio-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

/* 告别弹窗 */
.farewell-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.farewell-card {
  background: #fff;
  border-radius: 20px;
  padding: 40px 36px 32px;
  text-align: center;
  max-width: 360px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.farewell-avatar {
  font-size: 48px;
  margin-bottom: 16px;
}

.farewell-text {
  font-size: 16px;
  line-height: 1.8;
  color: var(--text);
  margin-bottom: 24px;
}

.farewell-btn {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 24px;
  padding: 12px 32px;
  font-size: 15px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.farewell-btn:hover {
  opacity: 0.9;
}

.farewell-fade-enter-active {
  transition: opacity 0.3s ease;
}

.farewell-fade-leave-active {
  transition: opacity 0.2s ease;
}

.farewell-fade-enter-from,
.farewell-fade-leave-to {
  opacity: 0;
}

/* 注册弹窗 */
.register-card {
  background: #fff;
  border-radius: 20px;
  padding: 40px 36px 32px;
  text-align: center;
  max-width: 380px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.register-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.register-subtitle {
  font-size: 14px;
  color: var(--text-light);
  margin-bottom: 24px;
}

.register-input {
  width: 100%;
  padding: 14px 18px;
  border: 2px solid #e0d5ca;
  border-radius: 12px;
  font-size: 16px;
  text-align: center;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.register-input:focus {
  border-color: var(--primary);
}

.register-btn {
  margin-top: 20px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 24px;
  padding: 14px 36px;
  font-size: 16px;
  cursor: pointer;
  transition: opacity 0.2s;
  letter-spacing: 2px;
}

.register-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.register-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.auth-error {
  color: #e74c3c;
  font-size: 13px;
  text-align: center;
  margin-top: 8px;
}

.auth-switch {
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
  color: #999;
}

.auth-switch a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 500;
}

.auth-switch a:hover {
  text-decoration: underline;
}

.farewell-fade-enter-from .farewell-card {
  transform: scale(0.9);
  transition: transform 0.3s ease;
}

/* 快捷问题 */
.quick-section {
  margin-bottom: 12px;
}

.quick-label {
  font-size: 13px;
  color: var(--text-light);
  margin-bottom: 8px;
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.quick-btn {
  background: #fff;
  border: 1px solid #e0d6cc;
  border-radius: 20px;
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s;
}

.quick-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: rgba(184, 56, 59, 0.04);
}

/* 输入框 */
.input-bar {
  display: flex;
  gap: 8px;
  padding: 12px 0;
  border-top: 1px solid #e8e0d8;
}

.input-bar input {
  flex: 1;
  border: 1px solid #e0d6cc;
  border-radius: 24px;
  padding: 12px 20px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

.input-bar input:focus {
  border-color: var(--primary);
}

.send-btn {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 24px;
  padding: 12px 24px;
  font-size: 15px;
  cursor: pointer;
  transition: opacity 0.2s;
  white-space: nowrap;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 移动端适配 */
@media (max-width: 640px) {
  .master-gates {
    flex-direction: column;
    align-items: center;
  }

  .gate-card {
    width: 100%;
    max-width: 340px;
  }

  .msg-bubble {
    max-width: 85%;
  }
}
</style>
