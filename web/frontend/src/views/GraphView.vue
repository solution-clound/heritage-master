<template>
  <div class="graph-view">
    <div class="graph-header">
      <h1>文化图谱</h1>
      <p class="graph-subtitle">探索非遗的传承脉络与文化关联</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <input
        v-model="searchQuery"
        class="search-input"
        placeholder="搜索人物、项目、技艺..."
        @keyup.enter="doSearch"
      />
      <button class="search-btn" @click="doSearch">搜索</button>
    </div>

    <!-- 类型筛选 -->
    <div class="type-filters">
      <button
        v-for="t in nodeTypes"
        :key="t.value"
        :class="['type-btn', { active: selectedType === t.value }]"
        @click="filterByType(t.value)"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- 统计信息 -->
    <div class="stats-bar" v-if="stats">
      <span class="stat-item">节点: {{ stats.total_nodes }}</span>
      <span class="stat-item">关系: {{ stats.total_edges }}</span>
      <span class="stat-item" v-for="(count, type) in stats.node_types" :key="type">
        {{ typeNames[type] || type }}: {{ count }}
      </span>
    </div>

    <!-- 图谱可视化区域 -->
    <div class="graph-container" ref="graphContainer">
      <div class="graph-controls">
        <button class="ctrl-btn" @click="zoom = Math.min(3, zoom * 1.2)" title="放大">+</button>
        <button class="ctrl-btn" @click="zoom = Math.max(0.3, zoom * 0.8)" title="缩小">−</button>
        <button class="ctrl-btn" @click="resetView" title="重置">⟲</button>
      </div>
      <svg ref="svgEl" class="graph-svg" @mousedown="startPan" @mousemove="doPan" @mouseup="endPan" @mouseleave="endPan">
        <!-- 边 -->
        <line
          v-for="(edge, i) in visibleEdges"
          :key="'e' + i"
          :x1="getNodeX(edge.from)"
          :y1="getNodeY(edge.from)"
          :x2="getNodeX(edge.to)"
          :y2="getNodeY(edge.to)"
          class="graph-edge"
          :class="{ highlight: isHighlightEdge(edge) }"
        />
        <!-- 节点 -->
        <g
          v-for="node in visibleNodes"
          :key="node.node_id"
          :transform="`translate(${getNodeX(node.node_id)}, ${getNodeY(node.node_id)})`"
          class="graph-node"
          :class="{ highlight: node.node_id === centerNodeId, selected: node.node_id === selectedNodeId }"
          @click="selectNode(node)"
        >
          <circle :r="getNodeRadius(node)" :fill="getNodeColor(node)" :stroke="getNodeStroke(node)" stroke-width="2" />
          <text class="node-label" text-anchor="middle" :dy="getNodeRadius(node) + 14">
            {{ truncateName(node.name) }}
          </text>
          <text class="node-type" text-anchor="middle" :dy="-getNodeRadius(node) - 6">
            {{ typeNames[node.type] || '' }}
          </text>
        </g>
      </svg>

      <!-- 空状态 -->
      <div v-if="visibleNodes.length === 0 && !loading" class="empty-state">
        <p>搜索或点击节点探索文化图谱</p>
      </div>

      <!-- 加载中 -->
      <div v-if="loading" class="loading-state">
        <p>加载中...</p>
      </div>
    </div>

    <!-- 节点详情面板 -->
    <transition name="slide">
      <div v-if="selectedNode" class="detail-panel">
        <div class="detail-header">
          <h3>{{ selectedNode.name }}</h3>
          <button class="close-btn" @click="selectedNode = null">&times;</button>
        </div>
        <div class="detail-body">
          <div class="detail-type">{{ typeNames[selectedNode.type] || selectedNode.type }}</div>
          <div v-if="selectedNode.description" class="detail-desc">{{ selectedNode.description }}</div>
          <div v-if="selectedNode.title" class="detail-title">{{ selectedNode.title }}</div>
          <div v-if="selectedNode.specialty" class="detail-specialty">专长: {{ selectedNode.specialty }}</div>

          <div class="detail-actions">
            <button class="action-btn" @click="expandFromNode(selectedNode.node_id)">展开关联</button>
            <button class="action-btn" @click="showChain(selectedNode.node_id)" v-if="selectedNode.type === 'person'">师承链</button>
          </div>

          <!-- 邻居列表 -->
          <div v-if="nodeNeighbors.length > 0" class="neighbors-section">
            <h4>关联节点</h4>
            <div class="neighbor-list">
              <div
                v-for="n in nodeNeighbors"
                :key="n.node_id"
                class="neighbor-item"
                @click="selectNode(n)"
              >
                <span class="neighbor-type">{{ typeNames[n.type] || n.type }}</span>
                <span class="neighbor-name">{{ n.name }}</span>
                <span class="neighbor-edge">{{ edgeTypeNames[n.edge_type] || n.edge_type }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- 师承链弹窗 -->
    <transition name="fade">
      <div v-if="inheritanceChain" class="chain-overlay" @click="inheritanceChain = null">
        <div class="chain-card" @click.stop>
          <h3>师承脉络</h3>
          <div class="chain-list">
            <div v-for="(c, i) in inheritanceChain" :key="i" class="chain-item" :style="{ paddingLeft: i * 24 + 'px' }">
              <span class="chain-arrow" v-if="i > 0">└─</span>
              <span class="chain-name">{{ c.name }}</span>
              <span class="chain-title" v-if="c.title">({{ c.title }})</span>
            </div>
          </div>
          <button class="close-chain-btn" @click="inheritanceChain = null">关闭</button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { api } from '../api.js'

const searchQuery = ref('')
const selectedType = ref('')
const stats = ref(null)
const loading = ref(false)
const graphContainer = ref(null)
const svgEl = ref(null)

// 图谱数据 — 位置单独存储以确保响应式
const nodes = ref({})
const positions = ref({})  // { node_id: { x, y } }
const edges = ref([])
const centerNodeId = ref('')
const selectedNodeId = ref('')
const selectedNode = ref(null)
const nodeNeighbors = ref([])
const inheritanceChain = ref(null)
// 记录每个节点的 depth（用于布局）
const nodeDepthMap = ref({})

// 平移缩放
const panX = ref(0)
const panY = ref(0)
const zoom = ref(1)
let isPanning = false
let panStartX = 0
let panStartY = 0

const nodeTypes = [
  { value: '', label: '全部' },
  { value: 'person', label: '人物' },
  { value: 'project', label: '项目' },
  { value: 'school', label: '流派' },
  { value: 'work', label: '作品' },
  { value: 'region', label: '地域' },
  { value: 'technique', label: '技艺' },
]

const typeNames = {
  person: '人物',
  project: '项目',
  school: '流派',
  work: '作品',
  region: '地域',
  technique: '技艺',
}

const edgeTypeNames = {
  HAS_INHERITOR: '传承人',
  BELONGS_TO: '属于',
  FROM_REGION: '流传于',
  PART_OF: '流派',
  HAS_TECHNIQUE: '技艺',
  RELATED_TO: '相关',
  PRACTICES: '实践',
  FOUNDED_BY: '创始人',
  REFORMED_BY: '改革者',
  INHERITS_FROM: '师承',
}

const visibleNodes = computed(() => {
  let list = Object.entries(nodes.value).map(([id, n]) => ({ node_id: id, ...n }))
  if (selectedType.value) {
    list = list.filter(n => n.type === selectedType.value)
  }
  return list
})

const visibleEdges = computed(() => {
  const nodeIds = new Set(visibleNodes.value.map(n => n.node_id))
  return edges.value.filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
})

onMounted(async () => {
  await loadStats()
  graphContainer.value?.addEventListener('wheel', handleWheel, { passive: false })
})

const loadStats = async () => {
  try {
    stats.value = await api.graphStats()
  } catch (e) {
    console.error('Load stats failed', e)
  }
}

// ─── 核心：重新布局所有当前节点 ───
const relayout = () => {
  const centerId = centerNodeId.value
  if (!centerId || !nodes.value[centerId]) {
    // 没有中心节点时，用网格布局
    layoutGrid()
    return
  }
  layoutNodesConcentric(centerId, nodeDepthMap.value)
}

const doSearch = async () => {
  if (!searchQuery.value.trim()) return
  loading.value = true
  try {
    const data = await api.graphSearch(searchQuery.value, selectedType.value, 30)
    const newNodes = {}
    for (const n of data.nodes) {
      newNodes[n.node_id] = n
    }
    nodes.value = newNodes
    edges.value = []
    centerNodeId.value = ''
    positions.value = {}
    nodeDepthMap.value = {}
    // 展开第一个节点的邻居
    if (data.nodes.length > 0) {
      await expandFromNode(data.nodes[0].node_id)
    }
  } catch (e) {
    console.error('Search failed', e)
  } finally {
    loading.value = false
  }
}

const filterByType = async (type) => {
  selectedType.value = type
  if (type) {
    loading.value = true
    try {
      const data = await api.graphByType(type, 30)
      const newNodes = {}
      for (const n of data.nodes) {
        newNodes[n.node_id] = n
      }
      nodes.value = newNodes
      edges.value = []
      nodeDepthMap.value = {}
      centerNodeId.value = ''
      // 网格布局
      await nextTick()
      layoutGrid()
    } catch (e) {
      console.error('Filter failed', e)
    } finally {
      loading.value = false
    }
  } else {
    // 清除筛选时重新布局
    await nextTick()
    relayout()
  }
}

const expandFromNode = async (nodeId) => {
  loading.value = true
  centerNodeId.value = nodeId
  try {
    const data = await api.graphExplore(nodeId, 2)

    // 合并节点（只保留节点属性字段）
    const merged = { ...nodes.value }
    const depthMap = { [nodeId]: 0 }

    // center 节点
    merged[nodeId] = {
      node_id: nodeId,
      type: data.center.type,
      name: data.center.name,
      ...(data.center.description && { description: data.center.description }),
      ...(data.center.title && { title: data.center.title }),
      ...(data.center.specialty && { specialty: data.center.specialty }),
    }

    // neighbor 节点
    for (const n of data.neighbors) {
      merged[n.node_id] = {
        node_id: n.node_id,
        type: n.type,
        name: n.name,
        ...(n.description && { description: n.description }),
        ...(n.title && { title: n.title }),
        ...(n.specialty && { specialty: n.specialty }),
        ...(n.category && { category: n.category }),
      }
      depthMap[n.node_id] = n.depth || 1
    }
    nodes.value = merged
    nodeDepthMap.value = depthMap

    // 构建边
    const newEdges = []
    for (const n of data.neighbors) {
      newEdges.push({ from: n.from, to: n.node_id, type: n.edge_type })
    }
    // 合并边（去重）
    const edgeSet = new Set(edges.value.map(e => `${e.from}|${e.to}|${e.type}`))
    const mergedEdges = [...edges.value]
    for (const e of newEdges) {
      const key = `${e.from}|${e.to}|${e.type}`
      if (!edgeSet.has(key)) {
        edgeSet.add(key)
        mergedEdges.push(e)
      }
    }
    edges.value = mergedEdges

    // 等待 DOM 更新后布局
    await nextTick()
    layoutNodesConcentric(nodeId, depthMap)
  } catch (e) {
    console.error('Expand failed', e)
  } finally {
    loading.value = false
  }
}

// ─── 同心圆布局：按 depth 分层 ───
const layoutNodesConcentric = (centerId, depthMap) => {
  const container = graphContainer.value
  if (!container) return

  const width = container.clientWidth || 800
  const height = container.clientHeight || 500
  const cx = width / 2
  const cy = height / 2
  const baseRadius = Math.min(width, height) * 0.2

  const newPos = {}
  newPos[centerId] = { x: cx, y: cy }

  // 按 depth 分组
  const layers = {}
  for (const [id, depth] of Object.entries(depthMap)) {
    if (id === centerId) continue
    if (!layers[depth]) layers[depth] = []
    layers[depth].push(id)
  }

  // 每层一个同心圆，同层内按类型聚簇
  for (const [depth, ids] of Object.entries(layers)) {
    const d = parseInt(depth)
    const radius = baseRadius * (0.7 + d * 0.65)
    const sorted = [...ids].sort((a, b) => {
      const ta = nodes.value[a]?.type || ''
      const tb = nodes.value[b]?.type || ''
      return ta.localeCompare(tb)
    })
    sorted.forEach((id, i) => {
      const angle = (2 * Math.PI * i) / sorted.length - Math.PI / 2
      newPos[id] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      }
    })
  }

  // 补充未在 depthMap 中但存在于 nodes 的节点
  for (const id of Object.keys(nodes.value)) {
    if (!newPos[id]) {
      newPos[id] = { x: cx + (Math.random() - 0.5) * 100, y: cy + (Math.random() - 0.5) * 100 }
    }
  }

  positions.value = newPos
}

