<template>
  <div class="amap-wrapper">
    <div v-if="loading" class="amap-loading">
      <span class="amap-loading-dot"></span>
      <span class="amap-loading-dot"></span>
      <span class="amap-loading-dot"></span>
      <span class="amap-loading-text">加载地图中...</span>
    </div>
    <div v-else-if="!available" class="amap-unavailable">
      <span>📍</span>
      <span>地图服务未配置</span>
    </div>
    <div ref="mapContainer" class="amap-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { http } from '../api.js'

const props = defineProps({
  venues: { type: Array, default: () => [] },
  routeDays: { type: Array, default: () => [] },
  height: { type: String, default: '360px' },
})

const mapContainer = ref(null)
const loading = ref(true)
const available = ref(false)
let map = null
let AMap = null

// 动态加载高德 JS SDK
let sdkPromise = null
function loadAmapSDK(key, securityCode) {
  if (window.AMap) return Promise.resolve(window.AMap)
  if (sdkPromise) return sdkPromise

  sdkPromise = new Promise((resolve, reject) => {
    // 设置安全密钥
    if (securityCode) {
      window._AMapSecurityConfig = { securityJsCode: securityCode }
    }

    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${key}&plugin=AMap.Scale,AMap.ToolBar,AMap.Walking`
    script.onload = () => resolve(window.AMap)
    script.onerror = () => reject(new Error('AMap SDK load failed'))
    document.head.appendChild(script)
  })

  return sdkPromise
}

const dayColors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22']

async function initMap() {
  try {
    const { data } = await http.get('/map-config')
    if (!data.available) {
      available.value = false
      loading.value = false
      return
    }
    available.value = true
    AMap = await loadAmapSDK(data.key, data.security_code)
    await nextTick()
    createMap()
  } catch (e) {
    console.error('地图初始化失败', e)
    available.value = false
  } finally {
    loading.value = false
  }
}

function createMap() {
  if (!mapContainer.value || !AMap) return

  map = new AMap.Map(mapContainer.value, {
    zoom: 13,
    mapStyle: 'amap://styles/whitesmoke',
    resizeEnable: true,
  })

  renderMarkers()
}

function renderMarkers() {
  if (!map || !AMap) return
  map.clearMap()

  const allMarkers = []
  const allLngs = []
  const allLats = []

  // 如果有多日路线，按天渲染不同颜色
  if (props.routeDays && props.routeDays.length > 0) {
    props.routeDays.forEach((dayVenues, dayIdx) => {
      const color = dayColors[dayIdx % dayColors.length]
      const path = []

      dayVenues.forEach((v, slotIdx) => {
        if (!v.lng || !v.lat) return
        const pos = new AMap.LngLat(v.lng, v.lat)
        path.push(pos)
        allLngs.push(v.lng)
        allLats.push(v.lat)

        // 起点/终点/普通站点标记
        const role = v.role || 'stop'
        const roleIcon = role === 'start' ? '🚩' : (role === 'end' ? '🏁' : '')
        const roleLabel = role === 'start' ? '起点' : (role === 'end' ? '终点' : '')
        const badgeText = roleLabel || `D${dayIdx + 1}`
        const badgeBg = role === 'start' ? '#2ecc71' : (role === 'end' ? '#e74c3c' : color)

        const marker = new AMap.Marker({
          position: pos,
          cursor: 'pointer',
          label: {
            content: `<div class="amap-marker-label" style="border-color:${badgeBg}">
              <span class="day-badge" style="background:${badgeBg}">${badgeText}</span>
              <span class="venue-name">${roleIcon} ${v.name}</span>
              <span class="nav-hint">🧭</span>
            </div>`,
            direction: 'top',
          },
          title: v.name,
          extData: v,
        })
        marker.on('click', () => {
          const name = encodeURIComponent(v.name || '')
          window.open(`https://uri.amap.com/marker?position=${v.lng},${v.lat}&name=${name}`, '_blank')
        })
        allMarkers.push(marker)
      })

      // 画路线
      if (path.length >= 2) {
        const polyline = new AMap.Polyline({
          path,
          strokeColor: color,
          strokeWeight: 4,
          strokeOpacity: 0.8,
          lineJoin: 'round',
        })
        map.add(polyline)
      }
    })
  } else {
    // 只有场馆列表，没有路线
    props.venues.forEach((v) => {
      if (!v.lng || !v.lat) return
      const pos = new AMap.LngLat(v.lng, v.lat)
      allLngs.push(v.lng)
      allLats.push(v.lat)

      const marker = new AMap.Marker({
        position: pos,
        cursor: 'pointer',
        title: v.name,
        extData: v,
        label: {
          content: `<div class="amap-marker-label">
            <span class="venue-name">${v.name}</span>
            <span class="nav-hint">🧭</span>
          </div>`,
          direction: 'top',
        },
      })
      marker.on('click', () => {
        const name = encodeURIComponent(v.name || '')
        window.open(`https://uri.amap.com/marker?position=${v.lng},${v.lat}&name=${name}`, '_blank')
      })
      allMarkers.push(marker)
    })
  }

  if (allMarkers.length > 0) {
    map.add(allMarkers)
    // 自适应视野
    map.setFitView(allMarkers, false, [60, 60, 60, 60])
  } else if (allLngs.length > 0) {
    const center = [
      allLngs.reduce((a, b) => a + b, 0) / allLngs.length,
      allLats.reduce((a, b) => a + b, 0) / allLats.length,
    ]
    map.setCenter(center)
  }
}

watch(() => [props.venues, props.routeDays], () => {
  if (map) renderMarkers()
}, { deep: true })

onMounted(() => {
  if (props.venues.length > 0 || (props.routeDays && props.routeDays.some(d => d.length > 0))) {
    initMap()
  } else {
    loading.value = false
    available.value = false
  }
})

onUnmounted(() => {
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<style scoped>
.amap-wrapper {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
  background: #f5f5f5;
}

.amap-container {
  width: 100%;
  height: v-bind(height);
}

.amap-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: v-bind(height);
  color: #999;
  font-size: 13px;
}

.amap-loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ccc;
  animation: amapBounce 1.2s infinite ease-in-out;
}

.amap-loading-dot:nth-child(2) { animation-delay: 0.2s; }
.amap-loading-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes amapBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.amap-loading-text {
  margin-left: 4px;
}

.amap-unavailable {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 120px;
  color: #999;
  font-size: 13px;
}

/* 标签样式（通过 JS 注入） */
:deep(.amap-marker-label) {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #fff;
  border-radius: 6px;
  border-left: 3px solid #e74c3c;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  font-size: 12px;
  white-space: nowrap;
}

:deep(.day-badge) {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
}

:deep(.venue-name) {
  color: #333;
  font-weight: 500;
}

:deep(.nav-hint) {
  font-size: 10px;
  opacity: 0.6;
  margin-left: 2px;
}
</style>
