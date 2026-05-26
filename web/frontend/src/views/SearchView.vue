<template>
  <div class="search-view">
    <h1>非遗搜索</h1>

    <!-- 筛选栏 -->
    <div class="filters card">
      <div class="filter-row">
        <input v-model="form.query" placeholder="关键词" @keyup.enter="doSearch" />
        <select v-model="form.category">
          <option value="">全部类别</option>
          <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
        </select>
        <input v-model="form.region" placeholder="地区，如 广东" @keyup.enter="doSearch" />
        <button class="btn" @click="doSearch">搜索</button>
      </div>
    </div>

    <!-- 结果 -->
    <div v-if="loading" class="loading">搜索中...</div>
    <div v-else-if="items.length === 0 && searched" class="empty">未找到匹配的非遗项目</div>

    <template v-else-if="items.length > 0">
      <!-- 非遗项目 -->
      <h2 class="section-title">非遗项目 ({{ items.length }})</h2>
      <div class="results">
        <router-link
          v-for="item in items"
          :key="item.name"
          :to="`/project/${item.name}`"
          class="result-card card"
        >
          <div class="result-header">
            <h3>{{ item.name }}</h3>
            <span v-if="item.unesco" class="unesco-badge">UNESCO</span>
            <span v-if="item.enriched" class="ai-badge">AI 增强</span>
          </div>
          <div class="result-meta">
            <span class="tag">{{ item.category }}</span>
            <span v-if="item.batch" class="tag">{{ item.batch }}</span>
            <span v-if="item.region" class="region">{{ item.region }}</span>
          </div>
          <p v-if="item.description" class="result-desc">{{ item.description.slice(0, 150) }}...</p>
        </router-link>
      </div>

      <!-- 相关活动 -->
      <template v-if="events.length > 0">
        <h2 class="section-title">相关活动 ({{ events.length }})</h2>
        <div class="events-grid">
          <div v-for="ev in events" :key="ev.title" class="event-card card">
            <div class="event-type-badge">{{ ev.event_type || '活动' }}</div>
            <h4 class="event-title">{{ ev.title }}</h4>
            <div class="event-meta">
              <span v-if="ev.date" class="event-date">{{ ev.date }}</span>
              <span class="event-source">来源：{{ ev.source }}</span>
            </div>
            <a
              v-if="ev.url"
              :href="ev.url"
              target="_blank"
              class="event-link"
            >查看详情</a>
            <span v-else class="event-no-link">暂无报名链接，请关注来源网站</span>
          </div>
        </div>
      </template>

      <!-- 路线建议 -->
      <div v-if="routeHint" class="route-hint card">
        <h3>路线规划建议</h3>
        <p>{{ routeHint.message }}</p>
        <div class="route-venues">
          <span v-for="v in routeHint.venues" :key="v" class="tag">{{ v }}</span>
        </div>
        <router-link :to="`/trip?city=${routeHint.city}`" class="btn">
          规划参观路线
        </router-link>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const categories = ref([])
const items = ref([])
const events = ref([])
const routeHint = ref(null)
const loading = ref(false)
const searched = ref(false)

const form = reactive({ query: '', category: '', region: '' })

const doSearch = async () => {
  loading.value = true
  searched.value = true
  events.value = []
  routeHint.value = null
  try {
    // 使用组合接口获取项目+活动+路线
    const data = await api.searchEnriched({
      query: form.query,
      category: form.category,
      region: form.region,
      limit: 20,
    })
    items.value = data.items || []
    events.value = data.events || []
    routeHint.value = data.route_hint || null
  } catch (e) {
    // 降级到普通搜索
    try {
      const data = await api.search({
        query: form.query,
        category: form.category,
        region: form.region,
        limit: 20,
      })
      items.value = data.items || []
    } catch (e2) {
      console.error(e2)
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const catData = await api.getCategories()
  categories.value = catData.categories || []

  // 从 URL 参数初始化
  if (route.query.q) form.query = route.query.q
  if (route.query.category) form.category = route.query.category
  if (route.query.region) form.region = route.query.region
  if (form.query || form.category || form.region) doSearch()
})

watch(() => route.query, (q) => {
  if (q.q !== undefined) form.query = q.q
  if (q.category !== undefined) form.category = q.category
  if (q.region !== undefined) form.region = q.region
  doSearch()
})
</script>

<style scoped>
.search-view h1 {
  font-size: 24px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 18px;
  margin: 24px 0 12px;
  color: var(--text);
  border-bottom: 2px solid var(--primary, #8b4513);
  padding-bottom: 6px;
}

.filter-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-row input,
.filter-row select {
  flex: 1;
  min-width: 140px;
}

.filter-row .btn {
  white-space: nowrap;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  display: block;
  text-decoration: none;
  color: var(--text);
  transition: transform 0.2s;
}

.result-card:hover {
  transform: translateY(-1px);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.result-header h3 {
  font-size: 16px;
}

.unesco-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: #d4a843;
  color: #fff;
  border-radius: 4px;
  font-weight: 700;
}

.ai-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: #4a9eff;
  color: #fff;
  border-radius: 4px;
  font-weight: 600;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}

.region {
  font-size: 13px;
  color: var(--text-light);
}

.result-desc {
  font-size: 13px;
  color: var(--text-light);
  margin: 0;
  line-height: 1.5;
}

/* 活动卡片 */
.events-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.event-card {
  padding: 14px;
  position: relative;
}

.event-type-badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  background: #e8f5e9;
  color: #2e7d32;
  border-radius: 12px;
  margin-bottom: 8px;
  font-weight: 600;
}

.event-title {
  font-size: 14px;
  margin: 0 0 8px;
  line-height: 1.4;
}

.event-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-light);
  margin-bottom: 8px;
}

.event-source {
  color: #999;
}

.event-link {
  font-size: 13px;
  color: var(--primary, #8b4513);
  text-decoration: none;
  font-weight: 600;
}

.event-link:hover {
  text-decoration: underline;
}

.event-no-link {
  font-size: 12px;
  color: #aaa;
  font-style: italic;
}

/* 路线建议 */
.route-hint {
  margin-top: 20px;
  padding: 16px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
}

.route-hint h3 {
  font-size: 16px;
  margin: 0 0 8px;
}

.route-hint p {
  font-size: 14px;
  margin: 0 0 10px;
}

.route-venues {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.route-hint .btn {
  display: inline-block;
  text-decoration: none;
}
</style>
