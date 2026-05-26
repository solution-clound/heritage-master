<template>
  <div class="trip-view">
    <h1>非遗旅行规划</h1>
    <p class="subtitle">选择城市和兴趣，规划非遗主题行程</p>

    <div class="card form-card">
      <div class="form-row">
        <div class="form-group">
          <label>城市</label>
          <input v-model="form.city" placeholder="如 广州、北京、成都" />
        </div>
        <div class="form-group">
          <label>天数</label>
          <select v-model.number="form.days">
            <option v-for="d in 7" :key="d" :value="d">{{ d }}天</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label>感兴趣的非遗类别（可多选）</label>
        <div class="interest-tags">
          <button
            v-for="cat in categories"
            :key="cat"
            :class="['tag-btn', { selected: form.interests.includes(cat) }]"
            @click="toggleInterest(cat)"
          >
            {{ cat }}
          </button>
        </div>
      </div>

      <button class="btn" :disabled="loading || !form.city.trim()" @click="planTrip">
        {{ loading ? '规划中...' : '生成行程' }}
      </button>
    </div>

    <!-- 结果 -->
    <div v-if="result" class="card result-card">
      <AmapView
        v-if="routeData"
        :venues="routeData.venues"
        :routeDays="routeData.days"
        height="340px"
        style="margin-bottom: 16px;"
      />
      <MarkdownRenderer :content="result" />
      <div class="save-trip-section">
        <button class="btn save-trip-btn" :disabled="tripSaved" @click="saveTrip">
          {{ tripSaved ? '已保存' : '保存路线' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api, userAuth } from '../api.js'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import AmapView from '../components/AmapView.vue'

const route = useRoute()
const categories = ref([])
const result = ref('')
const routeData = ref(null)
const loading = ref(false)
const tripSaved = ref(false)

const form = reactive({
  city: '',
  days: 2,
  interests: [],
})

const toggleInterest = (cat) => {
  const idx = form.interests.indexOf(cat)
  if (idx >= 0) form.interests.splice(idx, 1)
  else form.interests.push(cat)
}

const planTrip = async () => {
  if (!form.city.trim()) return
  loading.value = true
  result.value = ''
  routeData.value = null
  tripSaved.value = false
  try {
    const data = await api.planTrip({
      city: form.city.trim(),
      days: form.days,
      interests: form.interests,
    })
    result.value = data.result || '暂无规划结果。'
    routeData.value = data.route_data || null
  } catch (e) {
    result.value = '请求失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

const saveTrip = async () => {
  if (!userAuth.isLoggedIn()) {
    window.location.href = '/login'
    return
  }
  try {
    await api.saveTrip({
      user_id: userAuth.getUserId(),
      name: `${form.city} ${form.days}日游`,
      city: form.city.trim(),
      days: form.days,
      interests: form.interests,
      itinerary: result.value,
      route_data: routeData.value || {},
    })
    tripSaved.value = true
  } catch (e) {
    alert('保存失败')
  }
}

onMounted(async () => {
  const data = await api.getCategories()
  categories.value = data.categories || []

  // 从 URL 参数预填城市
  if (route.query.city) form.city = route.query.city
})
</script>

<style scoped>
.trip-view h1 {
  font-size: 24px;
  margin-bottom: 4px;
}

.subtitle {
  color: var(--text-light);
  margin-bottom: 20px;
}

.form-card {
  margin-bottom: 20px;
}

.form-row {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.form-group {
  flex: 1;
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}

.interest-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.tag-btn {
  padding: 6px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-btn.selected {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.tag-btn:hover {
  border-color: var(--primary);
}

.result-card {
  min-height: 200px;
}

.save-trip-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
  text-align: right;
}

.save-trip-btn:disabled {
  background: #aaa;
  cursor: default;
}
</style>
