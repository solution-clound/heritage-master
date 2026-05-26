<template>
  <div class="home">
    <!-- Hero -->
    <section class="hero">
      <h1>探索中国非物质文化遗产</h1>
      <p>搜索、了解、体验千年文化瑰宝</p>
      <SearchBar placeholder="输入关键词，如 昆曲、刺绣、醒狮..." @search="goSearch" />
    </section>

    <!-- 快捷入口 -->
    <section class="shortcuts">
      <router-link to="/explore" class="shortcut-card">
        <span class="shortcut-icon">🧭</span>
        <span>非遗探索</span>
      </router-link>
      <router-link to="/knowledge" class="shortcut-card">
        <span class="shortcut-icon">❓</span>
        <span>大师问答</span>
      </router-link>
    </section>

    <!-- 十大类别 -->
    <section v-if="categories.length" class="categories">
      <h2>非遗十大类别</h2>
      <div class="cat-grid">
        <button
          v-for="cat in categories"
          :key="cat"
          class="cat-btn"
          @click="goCategory(cat)"
        >
          {{ cat }}
        </button>
      </div>
    </section>

    <!-- 热门项目 -->
    <section class="featured">
      <h2>热门非遗项目</h2>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else class="project-grid">
        <router-link
          v-for="item in featured"
          :key="item.name"
          :to="`/project/${item.name}`"
          class="project-card card"
        >
          <div class="project-card-header">
            <h3>{{ item.name }}</h3>
            <span v-if="item.unesco" class="unesco-badge">UNESCO</span>
          </div>
          <span class="tag">{{ item.category }}</span>
          <p>{{ item.description?.slice(0, 80) }}...</p>
        </router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'
import SearchBar from '../components/SearchBar.vue'

const router = useRouter()
const categories = ref([])
const featured = ref([])
const loading = ref(true)

const goSearch = (q) => router.push({ path: '/explore', query: { q } })
const goCategory = (cat) => router.push({ path: '/explore', query: { category: cat } })

onMounted(async () => {
  try {
    const [catData, searchData] = await Promise.all([
      api.getCategories(),
      api.search({ limit: 8 }),
    ])
    categories.value = catData.categories || []
    featured.value = searchData.items || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.hero {
  text-align: center;
  padding: 60px 0 40px;
}

.hero h1 {
  font-size: 32px;
  margin-bottom: 8px;
  color: var(--primary);
}

.hero p {
  color: var(--text-light);
  margin-bottom: 24px;
}

.hero .search-bar {
  max-width: 560px;
  margin: 0 auto;
}

.shortcuts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 40px;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}

.shortcut-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 24px 16px;
  background: var(--bg-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  color: var(--text);
  text-decoration: none;
  transition: transform 0.2s, box-shadow 0.2s;
}

.shortcut-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
}

.shortcut-icon {
  font-size: 32px;
}

.categories {
  margin-bottom: 40px;
}

.categories h2,
.featured h2 {
  font-size: 22px;
  margin-bottom: 16px;
  color: var(--text);
}

.cat-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.cat-btn {
  padding: 8px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.cat-btn:hover {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.project-card {
  text-decoration: none;
  color: var(--text);
  transition: transform 0.2s;
}

.project-card:hover {
  transform: translateY(-2px);
}

.project-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.project-card-header h3 {
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

.project-card p {
  font-size: 13px;
  color: var(--text-light);
  margin-top: 8px;
}

@media (max-width: 640px) {
  .hero h1 {
    font-size: 24px;
  }
  .shortcuts {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
