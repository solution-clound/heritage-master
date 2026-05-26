import { createRouter, createWebHistory } from 'vue-router'
import { userAuth } from './api'

const routes = [
  { path: '/', name: 'Home', component: () => import('./views/HomeView.vue') },
  { path: '/login', name: 'Login', component: () => import('./views/LoginView.vue') },
  { path: '/explore', name: 'Explore', component: () => import('./views/AgentView.vue') },
  { path: '/search', name: 'Search', component: () => import('./views/AgentView.vue') },
  { path: '/venues', name: 'Venues', component: () => import('./views/AgentView.vue') },
  { path: '/project/:name', name: 'Detail', component: () => import('./views/DetailView.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('./views/KnowledgeView.vue'), meta: { requiresAuth: true } },
  { path: '/cultivation', name: 'Cultivation', component: () => import('./views/CultivationView.vue'), meta: { requiresAuth: true } },
  { path: '/cultivation-map', name: 'CultivationMap', component: () => import('./views/CultivationMapView.vue'), meta: { requiresAuth: true } },
  { path: '/graph', name: 'Graph', component: () => import('./views/GraphView.vue') },
  { path: '/profile', name: 'Profile', component: () => import('./views/ProfileView.vue'), meta: { requiresAuth: true } },
  { path: '/forum', name: 'Forum', component: () => import('./views/ForumView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// 路由守卫：需要登录的页面未登录时跳转到 /login
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth && !userAuth.isLoggedIn()) {
    next('/login')
  } else {
    next()
  }
})

export default router