// ─── 网格布局（用于无中心节点的场景） ───
const layoutGrid = () => {
  const container = graphContainer.value
  if (!container) return

  const width = container.clientWidth || 800
  const height = container.clientHeight || 500
  const nodeIds = Object.keys(nodes.value)
  if (nodeIds.length === 0) { positions.value = {}; return }

  const cols = Math.ceil(Math.sqrt(nodeIds.length))
  const cellW = (width - 80) / cols
  const cellH = (height - 80) / Math.ceil(nodeIds.length / cols)
  const newPos = {}

  nodeIds.forEach((id, i) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    newPos[id] = {
      x: 40 + cellW * (col + 0.5),
      y: 40 + cellH * (row + 0.5),
    }
  })

  positions.value = newPos
}

// ─── 位置计算 ───
const getNodeX = (nodeId) => {
  const pos = positions.value[nodeId]
  return (pos?.x ?? 100) * zoom.value + panX.value
}

const getNodeY = (nodeId) => {
  const pos = positions.value[nodeId]
  return (pos?.y ?? 100) * zoom.value + panY.value
}

const getNodeRadius = (node) => {
  if (node.node_id === centerNodeId.value) return 22
  if (node.type === 'person') return 14
  if (node.type === 'project') return 16
  if (node.type === 'school') return 12
  return 10
}

