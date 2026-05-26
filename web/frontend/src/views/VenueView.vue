<template>
  <div class="venue-view">
    <h1>非遗场馆查找</h1>

    <div class="filters card">
      <div class="filter-row">
        <input v-model="city" placeholder="城市名，如 广州、北京" @keyup.enter="doSearch" />
        <input v-model="keyword" placeholder="关键词，默认 非遗" @keyup.enter="doSearch" />
        <button class="btn" @click="doSearch">搜索</button>
      </div>
    </div>

    <div v-if="loading" class="loading">搜索中...</div>
    <div v-else-if="venues.length === 0 && searched" class="empty">
      未找到相关场馆，请尝试其他城市或关键词
    </div>
    <div v-else class="venue-grid">
      <div
        v-for="v in venues"
        :key="v.id || v.name"
        class="venue-card"
        @click="openDetail(v)"
      >
        <!-- 图片 -->
        <div class="venue-img">
          <img v-if="v.photos && v.photos.length" :src="v.photos[0]" :alt="v.name" />
          <img v-else-if="v.map_img" :src="v.map_img" :alt="v.name" />
          <div v-else class="venue-img-placeholder">
            <span>{{ getTypeEmoji(v.type) }}</span>
          </div>
          <span v-if="v.rating" class="rating-badge">{{ v.rating }}</span>
        </div>

        <!-- 信息 -->
        <div class="venue-body">
          <h3>{{ v.name }}</h3>
          <div class="venue-meta">
            <span v-if="v.type" class="type-tag">{{ formatType(v.type) }}</span>
          </div>
          <div v-if="v.address" class="venue-info">
            <span class="info-icon">📍</span>
            <span>{{ v.district }} {{ v.address }}</span>
          </div>
          <div v-if="v.tel" class="venue-info">
            <span class="info-icon">📞</span>
            <span>{{ v.tel }}</span>
          </div>
          <div v-if="v.business_hours" class="venue-info">
            <span class="info-icon">⏰</span>
            <span>{{ v.business_hours }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <Teleport to="body">
      <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
        <div class="modal">
          <button class="modal-close" @click="showDetail = false">&times;</button>

          <div v-if="detailLoading" class="loading">加载详情中...</div>
          <div v-else-if="detail" class="modal-content">
            <!-- 图片轮播 -->
            <div class="detail-images">
              <img
                v-if="detail.photos && detail.photos.length"
                :src="detail.photos[currentPhoto].url"
                :alt="detail.photos[currentPhoto].title || detail.name"
              />
              <img v-else-if="detail.map_img" :src="detail.map_img" :alt="detail.name" />
              <div v-else class="detail-img-placeholder">
                <span>{{ getTypeEmoji(detail.type) }}</span>
              </div>
              <!-- 图片导航 -->
              <div v-if="detail.photos && detail.photos.length > 1" class="photo-nav">
                <button @click="currentPhoto = (currentPhoto - 1 + detail.photos.length) % detail.photos.length">&lsaquo;</button>
                <span>{{ currentPhoto + 1 }} / {{ detail.photos.length }}</span>
                <button @click="currentPhoto = (currentPhoto + 1) % detail.photos.length">&rsaquo;</button>
              </div>
            </div>

            <!-- 基本信息 -->
            <div class="detail-info">
              <h2>{{ detail.name }}</h2>

              <div v-if="detail.tags && detail.tags.length" class="detail-tags">
                <span v-for="tag in detail.tags" :key="tag" class="tag">{{ tag }}</span>
              </div>

              <div class="detail-rating" v-if="detail.rating">
                <span class="stars">⭐ {{ detail.rating }}</span>
                <span v-if="detail.cost" class="cost">人均 ¥{{ detail.cost }}</span>
              </div>

              <div class="detail-list">
                <div v-if="detail.type" class="detail-row">
                  <span class="detail-label">类型</span>
                  <span>{{ formatType(detail.type) }}</span>
                </div>
                <div v-if="detail.address" class="detail-row">
                  <span class="detail-label">地址</span>
                  <span>{{ detail.district }} {{ detail.address }}</span>
                </div>
                <div v-if="detail.tel" class="detail-row">
                  <span class="detail-label">电话</span>
                  <a :href="'tel:' + detail.tel">{{ detail.tel }}</a>
                </div>
                <div v-if="detail.business_hours" class="detail-row">
                  <span class="detail-label">营业时间</span>
                  <span>{{ detail.business_hours }}</span>
                </div>
                <div v-if="detail.website" class="detail-row">
                  <span class="detail-label">官网</span>
                  <a :href="detail.website" target="_blank">{{ detail.website }}</a>
                </div>
              </div>

              <div class="detail-actions">
                <a
                  v-if="detail.lng && detail.lat"
                  :href="`https://uri.amap.com/marker?position=${detail.lng},${detail.lat}&name=${detail.name}`"
                  target="_blank"
                  class="btn"
                >
                  🗺 在高德地图中打开
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../api.js'

const city = ref('')
const keyword = ref('非遗')
const venues = ref([])
const loading = ref(false)
const searched = ref(false)

// 详情弹窗
const showDetail = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const currentPhoto = ref(0)

const formatType = (type) => {
  if (!type) return ''
  const parts = type.split(';')
  return parts[parts.length - 1] || parts[0]
}

const getTypeEmoji = (type) => {
  if (!type) return '🏛'
  if (type.includes('博物馆')) return '🏛'
  if (type.includes('展览')) return '🖼'
  if (type.includes('风景')) return '🏯'
  if (type.includes('文化')) return '🎭'
  return '📍'
}

const doSearch = async () => {
  if (!city.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    const data = await api.getVenues({
      city: city.value.trim(),
      keyword: keyword.value.trim() || '非遗',
      limit: 12,
    })
    venues.value = data.venues || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openDetail = async (venue) => {
  if (!venue.id) {
    // 没有 POI ID，直接用现有信息
    detail.value = venue
    showDetail.value = true
    return
  }
  showDetail.value = true
  detailLoading.value = true
  detail.value = null
  currentPhoto.value = 0
  try {
    const data = await api.getVenueDetail(venue.id)
    detail.value = data.detail || venue
  } catch (e) {
    detail.value = venue
  } finally {
    detailLoading.value = false
  }
}
</script>

<style scoped>
.venue-view h1 {
  font-size: 24px;
  margin-bottom: 16px;
}

.filter-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-row input {
  flex: 1;
  min-width: 160px;
}

.filter-row .btn {
  white-space: nowrap;
}

.venue-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.venue-card {
  background: var(--bg-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
}

.venue-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
}

.venue-img {
  position: relative;
  height: 180px;
  overflow: hidden;
  background: #f0ebe6;
}

.venue-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.venue-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  background: linear-gradient(135deg, #f5efe8 0%, #e8ddd2 100%);
}

.rating-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.7);
  color: #ffd700;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
}

.venue-body {
  padding: 14px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.venue-body h3 {
  font-size: 16px;
  margin-bottom: 6px;
  line-height: 1.3;
}

.venue-meta {
  margin-bottom: 8px;
}

.type-tag {
  display: inline-block;
  padding: 2px 8px;
  background: #f0e6e6;
  color: var(--primary);
  border-radius: 10px;
  font-size: 11px;
}

.venue-info {
  display: flex;
  gap: 6px;
  font-size: 13px;
  color: var(--text-light);
  margin-bottom: 4px;
  line-height: 1.4;
}

.info-icon {
  flex-shrink: 0;
}

/* ─── 弹窗 ─── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal {
  background: var(--bg-card);
  border-radius: 12px;
  max-width: 680px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
}

.modal-close {
  position: absolute;
  top: 10px;
  right: 14px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  font-size: 20px;
  cursor: pointer;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  background: rgba(0, 0, 0, 0.7);
}

.detail-images {
  position: relative;
  height: 280px;
  overflow: hidden;
  background: #f0ebe6;
}

.detail-images img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.detail-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 64px;
  background: linear-gradient(135deg, #f5efe8 0%, #e8ddd2 100%);
}

.photo-nav {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border-radius: 16px;
  padding: 4px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.photo-nav button {
  background: none;
  border: none;
  color: #fff;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}

.detail-info {
  padding: 20px;
}

.detail-info h2 {
  font-size: 22px;
  margin-bottom: 10px;
}

.detail-tags {
  margin-bottom: 10px;
}

.detail-tags .tag {
  margin-right: 4px;
}

.detail-rating {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
}

.stars {
  font-size: 15px;
  color: #e6a817;
}

.cost {
  font-size: 14px;
  color: var(--text-light);
}

.detail-list {
  border-top: 1px solid var(--border);
  padding-top: 12px;
  margin-bottom: 16px;
}

.detail-row {
  display: flex;
  padding: 8px 0;
  font-size: 14px;
  border-bottom: 1px solid #f5f0ec;
}

.detail-label {
  width: 80px;
  flex-shrink: 0;
  color: var(--text-light);
}

.detail-row a {
  word-break: break-all;
}

.detail-actions {
  padding-top: 8px;
}

.detail-actions .btn {
  width: 100%;
  text-align: center;
}

@media (max-width: 640px) {
  .venue-grid {
    grid-template-columns: 1fr;
  }
  .venue-img {
    height: 150px;
  }
  .detail-images {
    height: 200px;
  }
  .modal {
    max-height: 95vh;
  }
}
</style>
