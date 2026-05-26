<template>
  <div class="cultivation-map">
    <div class="map-header">
      <h1>修行地图</h1>
      <p class="map-subtitle">你的文化修行之路</p>
    </div>

    <!-- 大师选择 -->
    <div class="master-selector">
      <button
        v-for="m in masters"
        :key="m.id"
        :class="['master-btn', { active: selectedMaster === m.id }]"
        @click="selectMaster(m.id)"
      >
        {{ m.avatar }} {{ m.name }}
      </button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-if="!loading && cultivationData" class="map-content">
      <!-- 当前阶段卡片 -->
      <div class="current-stage-card">
        <div class="stage-icon">{{ stageIcons[currentStage] || '🌱' }}</div>
        <div class="stage-info">
          <div class="stage-name">{{ currentStage }}</div>
          <div class="stage-desc">{{ stageDescriptions[currentStage] || '' }}</div>
        </div>
        <div class="stage-stats">
          <div class="stat">
            <span class="stat-value">{{ totalPracticeDays }}</span>
            <span class="stat-label">练习天数</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ totalQuestions }}</span>
            <span class="stat-label">提问次数</span>
          </div>
        </div>
      </div>

      <!-- 修行路径 -->
      <div class="path-container">
        <div class="path-line"></div>
        <div
          v-for="(stage, i) in stages"
          :key="stage"
          :class="['path-node', { completed: isCompleted(stage), current: isCurrent(stage), locked: isLocked(stage) }]"
        >
          <div class="node-marker">
            <span v-if="isCompleted(stage)" class="stamp">✓</span>
            <span v-else-if="isCurrent(stage)" class="pulse"></span>
            <span v-else class="lock">🔒</span>
          </div>
          <div class="node-content">
            <div class="node-title">{{ stageIcons[stage] }} {{ stage }}</div>
            <div class="node-desc">{{ stageDescriptions[stage] }}</div>
            <div v-if="isCurrent(stage) && nextStage" class="node-progress">
              <div class="progress-label">距离下一阶段</div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
              </div>
              <div class="progress-hint">{{ progressHint }}</div>
            </div>
            <div v-if="isCompleted(stage)" class="node-badge">已通关</div>
          </div>
        </div>
      </div>

      <!-- 阶段转换提示 -->
      <div v-if="canTransition" class="transition-card">
        <div class="transition-icon">🎊</div>
        <div class="transition-text">
          <div class="transition-title">恭喜！你已满足晋级条件</div>
          <div class="transition-desc">可以进入「{{ nextStage }}」阶段</div>
        </div>
        <button class="transition-btn" @click="doTransition">接受晋级</button>
      </div>
    </div>

    <!-- 未注册提示 -->
    <div v-if="!loading && !isLoggedIn" class="login-hint">
      <p>请先注册并登录，开始你的修行之旅</p>
      <router-link to="/knowledge" class="login-link">前往拜师</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, userAuth } from '../api.js'

const masters = ref([])
const selectedMaster = ref('')
const cultivationData = ref(null)
const loading = ref(false)

const isLoggedIn = computed(() => userAuth.isLoggedIn())
const userId = computed(() => userAuth.getUserId())

const stages = ['入门期', '成长期', '精进期', '传承期']

const stageIcons = {
  '入门期': '🌱',
  '成长期': '🌿',
  '精进期': '🌳',
  '传承期': '🏮',
}

const stageDescriptions = {
  '入门期': '初识非遗，好奇心驱动',
  '成长期': '开始深入，建立兴趣方向',
  '精进期': '专注修炼，技艺日进',
  '传承期': '融会贯通，薪火相传',
}

const currentStage = computed(() => cultivationData.value?.stage || '')
const totalPracticeDays = computed(() => cultivationData.value?.transition?.progress?.practice_days || 0)
const totalQuestions = computed(() => cultivationData.value?.transition?.progress?.questions || 0)
const canTransition = computed(() => cultivationData.value?.transition?.can_transition || false)
const nextStage = computed(() => cultivationData.value?.transition?.next_stage || '')

const stageIndex = computed(() => {
  if (!currentStage.value) return -1
  return stages.indexOf(currentStage.value)
})

const isCompleted = (stage) => {
  const idx = stages.indexOf(stage)
  return idx < stageIndex.value
}

const isCurrent = (stage) => stage === currentStage.value

const isLocked = (stage) => {
  const idx = stages.indexOf(stage)
  return idx > stageIndex.value
}

const progressPercent = computed(() => {
  if (!cultivationData.value) return 0
  const p = cultivationData.value.transition?.progress
  if (!p) return 0
  const dayPct = p.required_days ? Math.min(p.practice_days / p.required_days, 1) * 50 : 50
  const qPct = p.required_questions ? Math.min(p.questions / p.required_questions, 1) * 50 : 50
  return Math.round(dayPct + qPct)
})

const progressHint = computed(() => {
  if (!cultivationData.value) return ''
  const p = cultivationData.value.transition?.progress
  if (!p) return ''
  const needDays = Math.max(0, (p.required_days || 0) - (p.practice_days || 0))
  const needQ = Math.max(0, (p.required_questions || 0) - (p.questions || 0))
  const parts = []
  if (needDays > 0) parts.push(`还需${needDays}天练习`)
  if (needQ > 0) parts.push(`还需${needQ}次提问`)
  return parts.length ? parts.join('，') : '已满足条件'
})

const selectMaster = async (masterId) => {
  selectedMaster.value = masterId
  await loadCultivationData()
}

