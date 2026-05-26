<template>
  <div class="forum-view">
    <h1>非遗论坛</h1>

    <!-- 工具栏 -->
    <div class="toolbar card">
      <div class="toolbar-row">
        <input v-model="searchKw" placeholder="搜索讨论..." @keyup.enter="doSearch" />
        <button class="btn" @click="doSearch">搜索</button>
        <select v-model="filterCat" @change="resetAndLoad">
          <option value="">全部分类</option>
          <option value="experience">体验分享</option>
          <option value="guide">攻略推荐</option>
          <option value="qna">知识问答</option>
          <option value="stories">传承人故事</option>
          <option value="events">活动信息</option>
        </select>
        <button class="btn btn-outline" @click="openCreate">发帖</button>
      </div>
    </div>

    <!-- 帖子列表 -->
    <div v-if="loading && posts.length === 0" class="loading">加载中...</div>
    <div v-else-if="posts.length === 0" class="empty">暂无讨论</div>

    <div class="post-list">
      <div v-for="p in posts" :key="p.id" class="post-card card" @click="openDetail(p.id)">
        <div class="post-card-header">
          <span class="post-cat-tag">{{ categoryLabel(p.category) }}</span>
          <span class="post-card-time">{{ formatTime(p.created_at) }}</span>
        </div>
        <h3 class="post-card-title">{{ p.title }}</h3>
        <p class="post-card-snippet">{{ snippet(p.content) }}</p>
        <div class="post-card-footer">
          <span class="post-card-author">{{ p.author_nickname }}</span>
          <span class="post-card-stats">
            ❤️ {{ p.like_count }} &nbsp; 💬 {{ p.comment_count }}
          </span>
        </div>
      </div>
    </div>

    <!-- 无限滚动哨兵 -->
    <div ref="sentinel" class="sentinel">
      <div v-if="loadingMore" class="loading">加载更多...</div>
      <div v-else-if="!hasMore && posts.length > 0" class="no-more">没有更多了</div>
    </div>

    <!-- 发帖弹窗 -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal-content">
        <button class="modal-close" @click="showCreate = false">&times;</button>
        <h2>发布新讨论</h2>
        <input v-model="createForm.title" placeholder="标题" class="create-input" />
        <select v-model="createForm.category" class="create-input">
          <option value="experience">体验分享</option>
          <option value="guide">攻略推荐</option>
          <option value="qna">知识问答</option>
          <option value="stories">传承人故事</option>
          <option value="events">活动信息</option>
        </select>
        <textarea v-model="createForm.content" placeholder="内容（支持 Markdown）" rows="6" class="create-input"></textarea>

        <!-- 图片上传 -->
        <div class="image-upload-section">
          <label class="upload-btn" :class="{ disabled: uploading }">
            <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" @change="handleImageUpload" hidden />
            {{ uploading ? '上传中...' : '+ 添加图片' }}
          </label>
          <div v-if="createForm.images.length" class="image-preview-list">
            <div v-for="(img, i) in createForm.images" :key="i" class="image-preview">
              <img :src="img" alt="预览" />
              <button class="image-remove" @click="removeImage(i)">&times;</button>
            </div>
          </div>
        </div>

        <!-- 路线选择 -->
        <div v-if="savedRoutes.length" class="route-select-section">
          <select v-model="createForm.route_id" class="create-input">
            <option value="">不附加路线</option>
            <option v-for="r in savedRoutes" :key="r.id" :value="r.id">
              {{ r.name }}（{{ r.city }}{{ r.days }}天）
            </option>
          </select>
        </div>

        <div class="create-actions">
          <button class="btn btn-outline" @click="showCreate = false">取消</button>
          <button class="btn" :disabled="posting || !createForm.title.trim() || !createForm.content.trim()" @click="submitPost">
            {{ posting ? '发布中...' : '发布' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 帖子详情弹窗 -->
    <PostDetailModal v-if="detailId" :post-id="detailId" @close="detailId = null" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { api, userAuth } from '../api'
import PostDetailModal from '../components/PostDetailModal.vue'

const categoryLabels = {
  experience: '体验分享', guide: '攻略推荐', qna: '知识问答',
  stories: '传承人故事', events: '活动信息',
}
const categoryLabel = (cat) => categoryLabels[cat] || cat

const formatTime = (t) => {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  return d.toLocaleDateString('zh-CN')
}

const snippet = (text) => {
  if (!text) return ''
  return text.replace(/[#*`\n]/g, ' ').slice(0, 120) + (text.length > 120 ? '...' : '')
}

// State
const posts = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)
const cursor = ref(0)
const searchKw = ref('')
const filterCat = ref('')
const showCreate = ref(false)
const posting = ref(false)
const detailId = ref(null)
const sentinel = ref(null)
const isSearching = ref(false)

const createForm = reactive({ title: '', content: '', category: 'experience', images: [], route_id: '' })
const savedRoutes = ref([])
const uploading = ref(false)

let observer = null

const PAGE_SIZE = 10

const loadPosts = async (reset = false) => {
  if (reset) {
    cursor.value = 0
    posts.value = []
    hasMore.value = true
  }
  if (!hasMore.value) return

  if (cursor.value === 0) loading.value = true
  else loadingMore.value = true

  try {
    const params = { limit: PAGE_SIZE, cursor: cursor.value }
    if (filterCat.value) params.category = filterCat.value
    const data = await api.getForumPosts(params)
    const newPosts = data.posts || []
    posts.value.push(...newPosts)
    cursor.value = data.next_cursor
    hasMore.value = data.has_more
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const resetAndLoad = () => {
  isSearching.value = false
  searchKw.value = ''
  loadPosts(true)
}

const doSearch = async () => {
  const kw = searchKw.value.trim()
  if (!kw) return resetAndLoad()
  loading.value = true
  isSearching.value = true
  hasMore.value = false
  try {
    const data = await api.searchForumPosts({ keyword: kw, limit: 50 })
    posts.value = data.posts || data || []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const openCreate = async () => {
  if (!userAuth.isLoggedIn()) {
    window.location.href = '/login'
    return
  }
  showCreate.value = true
  // 加载用户已保存路线
  try {
    const data = await api.getSavedTrips(userAuth.getUserId())
    savedRoutes.value = data.routes || []
  } catch { savedRoutes.value = [] }
}

const handleImageUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  uploading.value = true
  try {
    const res = await api.uploadImage(file)
    createForm.images.push(res.url)
  } catch (err) {
    alert('上传失败：' + (err.response?.data?.error || err.message))
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

const removeImage = (idx) => {
  createForm.images.splice(idx, 1)
}

const submitPost = async () => {
  if (!createForm.title.trim() || !createForm.content.trim()) return
  posting.value = true
  try {
    await api.createForumPost({
      user_id: userAuth.getUserId(),
      title: createForm.title.trim(),
      content: createForm.content.trim(),
      category: createForm.category,
      images: createForm.images,
      route_id: createForm.route_id,
    })
    showCreate.value = false
    createForm.title = ''
    createForm.content = ''
    createForm.category = 'experience'
    createForm.images = []
    createForm.route_id = ''
    loadPosts(true)
  } catch (e) {
    console.error(e)
    alert('发布失败')
  } finally {
    posting.value = false
  }
}

const openDetail = (id) => {
  detailId.value = id
}

// IntersectionObserver for infinite scroll
const setupObserver = () => {
  if (!sentinel.value) return
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !loading.value && !loadingMore.value && !isSearching.value) {
      loadPosts()
    }
  }, { threshold: 0.1 })
  observer.observe(sentinel.value)
}

onMounted(async () => {
  await loadPosts(true)
  await nextTick()
  setupObserver()
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.forum-view h1 {
  font-size: 24px;
  margin-bottom: 16px;
}

.toolbar {
  margin-bottom: 16px;
}

.toolbar-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-row input {
  flex: 1;
  min-width: 160px;
}

.toolbar-row select {
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 14px;
}

.post-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.post-card {
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.2s;
  padding: 16px 20px;
}

.post-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.post-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.post-cat-tag {
  display: inline-block;
  background: var(--primary, #b8860b);
  color: #fff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.post-card-time {
  font-size: 12px;
  color: #999;
}

.post-card-title {
  font-size: 17px;
  margin: 0 0 6px;
  color: #333;
}

.post-card-snippet {
  font-size: 13px;
  color: #666;
  line-height: 1.6;
  margin: 0 0 10px;
}

.post-card-footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
}

.post-card-stats {
  display: flex;
  gap: 8px;
}

.sentinel {
  padding: 16px 0;
  text-align: center;
}

.no-more {
  color: #999;
  font-size: 13px;
}

/* 发帖弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-content {
  background: #fff;
  border-radius: 12px;
  max-width: 560px;
  width: 100%;
  padding: 24px;
  position: relative;
}

.modal-close {
  position: absolute;
  top: 12px;
  right: 16px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.modal-content h2 {
  margin: 0 0 16px;
  font-size: 20px;
}

.create-input {
  width: 100%;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  margin-bottom: 12px;
  box-sizing: border-box;
}

.create-input:focus {
  outline: none;
  border-color: var(--primary, #b8860b);
}

textarea.create-input {
  resize: vertical;
  min-height: 120px;
}

.create-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.btn-outline {
  background: #fff;
  border: 1px solid #ddd;
  color: #333;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
}

.btn {
  padding: 8px 16px;
  background: var(--primary, #b8860b);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading, .empty {
  text-align: center;
  padding: 32px;
  color: #999;
}

/* 图片上传 */
.image-upload-section {
  margin-bottom: 12px;
}

.upload-btn {
  display: inline-block;
  padding: 6px 14px;
  background: #f5f5f5;
  border: 1px dashed #ccc;
  border-radius: 8px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-btn:hover {
  border-color: var(--primary, #b8860b);
  color: var(--primary, #b8860b);
}

.upload-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.image-preview-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.image-preview {
  position: relative;
  width: 80px;
  height: 80px;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
}

.image-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 50%;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 路线选择 */
.route-select-section {
  margin-bottom: 12px;
}
</style>