const getNodeColor = (node) => {
  const colors = {
    person: '#bbdefb',
    project: '#ffe0b2',
    school: '#e1bee7',
    work: '#c8e6c9',
    region: '#f8bbd0',
    technique: '#b2ebf2',
  }
  return colors[node.type] || '#f5f5f5'
}

const getNodeStroke = (node) => {
  if (node.node_id === centerNodeId.value) return '#b8383b'
  if (node.node_id === selectedNodeId.value) return '#1565c0'
  const strokes = {
    person: '#1565c0',
    project: '#e65100',
    school: '#7b1fa2',
    work: '#2e7d32',
    region: '#c62828',
    technique: '#00838f',
  }
  return strokes[node.type] || '#999'
}

const isHighlightEdge = (edge) => {
  return edge.from === centerNodeId.value || edge.to === centerNodeId.value
}

const truncateName = (name) => {
  if (!name) return ''
  return name.length > 8 ? name.substring(0, 8) + '..' : name
}

const selectNode = async (node) => {
  selectedNode.value = node
  selectedNodeId.value = node.node_id
  try {
    const data = await api.graphNode(node.node_id)
    nodeNeighbors.value = data.neighbors || []
  } catch (e) {
    nodeNeighbors.value = []
  }
}

const showChain = async (nodeId) => {
  try {
    const personName = nodeId.includes(':') ? nodeId.split(':')[1] : nodeId
    const data = await api.graphChain(personName)
    inheritanceChain.value = data.chain || []
  } catch (e) {
    console.error('Chain failed', e)
  }
}

