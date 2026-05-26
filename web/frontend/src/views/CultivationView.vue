<template>
  <div class="cultivation-view">
    <div class="cultivation-header">
      <h1>修行之路</h1>
      <p class="cultivation-subtitle">与大师同行，一步一步来</p>
    </div>

    <!-- 未登录提示 -->
    <div v-if="!isLoggedIn" class="login-hint">
      <p>请先拜访大师，开始你的修行之旅</p>
      <router-link to="/knowledge" class="login-btn">拜访大师</router-link>
    </div>

    <!-- 已登录：修行仪表盘 -->
    <div v-else class="cultivation-content">
      <!-- 选择大师 -->
      <div class="master-selector">
        <button
          v-for="m in masters"
          :key="m.id"
          :class="['master-tab', { active: selectedMaster === m.id }]"
          @click="selectMaster(m.id)"
        >
          {{ m.avatar }} {{ m.name }}
        </button>
      </div>

      <!-- 当前阶段卡片 -->
      <div class="stage-card" v-if="stageInfo">
        <div class="stage-badge" :class="stageClass">{{ stageInfo.stage }}</div>
        <div class="stage-description">{{ stageInfo.description }}</div>
        <div class="stage-progress" v-if="stageInfo.transition">
          <div class="progress-item">
            <span class="progress-label">练习天数</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: practiceProgress + '%' }"></div>
            </div>
            <span class="progress-value">{{ stageInfo.transition.progress.practice_days }}/{{ stageInfo.transition.progress.required_days }}</span>
          </div>
          <div class="progress-item">
            <span class="progress-label">提问次数</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: questionProgress + '%' }"></div>
            </div>
            <span class="progress-value">{{ stageInfo.transition.progress.questions }}/{{ stageInfo.transition.progress.required_questions }}</span>
          </div>
        </div>
        <button
          v-if="stageInfo.transition && stageInfo.transition.can_transition"
          class="transition-btn"
          @click="doTransition"
        >
          进入下一阶段
        </button>
      </div>

      <!-- 今日功课 -->
      <div class="practice-section">
        <h2>今日功课</h2>
        <div v-if="todayPractice" class="practice-card">
          <div class="practice-content">{{ todayPractice.content }}</div>
          <div class="practice-meta">大师为你安排的功课</div>
        </div>
        <button v-else class="assign-btn" @click="getPractice">获取今日功课</button>
      </div>

      <!-- 提交练习 -->
      <div class="submit-section">
        <h2>提交练习</h2>
        <textarea
          v-model="practiceContent"
          class="practice-textarea"
          placeholder="记录你的练习感悟..."
          rows="4"
        ></textarea>
        <button class="submit-btn" @click="submitPractice" :disabled="!practiceContent.trim()">
          提交，让大师点评
        </button>
      </div>

      <!-- 练习历史 -->
      <div class="history-section" v-if="practiceHistory.length > 0">
        <h2>练习记录</h2>
        <div class="history-list">
          <div v-for="record in practiceHistory" :key="record.id" class="history-card">
            <div class="history-date">{{ formatDate(record.created_at) }}</div>
            <div class="history-content">{{ record.content }}</div>
            <div v-if="record.master_comment" class="history-comment">
              <span class="comment-label">大师点评：</span>{{ record.master_comment }}
            </div>
            <div v-if="record.score > 0" class="history-score">
              <span class="score-label">评分：</span>{{ record.score }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { api, userAuth } from '../api.js'

const isLoggedIn = computed(() => userAuth.isLoggedIn())
const userId = computed(() => userAuth.getUserId())

const masters = ref([])
const selectedMaster = ref('')
const stageInfo = ref(null)
const todayPractice = ref(null)
const practiceContent = ref('')
const practiceHistory = ref([])

const stageClass = computed(() => {
  if (!stageInfo.value) return ''
  const stage = stageInfo.value.stage
  return {
    '入门期': 'stage-beginner',
    '成长期': 'stage-growing',
    '精进期': 'stage-advanced',
    '传承期': 'stage-master',
  }[stage] || ''
})

const practiceProgress = computed(() => {
  if (!stageInfo.value?.transition?.progress) return 0
  const p = stageInfo.value.transition.progress
  if (p.required_days === 0) return 100
  return Math.min(100, (p.practice_days / p.required_days) * 100)
})

const questionProgress = computed(() => {
  if (!stageInfo.value?.transition?.progress) return 0
  const p = stageInfo.value.transition.progress
  if (p.required_questions === 0) return 100
  return Math.min(100, (p.questions / p.required_questions) * 100)
})

onMounted(async () => {
  try {
    const data = await api.getMasters()
    masters.value = data.masters || []
    if (masters.value.length > 0) {
      selectedMaster.value = masters.value[0].id
    }
  } catch (e) {
    console.error('加载大师列表失败', e)
  }
})

watch(selectedMaster, async (masterId) => {
  if (!masterId || !userId.value) return
  await loadStageInfo(masterId)
  await loadPracticeHistory(masterId)
})

const selectMaster = (masterId) => {
  selectedMaster.value = masterId
  todayPractice.value = null
}

const loadStageInfo = async (masterId) => {
  try {
    stageInfo.value = await api.getCultivationStage(userId.value, masterId)
  } catch (e) {
    console.error('加载阶段信息失败', e)
  }
}

const loadPracticeHistory = async (masterId) => {
  try {
    const data = await api.getPracticeHistory(userId.value, masterId, 20)
    practiceHistory.value = data.history || []
  } catch (e) {
    console.error('加载练习历史失败', e)
  }
}

const getPractice = async () => {
  try {
    todayPractice.value = await api.assignPractice(userId.value, selectedMaster.value)
  } catch (e) {
    console.error('获取功课失败', e)
  }
}

const submitPractice = async () => {
  if (!practiceContent.value.trim()) return
  try {
    const result = await api.submitPractice(userId.value, selectedMaster.value, practiceContent.value)
    practiceContent.value = ''
    // 刷新历史
    await loadPracticeHistory(selectedMaster.value)
    await loadStageInfo(selectedMaster.value)
  } catch (e) {
    console.error('提交练习失败', e)
  }
}

const doTransition = async () => {
  try {
    const result = await api.doStageTransition(userId.value, selectedMaster.value)
    if (result.success) {
      alert(`恭喜！你已从${result.old_stage}进入${result.new_stage}`)
      await loadStageInfo(selectedMaster.value)
    }
  } catch (e) {
    console.error('阶段转换失败', e)
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
</script>

<style scoped>
.cultivation-view {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.cultivation-header {
  text-align: center;
  margin-bottom: 32px;
}

.cultivation-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.cultivation-subtitle {
  color: var(--text-light);
  font-size: 14px;
}

.login-hint {
  text-align: center;
  padding: 60px 20px;
}

.login-hint p {
  color: var(--text-light);
  margin-bottom: 20px;
}

.login-btn {
  display: inline-block;
  background: var(--primary);
  color: #fff;
  padding: 12px 32px;
  border-radius: 24px;
  text-decoration: none;
  transition: opacity 0.2s;
}

.login-btn:hover {
  opacity: 0.9;
}

/* 大师选择器 */
.master-selector {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.master-tab {
  padding: 10px 20px;
  border: 2px solid #e0d5ca;
  border-radius: 24px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.master-tab.active {
  border-color: var(--primary);
  background: rgba(184, 56, 59, 0.05);
  color: var(--primary);
}

/* 阶段卡片 */
.stage-card {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.stage-badge {
  display: inline-block;
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
}

.stage-beginner { background: #e8f5e9; color: #2e7d32; }
.stage-growing { background: #e3f2fd; color: #1565c0; }
.stage-advanced { background: #fff3e0; color: #e65100; }
.stage-master { background: #fce4ec; color: #c62828; }

.stage-description {
  color: var(--text-light);
  font-size: 14px;
  margin-bottom: 16px;
}

.stage-progress {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-label {
  font-size: 13px;
  color: var(--text-light);
  min-width: 70px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: #eee;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 4px;
  transition: width 0.3s;
}

.progress-value {
  font-size: 13px;
  color: var(--text-light);
  min-width: 50px;
  text-align: right;
}

.transition-btn {
  width: 100%;
  padding: 12px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.transition-btn:hover {
  opacity: 0.9;
}

/* 功课区域 */
.practice-section,
.submit-section,
.history-section {
  margin-bottom: 24px;
}

.practice-section h2,
.submit-section h2,
.history-section h2 {
  font-size: 18px;
  margin-bottom: 16px;
  padding-left: 12px;
  border-left: 4px solid var(--primary);
}

.practice-card {
  background: #f8f0e6;
  border-radius: 12px;
  padding: 20px;
}

.practice-content {
  font-size: 15px;
  line-height: 1.8;
  margin-bottom: 8px;
}

.practice-meta {
  font-size: 12px;
  color: var(--text-light);
}

.assign-btn {
  padding: 12px 24px;
  background: #f8f0e6;
  border: 2px dashed #d0c4b8;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  width: 100%;
}

.assign-btn:hover {
  border-color: var(--primary);
  background: rgba(184, 56, 59, 0.05);
}

/* 提交区域 */
.practice-textarea {
  width: 100%;
  padding: 16px;
  border: 2px solid #e0d5ca;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
  font-family: inherit;
}

.practice-textarea:focus {
  border-color: var(--primary);
}

.submit-btn {
  margin-top: 12px;
  padding: 12px 24px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.9;
}

/* 历史记录 */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.history-date {
  font-size: 12px;
  color: var(--text-light);
  margin-bottom: 8px;
}

.history-content {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.history-comment {
  font-size: 13px;
  color: var(--text-light);
  padding: 8px 12px;
  background: #f8f0e6;
  border-radius: 8px;
  margin-bottom: 4px;
}

.comment-label {
  font-weight: 600;
  color: var(--primary);
}

.history-score {
  font-size: 13px;
  color: var(--text-light);
}

.score-label {
  font-weight: 600;
}

@media (max-width: 640px) {
  .cultivation-view {
    padding: 16px;
  }

  .master-selector {
    gap: 8px;
  }

  .master-tab {
    padding: 8px 14px;
    font-size: 13px;
  }
}
</style>
