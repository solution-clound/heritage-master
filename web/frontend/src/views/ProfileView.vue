<template>
  <div class="profile-view">
    <div class="profile-header">
      <h1>学徒档案</h1>
      <p class="profile-subtitle">你的非遗修行记录</p>
    </div>

    <div v-if="!isLoggedIn" class="login-hint">
      <p>请先注册并登录，查看你的修行档案</p>
      <router-link to="/knowledge" class="login-link">前往拜师</router-link>
    </div>

    <div v-else>
      <!-- 用户信息卡 -->
      <div class="user-card">
        <div class="user-avatar">{{ userNickname.charAt(0) }}</div>
        <div class="user-info">
          <div class="user-name">{{ userNickname }}</div>
          <div class="user-id">ID: {{ userId }}</div>
        </div>
      </div>

      <!-- 各大师修行状态 -->
      <div class="section-title">修行进度</div>
      <div class="masters-grid" v-if="profiles.length > 0">
        <div v-for="p in profiles" :key="p.master_id" class="master-card">
          <div class="master-card-header">
            <span class="master-avatar">{{ masterAvatar(p.master_id) }}</span>
            <span class="master-name">{{ masterName(p.master_id) }}</span>
          </div>
          <div class="master-stage">
            <span class="stage-badge">{{ p.relationship_stage || '试探期' }}</span>
          </div>
          <div class="master-tags" v-if="parseTags(p.interest_tags).length > 0">
            <span v-for="tag in parseTags(p.interest_tags)" :key="tag" class="tag">{{ tag }}</span>
          </div>
          <div class="master-meta">
            <span>提问 {{ p.question_count || 0 }} 次</span>
            <span v-if="p.last_talk_at">最后对话: {{ formatDate(p.last_talk_at) }}</span>
          </div>
          <div v-if="p.aesthetic_pref" class="master-pref">
            大师评语: {{ p.aesthetic_pref }}
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>你还没有拜访过任何大师</p>
        <router-link to="/knowledge" class="login-link">去拜师</router-link>
      </div>

      <!-- 修行阶段详情 -->
      <div class="section-title">阶段详情</div>
      <div class="stages-grid" v-if="stageProgress.length > 0">
        <div v-for="s in stageProgress" :key="s.master_id" class="stage-item">
          <div class="stage-master">{{ masterName(s.master_id) }}</div>
          <div class="stage-current">
            <span class="stage-icon">{{ stageIcons[s.stage] || '🌱' }}</span>
            {{ s.stage }}
          </div>
          <div class="stage-detail">
            练习 {{ s.total_practice_days }} 天 · 提问 {{ s.total_questions }} 次
          </div>
        </div>
      </div>

      <!-- 最近对话 -->
      <div class="section-title">最近对话</div>
      <div class="history-list" v-if="recentHistory.length > 0">
        <div v-for="h in recentHistory" :key="h.id" class="history-item">
          <div class="history-time">{{ formatDate(h.created_at) }}</div>
          <div class="history-content">{{ h.content }}</div>
          <div class="history-role">{{ h.role === 'user' ? '我' : '大师' }}</div>
        </div>
      </div>
      <div v-else class="empty-state">
        <p>暂无对话记录</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, userAuth } from '../api.js'

const isLoggedIn = computed(() => userAuth.isLoggedIn())
const userId = computed(() => userAuth.getUserId())
const userNickname = computed(() => userAuth.getNickname())

const profiles = ref([])
const stageProgress = ref([])
const recentHistory = ref([])
const mastersList = ref([])

const masterMap = computed(() => {
  const m = {}
  for (const master of mastersList.value) {
    m[master.id] = master
  }
  return m
})

const masterAvatar = (id) => masterMap.value[id]?.avatar || '🏛'
const masterName = (id) => masterMap.value[id]?.name || id

const stageIcons = {
  '入门期': '🌱',
  '成长期': '🌿',
  '精进期': '🌳',
  '传承期': '🏮',
}

const parseTags = (tags) => {
  if (!tags) return []
  try {
    const parsed = JSON.parse(tags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

const loadData = async () => {
  if (!userId.value) return
  try {
    // 加载用户画像
    const profileData = await api.getUserProfiles(userId.value)
    profiles.value = profileData.profiles || []

    // 加载修行阶段
    const stagePromises = profiles.value.map(p =>
      api.getCultivationStage(userId.value, p.master_id).catch(() => null)
    )
    const stageResults = await Promise.all(stagePromises)
    stageProgress.value = stageResults.filter(Boolean)

    // 加载最近对话（取第一个大师的）
    if (profiles.value.length > 0) {
      const historyData = await api.getUserHistory(userId.value, profiles.value[0].master_id, 10)
      recentHistory.value = historyData.messages || []
    }
  } catch (e) {
    console.error('Load profile data failed', e)
  }
}

onMounted(async () => {
  try {
    const data = await api.getMasters()
    mastersList.value = data.masters || []
  } catch (e) {
    console.error('Load masters failed', e)
  }
  await loadData()
})
</script>

<style scoped>
.profile-view {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.profile-header {
  text-align: center;
  margin-bottom: 28px;
}

.profile-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.profile-subtitle {
  color: var(--text-light);
  font-size: 14px;
}

/* 用户卡片 */
.user-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: linear-gradient(135deg, #f8f0e6 0%, #fff 100%);
  border-radius: 16px;
  border: 1px solid #e8ddd0;
  margin-bottom: 28px;
}

.user-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  flex-shrink: 0;
}

.user-name {
  font-size: 20px;
  font-weight: 700;
}

.user-id {
  font-size: 12px;
  color: var(--text-light);
  margin-top: 4px;
}

/* 通用 */
.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0ece8;
}

/* 大师卡片网格 */
.masters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}

.master-card {
  padding: 18px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eee;
  transition: box-shadow 0.2s;
}

.master-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
}

.master-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.master-avatar {
  font-size: 28px;
}

.master-name {
  font-size: 16px;
  font-weight: 600;
}

.master-stage {
  margin-bottom: 10px;
}

.stage-badge {
  display: inline-block;
  padding: 3px 12px;
  background: rgba(184, 56, 59, 0.08);
  color: var(--primary);
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.master-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.tag {
  padding: 2px 10px;
  background: #f5f5f5;
  border-radius: 10px;
  font-size: 11px;
  color: #666;
}

.master-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-light);
}

.master-pref {
  margin-top: 8px;
  font-size: 13px;
  color: #666;
  font-style: italic;
  padding-top: 8px;
  border-top: 1px solid #f5f5f5;
}

/* 阶段详情 */
.stages-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 28px;
}

.stage-item {
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eee;
  text-align: center;
}

.stage-master {
  font-size: 13px;
  color: var(--text-light);
  margin-bottom: 8px;
}

.stage-current {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 6px;
}

.stage-icon {
  font-size: 24px;
  vertical-align: middle;
  margin-right: 4px;
}

.stage-detail {
  font-size: 12px;
  color: var(--text-light);
}

/* 对话历史 */
.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 28px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
}

.history-time {
  font-size: 11px;
  color: var(--text-light);
  white-space: nowrap;
  min-width: 70px;
}

.history-content {
  flex: 1;
  font-size: 14px;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-role {
  font-size: 11px;
  color: var(--primary);
  white-space: nowrap;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--text-light);
  margin-bottom: 28px;
}

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

@media (max-width: 640px) {
  .masters-grid {
    grid-template-columns: 1fr;
  }

  .stages-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .history-content {
    white-space: normal;
  }
}
</style>