const loadCultivationData = async () => {
  if (!userId.value || !selectedMaster.value) return
  loading.value = true
  try {
    const data = await api.getCultivationStage(userId.value, selectedMaster.value)
    cultivationData.value = data
  } catch (e) {
    console.error('Load cultivation data failed', e)
    cultivationData.value = null
  } finally {
    loading.value = false
  }
}

const doTransition = async () => {
  if (!userId.value || !selectedMaster.value) return
  try {
    await api.doStageTransition(userId.value, selectedMaster.value)
    await loadCultivationData()
  } catch (e) {
    console.error('Stage transition failed', e)
  }
}

onMounted(async () => {
  try {
    const data = await api.getMasters()
    masters.value = data.masters || []
    if (masters.value.length > 0) {
      selectedMaster.value = masters.value[0].id
      if (isLoggedIn.value) {
        await loadCultivationData()
      }
    }
  } catch (e) {
    console.error('Load masters failed', e)
  }
})
</script>

<style scoped>
.cultivation-map {
  max-width: 700px;
  margin: 0 auto;
  padding: 20px;
}

.map-header {
  text-align: center;
  margin-bottom: 24px;
}

.map-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.map-subtitle {
  color: var(--text-light);
  font-size: 14px;
}

/* 大师选择 */
.master-selector {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 28px;
  flex-wrap: wrap;
}

.master-btn {
  padding: 10px 20px;
  border: 2px solid #e0d6cc;
  border-radius: 24px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.master-btn.active {
  border-color: var(--primary);
  background: rgba(184, 56, 59, 0.06);
  color: var(--primary);
  font-weight: 600;
}

/* 当前阶段卡片 */
.current-stage-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: linear-gradient(135deg, #f8f0e6 0%, #fff 100%);
  border-radius: 16px;
  border: 1px solid #e8ddd0;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.stage-icon {
  font-size: 48px;
  flex-shrink: 0;
}

.stage-info {
  flex: 1;
  min-width: 120px;
}

.stage-name {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 4px;
}

.stage-desc {
  font-size: 13px;
  color: var(--text-light);
}

.stage-stats {
  display: flex;
  gap: 20px;
}

.stat {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-light);
}

/* 修行路径 */
.path-container {
  position: relative;
  padding-left: 40px;
  margin-bottom: 32px;
}

.path-line {
  position: absolute;
  left: 19px;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--primary) 0%, #e0d6cc 100%);
  border-radius: 2px;
}

.path-node {
  position: relative;
  margin-bottom: 32px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.path-node:last-child {
  margin-bottom: 0;
}

.node-marker {
  position: absolute;
  left: -40px;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: 1;
}

.path-node.completed .node-marker {
  background: var(--primary);
  box-shadow: 0 2px 8px rgba(184, 56, 59, 0.3);
}

.path-node.current .node-marker {
  background: #fff;
  border: 3px solid var(--primary);
  box-shadow: 0 2px 12px rgba(184, 56, 59, 0.2);
}

.path-node.locked .node-marker {
  background: #f0ece8;
  border: 2px solid #d5cec6;
}

.stamp {
  color: #fff;
  font-size: 18px;
  font-weight: 700;
}

.pulse {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--primary);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.6; }
}

.lock {
  font-size: 14px;
}

.node-content {
  flex: 1;
  padding: 16px 20px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eee;
  transition: all 0.2s;
}

.path-node.current .node-content {
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(184, 56, 59, 0.08);
}

.path-node.locked .node-content {
  opacity: 0.6;
}

.node-title {
  font-size: 17px;
  font-weight: 600;
  margin-bottom: 6px;
}

.node-desc {
  font-size: 13px;
  color: var(--text-light);
  margin-bottom: 8px;
}

.node-badge {
  display: inline-block;
  padding: 3px 10px;
  background: rgba(184, 56, 59, 0.08);
  color: var(--primary);
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

/* 进度条 */
.node-progress {
  margin-top: 10px;
}

.progress-label {
  font-size: 12px;
  color: var(--text-light);
  margin-bottom: 6px;
}

.progress-bar {
  height: 8px;
  background: #f0ece8;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary) 0%, #d4635a 100%);
  border-radius: 4px;
  transition: width 0.6s ease;
}

.progress-hint {
  font-size: 12px;
  color: var(--text-light);
}

/* 晋级卡片 */
.transition-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: linear-gradient(135deg, #fff8e1 0%, #fff3e0 100%);
  border-radius: 16px;
  border: 1px solid #ffe0b2;
  flex-wrap: wrap;
}

.transition-icon {
  font-size: 36px;
  flex-shrink: 0;
}

.transition-text {
  flex: 1;
  min-width: 160px;
}

.transition-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.transition-desc {
  font-size: 13px;
  color: var(--text-light);
}

.transition-btn {
  padding: 10px 24px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 24px;
  font-size: 14px;
  cursor: pointer;
  transition: opacity 0.2s;
  white-space: nowrap;
}

.transition-btn:hover {
  opacity: 0.9;
}

/* 登录提示 */
.login-hint {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-light);
}

.login-link {
  display: inline-block;
  margin-top: 16px;
  padding: 10px 24px;
  background: var(--primary);
  color: #fff;
  border-radius: 24px;
  text-decoration: none;
  font-size: 14px;
}

.loading {
  text-align: center;
  padding: 40px;
  color: var(--text-light);
}

@media (max-width: 640px) {
  .current-stage-card {
    flex-direction: column;
    text-align: center;
  }

  .stage-stats {
    justify-content: center;
  }

  .path-container {
    padding-left: 32px;
  }

  .node-marker {
    left: -32px;
    width: 30px;
    height: 30px;
  }
}
</style>
