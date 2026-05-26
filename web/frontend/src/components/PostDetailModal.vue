<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content" v-if="post">
      <button class="modal-close" @click="$emit('close')">&times;</button>

      <!-- 帖子头部 -->
      <div class="post-header">
        <span class="post-cat">{{ categoryLabel(post.category) }}</span>
        <h2 class="post-title">{{ post.title }}</h2>
        <div class="post-meta">
          <span class="post-author">{{ post.author_nickname }}</span>
          <span class="post-time">{{ formatTime(post.created_at) }}</span>
        </div>
      </div>

      <!-- 帖子内容 -->
      <div class="post-body">
        <MarkdownRenderer :content="post.content" />
      </div>

      <!-- 图片 -->
      <div v-if="post.images && post.images.length" class="post-images">
        <img v-for="(img, i) in post.images" :key="i" :src="img" alt="图片" />
      </div>

      <!-- 路线卡片 -->
      <div v-if="post.route_data && post.route_data.city" class="route-card">
        <div class="route-card-header">
          <span class="route-card-icon">🗺</span>
          <h3>{{ post.route_data.name || (post.route_data.city + ' ' + post.route_data.days + '日游') }}</h3>
        </div>
        <AmapView
          v-if="post.route_data.venues"
          :venues="post.route_data.venues"
          :routeDays="post.route_data.days"
          height="220px"
          style="margin-bottom: 10px;"
        />
        <div v-if="post.route_data.itinerary" class="route-itinerary">
          <MarkdownRenderer :content="post.route_data.itinerary.slice(0, 300) + (post.route_data.itinerary.length > 300 ? '...' : '')" />
        </div>
        <button v-if="isLoggedIn" class="btn route-save-btn" :disabled="routeSaved" @click="saveRoute">
          {{ routeSaved ? '已保存到我的路线' : '保存到我的路线' }}
        </button>
      </div>

      <!-- 操作栏 -->
      <div class="post-actions">
        <button :class="['like-btn', { liked: post.liked }]" @click="doLike">
          {{ post.liked ? '❤️' : '🤍' }} {{ post.like_count }}
        </button>
        <span class="comment-count">💬 {{ post.comment_count }}</span>
      </div>

      <!-- 评论区 -->
      <div class="comments-section">
        <h3>评论 ({{ comments.length }})</h3>

        <div v-if="comments.length === 0" class="no-comments">暂无评论，快来抢沙发！</div>

        <div v-for="c in comments" :key="c.id" class="comment-item">
          <div class="comment-header">
            <span class="comment-author">{{ c.author_nickname }}</span>
            <span class="comment-time">{{ formatTime(c.created_at) }}</span>
          </div>
          <div class="comment-content">{{ c.content }}</div>
        </div>

        <!-- 发评论 -->
        <div v-if="isLoggedIn" class="comment-form">
          <textarea v-model="commentText" placeholder="写评论..." rows="2"></textarea>
          <button class="btn" :disabled="!commentText.trim()" @click="submitComment">发送</button>
        </div>
        <div v-else class="login-hint">
          <router-link to="/login">登录</router-link>后参与讨论
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api, userAuth } from '../api'
import MarkdownRenderer from './MarkdownRenderer.vue'
import AmapView from './AmapView.vue'

const props = defineProps({ postId: String })
const emit = defineEmits(['close'])

const post = ref(null)
const comments = ref([])
const commentText = ref('')
const routeSaved = ref(false)
const isLoggedIn = userAuth.isLoggedIn()

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

const loadPost = async () => {
  const viewerId = userAuth.getUserId()
  const res = await api.getForumPost(props.postId, viewerId)
  post.value = res.post
}

const loadComments = async () => {
  const res = await api.getForumComments(props.postId, 50)
  comments.value = res.comments || []
}

const doLike = async () => {
  if (!isLoggedIn) return
  const userId = userAuth.getUserId()
  const res = await api.toggleForumLike(props.postId, userId)
  post.value.liked = res.liked
  post.value.like_count = res.like_count
}

const submitComment = async () => {
  if (!commentText.value.trim()) return
  const userId = userAuth.getUserId()
  const res = await api.addForumComment(props.postId, {
    user_id: userId,
    content: commentText.value.trim(),
  })
  comments.value.push(res.comment)
  post.value.comment_count++
  commentText.value = ''
}

const saveRoute = async () => {
  if (!post.value?.route_data) return
  const rd = post.value.route_data
  try {
    await api.saveTrip({
      user_id: userAuth.getUserId(),
      name: rd.name || `${rd.city} ${rd.days}日游`,
      city: rd.city || '',
      days: rd.days || 1,
      itinerary: rd.itinerary || '',
      route_data: rd,
    })
    routeSaved.value = true
  } catch (e) {
    alert('保存失败')
  }
}

onMounted(() => {
  loadPost()
  loadComments()
})
</script>

<style scoped>
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
  max-width: 640px;
  width: 100%;
  max-height: 85vh;
  overflow-y: auto;
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

.post-header {
  margin-bottom: 16px;
}

.post-cat {
  display: inline-block;
  background: var(--primary, #b8860b);
  color: #fff;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.post-title {
  font-size: 20px;
  margin: 0 0 8px;
}

.post-meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #999;
}

.post-body {
  line-height: 1.8;
  margin-bottom: 16px;
}

.post-images {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.post-images img {
  max-width: 200px;
  max-height: 150px;
  border-radius: 8px;
  object-fit: cover;
}

.post-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid #eee;
  border-bottom: 1px solid #eee;
  margin-bottom: 16px;
}

.like-btn {
  background: none;
  border: 1px solid #ddd;
  border-radius: 20px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.like-btn.liked {
  border-color: #e74c3c;
  color: #e74c3c;
}

.comment-count {
  font-size: 14px;
  color: #666;
}

.comments-section h3 {
  font-size: 16px;
  margin: 0 0 12px;
}

.no-comments {
  color: #999;
  font-size: 14px;
  padding: 16px 0;
}

.comment-item {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.comment-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.comment-author {
  font-weight: 600;
  font-size: 13px;
}

.comment-time {
  font-size: 12px;
  color: #999;
}

.comment-content {
  font-size: 14px;
  line-height: 1.6;
}

.comment-form {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.comment-form textarea {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px;
  resize: none;
  font-size: 14px;
}

.comment-form .btn {
  padding: 8px 16px;
  background: var(--primary, #b8860b);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.login-hint {
  text-align: center;
  padding: 16px;
  color: #999;
}

.login-hint a {
  color: var(--primary, #b8860b);
}

/* 路线卡片 */
.route-card {
  background: #f9f7f4;
  border: 1px solid #e8e0d8;
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 16px;
}

.route-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.route-card-icon {
  font-size: 18px;
}

.route-card-header h3 {
  font-size: 15px;
  margin: 0;
  color: #333;
}

.route-itinerary {
  font-size: 13px;
  line-height: 1.6;
  color: #555;
  margin-bottom: 10px;
}

.route-save-btn {
  font-size: 13px;
  padding: 6px 14px;
}

.route-save-btn:disabled {
  background: #aaa;
  cursor: default;
}
</style>
