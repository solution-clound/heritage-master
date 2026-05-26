<template>
  <div class="detail-view">
    <router-link to="/explore" class="back-link">&larr; 返回探索</router-link>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!project.name" class="empty">未找到该项目</div>
    <div v-else>
      <!-- 基本信息 -->
      <div class="card header-card">
        <h1>
          {{ project.name }}
          <span v-if="project.unesco" class="unesco-badge">UNESCO</span>
        </h1>
        <div class="meta-row">
          <span v-if="project.category" class="tag">{{ project.category }}</span>
          <span v-if="project.batch" class="tag">{{ project.batch }}</span>
          <span v-if="project.level" class="tag">{{ project.level }}</span>
        </div>
        <div v-if="project.region" class="region">流传地区：{{ project.region }}</div>
        <div v-if="project.unesco_year" class="region">
          UNESCO 入选年份：{{ project.unesco_year }}
        </div>
      </div>

      <!-- 知识标签 -->
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          :class="['tab-btn', { active: activeTab === tab.key }]"
          @click="loadKnowledge(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 内容区 -->
      <div class="card content-card">
        <div v-if="knowledgeLoading" class="loading">加载中...</div>
        <MarkdownRenderer v-else :content="knowledgeContent" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'

const route = useRoute()
const project = ref({})
const loading = ref(true)
const activeTab = ref('overview')
const knowledgeContent = ref('')
const knowledgeLoading = ref(false)

const tabs = [
  { key: 'overview', label: '概述' },
  { key: 'history', label: '历史渊源' },
  { key: 'technique', label: '技艺特点' },
  { key: 'inheritors', label: '传承人' },
  { key: 'works', label: '代表作品' },
]

const loadProject = async () => {
  loading.value = true
  try {
    const data = await api.getProject(route.params.name)
    project.value = data.project || {}
    // 默认显示描述
    knowledgeContent.value = buildDefaultContent()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const buildDefaultContent = () => {
  const p = project.value
  const parts = []
  if (p.description) parts.push(p.description)
  if (p.summary) parts.push(p.summary)
  if (p.content) parts.push(p.content)
  return parts.join('\n\n') || '暂无详细描述。'
}

const loadKnowledge = async (aspect) => {
  activeTab.value = aspect
  if (aspect === 'overview') {
    knowledgeContent.value = buildDefaultContent()
    return
  }
  knowledgeLoading.value = true
  try {
    const data = await api.getKnowledge({ name: route.params.name, aspect })
    knowledgeContent.value = data.content || '暂无相关信息。'
  } catch (e) {
    knowledgeContent.value = '加载失败。'
  } finally {
    knowledgeLoading.value = false
  }
}

onMounted(loadProject)
watch(() => route.params.name, loadProject)
</script>

<style scoped>
.back-link {
  display: inline-block;
  margin-bottom: 16px;
  font-size: 14px;
}

.header-card h1 {
  font-size: 26px;
  margin-bottom: 12px;
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.unesco-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: #d4a843;
  color: #fff;
  border-radius: 4px;
  font-weight: 700;
  vertical-align: middle;
}

.region {
  font-size: 14px;
  color: var(--text-light);
  margin-top: 4px;
}

.tabs {
  display: flex;
  gap: 4px;
  margin: 16px 0;
  overflow-x: auto;
}

.tab-btn {
  padding: 8px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.tab-btn.active,
.tab-btn:hover {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.content-card {
  min-height: 200px;
}
</style>