// ─── 缩放 ───
const handleWheel = (e) => {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.max(0.3, Math.min(3, zoom.value * delta))
  const rect = graphContainer.value.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  panX.value = mx - (mx - panX.value) * (newZoom / zoom.value)
  panY.value = my - (my - panY.value) * (newZoom / zoom.value)
  zoom.value = newZoom
}

// ─── 平移 ───
const startPan = (e) => {
  if (e.button !== 0) return
  isPanning = true
  panStartX = e.clientX - panX.value
  panStartY = e.clientY - panY.value
}

const doPan = (e) => {
  if (!isPanning) return
  panX.value = e.clientX - panStartX
  panY.value = e.clientY - panStartY
}

const endPan = () => {
  isPanning = false
}

// ─── 重置视图 ───
const resetView = () => {
  panX.value = 0
  panY.value = 0
  zoom.value = 1
  relayout()
}
</script>

<style scoped>
.graph-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.graph-header {
  text-align: center;
  margin-bottom: 24px;
}

.graph-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.graph-subtitle {
  color: var(--text-light);
  font-size: 14px;
}

/* 搜索栏 */
.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  padding: 12px 18px;
  border: 2px solid #e0d5ca;
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--primary);
}

.search-btn {
  padding: 12px 24px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
}

/* 类型筛选 */
.type-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.type-btn {
  padding: 6px 14px;
  border: 1px solid #ddd;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.type-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

/* 统计 */
.stats-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--text-light);
  flex-wrap: wrap;
}

