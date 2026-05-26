<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <span class="login-icon">🏛</span>
        <h1>非遗大师</h1>
        <p class="login-subtitle">{{ isLogin ? '欢迎回来' : '拜师入门' }}</p>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>昵称</label>
          <input
            v-model="nickname"
            type="text"
            placeholder="请输入昵称..."
            maxlength="20"
            autocomplete="username"
          />
        </div>
        <div class="form-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="请输入密码..."
            minlength="4"
            autocomplete="current-password"
          />
        </div>

        <div v-if="error" class="login-error">{{ error }}</div>

        <button type="submit" class="login-btn" :disabled="loading || !nickname.trim() || password.length < 4">
          {{ loading ? '请稍候...' : (isLogin ? '登 录' : '注 册') }}
        </button>
      </form>

      <div class="login-switch">
        <span v-if="isLogin">还没有账号？</span>
        <span v-else>已有账号？</span>
        <a href="#" @click.prevent="isLogin = !isLogin; error = ''">
          {{ isLogin ? '立即注册' : '去登录' }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, userAuth } from '../api'

const router = useRouter()
const nickname = ref('')
const password = ref('')
const isLogin = ref(true)
const loading = ref(false)
const error = ref('')

const handleSubmit = async () => {
  if (!nickname.value.trim() || password.value.length < 4) return
  loading.value = true
  error.value = ''

  try {
    let user
    if (isLogin.value) {
      user = await api.userLogin(nickname.value.trim(), password.value)
    } else {
      user = await api.userRegister(nickname.value.trim(), password.value)
    }
    userAuth.save(user.id, user.nickname)
    router.push('/knowledge')
  } catch (e) {
    const msg = e.response?.data?.error || (isLogin.value ? '登录失败' : '注册失败')
    error.value = msg
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 120px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
  padding: 40px 36px;
  width: 100%;
  max-width: 380px;
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 12px;
}

.login-header h1 {
  font-size: 24px;
  color: var(--primary, #8B4513);
  margin: 0 0 8px;
}

.login-subtitle {
  color: #888;
  font-size: 14px;
  margin: 0;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 14px;
  color: #555;
  margin-bottom: 6px;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
  border-color: var(--primary, #8B4513);
}

.login-error {
  color: #e74c3c;
  font-size: 13px;
  margin-bottom: 16px;
  text-align: center;
}

.login-btn {
  width: 100%;
  padding: 12px;
  background: var(--primary, #8B4513);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.login-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.login-switch {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: #888;
}

.login-switch a {
  color: var(--primary, #8B4513);
  text-decoration: none;
  font-weight: 500;
}

.login-switch a:hover {
  text-decoration: underline;
}
</style>
