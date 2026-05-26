<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/" class="logo">
        <span class="logo-icon">🏛</span>
        <span class="logo-text">非遗大师</span>
      </router-link>
      <nav class="nav">
        <router-link to="/explore">探索</router-link>
        <router-link to="/knowledge">问答</router-link>
        <router-link to="/cultivation">修行</router-link>
        <router-link to="/graph">图谱</router-link>
        <router-link to="/profile">档案</router-link>
        <router-link to="/forum">论坛</router-link>
      </nav>
      <div class="user-area">
        <template v-if="isLoggedIn">
          <span class="user-name">{{ nickname }}</span>
          <button class="logout-btn" @click="handleLogout">退出</button>
        </template>
        <router-link v-else to="/login" class="login-link">登录</router-link>
      </div>
      <button class="menu-toggle" @click="menuOpen = !menuOpen">☰</button>
    </div>
    <nav v-if="menuOpen" class="nav-mobile" @click="menuOpen = false">
      <router-link to="/explore">探索</router-link>
      <router-link to="/knowledge">问答</router-link>
      <router-link to="/cultivation">修行</router-link>
      <router-link to="/graph">图谱</router-link>
      <router-link to="/profile">档案</router-link>
      <router-link to="/forum">论坛</router-link>
      <template v-if="isLoggedIn">
        <span class="mobile-user">{{ nickname }}</span>
        <a href="#" @click.prevent="handleLogout">退出登录</a>
      </template>
      <router-link v-else to="/login">登录</router-link>
    </nav>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { userAuth } from '../api'

const router = useRouter()
const menuOpen = ref(false)
const isLoggedIn = computed(() => userAuth.isLoggedIn())
const nickname = computed(() => userAuth.getNickname())

const handleLogout = () => {
  userAuth.clear()
  menuOpen.value = false
  router.push('/login')
}
</script>

<style scoped>
.header {
  background: var(--primary);
  color: #fff;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.header-inner {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 16px;
  display: flex;
  align-items: center;
  height: 56px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  text-decoration: none;
  margin-right: auto;
}

.logo-icon {
  font-size: 24px;
}

.nav {
  display: flex;
  gap: 24px;
}

.nav a {
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  text-decoration: none;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.nav a:hover,
.nav a.router-link-active {
  color: #fff;
  border-bottom-color: #fff;
}

.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 20px;
}

.user-name {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.logout-btn {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 4px;
  padding: 4px 12px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.25);
}

.login-link {
  color: #fff;
  font-size: 14px;
  text-decoration: none;
  padding: 4px 12px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 4px;
  transition: background 0.2s;
}

.login-link:hover {
  background: rgba(255, 255, 255, 0.15);
}

.menu-toggle {
  display: none;
  background: none;
  border: none;
  color: #fff;
  font-size: 22px;
  cursor: pointer;
  margin-left: 12px;
}

.nav-mobile {
  display: flex;
  flex-direction: column;
  padding: 8px 16px 12px;
  gap: 8px;
}

.nav-mobile a {
  color: rgba(255, 255, 255, 0.85);
  text-decoration: none;
  padding: 6px 0;
}

.mobile-user {
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  padding: 6px 0 0;
}

@media (max-width: 640px) {
  .nav {
    display: none;
  }
  .user-area {
    display: none;
  }
  .menu-toggle {
    display: block;
  }
}
</style>