/* 图谱容器 */
.graph-container {
  position: relative;
  width: 100%;
  height: 500px;
  background: #fafafa;
  border-radius: 16px;
  border: 1px solid #eee;
  overflow: hidden;
}

/* 缩放控制 */
.graph-controls {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
}

.ctrl-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fff;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  color: #555;
}

.ctrl-btn:hover {
  background: #f0f0f0;
  border-color: #bbb;
}

.graph-svg {
  width: 100%;
  height: 100%;
  cursor: grab;
}

.graph-svg:active {
  cursor: grabbing;
}

.graph-edge {
  stroke: #ddd;
  stroke-width: 1;
}

.graph-edge.highlight {
  stroke: var(--primary);
  stroke-width: 2;
}

.graph-node {
  cursor: pointer;
}

.graph-node circle {
  transition: all 0.2s;
}

.graph-node:hover circle {
  stroke-width: 3;
}

.graph-node.highlight circle {
  stroke: var(--primary);
  stroke-width: 3;
}

.graph-node.selected circle {
  stroke: #1565c0;
  stroke-width: 3;
}

.node-label {
  font-size: 11px;
  fill: #333;
  pointer-events: none;
}

.node-type {
  font-size: 9px;
  fill: #999;
  pointer-events: none;
}

/* 空状态 */
.empty-state,
.loading-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-light);
}

/* 详情面板 */
.detail-panel {
  position: fixed;
  right: 0;
  top: 56px;
  width: 320px;
  height: calc(100vh - 56px);
  background: #fff;
  box-shadow: -4px 0 20px rgba(0, 0, 0, 0.1);
  overflow-y: auto;
  z-index: 50;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.detail-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.detail-body {
  padding: 20px;
}

.detail-type {
  display: inline-block;
  padding: 4px 12px;
  background: #f5f5f5;
  border-radius: 12px;
  font-size: 12px;
  margin-bottom: 12px;
}

.detail-desc {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 12px;
  color: var(--text-light);
}

.detail-title,
.detail-specialty {
  font-size: 14px;
  margin-bottom: 8px;
}

.detail-actions {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}

.action-btn {
  padding: 8px 16px;
  border: 1px solid var(--primary);
  color: var(--primary);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--primary);
  color: #fff;
}

/* 邻居列表 */
.neighbors-section h4 {
  font-size: 14px;
  margin-bottom: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.neighbor-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.neighbor-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8f8f8;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.neighbor-item:hover {
  background: #f0f0f0;
}

.neighbor-type {
  font-size: 11px;
  color: #999;
  min-width: 30px;
}

.neighbor-name {
  flex: 1;
  font-size: 13px;
}

.neighbor-edge {
  font-size: 11px;
  color: var(--primary);
}

/* 师承链弹窗 */
.chain-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.chain-card {
  background: #fff;
  border-radius: 20px;
  padding: 32px;
  max-width: 500px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.chain-card h3 {
  margin: 0 0 20px;
  font-size: 20px;
}

.chain-list {
  margin-bottom: 20px;
}

.chain-item {
  padding: 8px 0;
  font-size: 15px;
  line-height: 1.6;
}

.chain-arrow {
  color: var(--primary);
  margin-right: 8px;
}

.chain-name {
  font-weight: 600;
}

.chain-title {
  color: var(--text-light);
  font-size: 13px;
  margin-left: 4px;
}

.close-chain-btn {
  padding: 10px 24px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

/* 动画 */
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 640px) {
  .graph-container {
    height: 350px;
  }

  .detail-panel {
    width: 100%;
  }
}
</style>
