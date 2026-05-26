# 非遗大师 - 2026年5月16日 开发日志

## 一、新增功能

### 1. 组合搜索接口 `/api/search/enriched`

一次请求返回项目搜索结果 + 相关活动 + 场馆 + 路线规划建议。

**接口参数：**
- `query` - 搜索关键词
- `category` - 非遗类别
- `region` - 地区
- `limit` - 返回数量

**返回结构：**
```json
{
  "items": [...],        // 非遗项目列表
  "events": [...],       // 相关活动
  "venues": [...],       // 相关场馆
  "route_hint": {...},   // 路线规划建议
  "total_projects": 1,
  "total_events": 0
}
```

**文件变更：** `web/app.py` 第172-215行

---

### 2. 活动/事件接口 `/api/events`

从中国非遗网获取活动信息，自动分类为展览、体验活动、讲座论坛、比赛评选、演出、培训传习、节庆市集等类型。

**接口参数：**
- `keyword` - 搜索关键词（如"茶文化"、"刺绣"）
- `region` - 地区筛选（如"广东"）
- `limit` - 返回数量

**活动分类关键词：**
```python
_EVENT_KEYWORDS = [
    "展览", "展演", "展示", "博览会",
    "活动", "体验", "互动", "参与",
    "工作坊", "讲座", "论坛", "研讨会",
    "大赛", "比赛", "竞赛", "评选",
    "演出", "公演", "汇演", "巡演",
    "培训", "研修", "传习",
    "市集", "集市", "庙会", "节庆",
    "开幕", "启动",
]
```

**文件变更：** `src/heritage_master/data/realtime.py` 第43-220行, `web/app.py` 第499-514行

---

### 3. LLM 搜索增强 `/api/search?enrich=true`

使用 LLM 为搜索结果生成丰富描述。基于知识库 + 项目元数据构建 prompt，生成 2-3 句话的自然语言描述。

**工作流程：**
1. 搜索非遗项目
2. 为每个项目获取知识库内容 + 元数据
3. 构建 prompt 调用 LLM
4. 用 AI 生成的描述替换原始描述
5. 并发处理，信号量限制为 3

**前置条件：** 需配置 `HERITAGE_LLM_API_KEY` 环境变量

**文件变更：** `web/app.py` 第131-170行

---

### 4. 前端活动展示

SearchView 更新为使用组合搜索接口，展示：
- 非遗项目列表（带 AI 增强标识）
- 相关活动卡片（含活动类型标签、日期、来源链接）
- 路线规划建议（含跳转到旅行规划页面的按钮）

**文件变更：** `web/frontend/src/views/SearchView.vue`, `web/frontend/src/api.js`

---

## 二、Bug 修复

### 1. 项目详情页"暂无详细信息"问题

**问题：** 当 ihchina.cn 不可达时，`get_heritage_detail` 返回空 dict，导致 `if not result:` 过早返回"暂无详细信息"，跳过了知识库和内置数据的降级逻辑。

**修复：** 调整 `get_heritage_detail` 中的降级逻辑顺序，确保知识库、百度百科、内置数据都能被正确尝试。

```python
# 修复前（crawler.py 第441行）
if not result:
    return {"name": name, "description": "暂无详细信息"}

# 修复后
if result and not result.get("description"):
    result["description"] = _generate_meta_description(result)
if not result:
    result = {"name": name}
if not result.get("description"):
    result["description"] = "暂无详细信息"
```

**文件变更：** `src/heritage_master/data/crawler.py` 第441-450行

---

### 2. 内置数据降级只复制描述字段

**问题：** 从内置数据降级时，只复制了 `description` 字段，`category`、`region`、`batch` 等字段丢失。

**修复：** 改为复制所有缺失的字段。

```python
# 修复前
for item in builtin:
    if item["name"] == name:
        if not result.get("description"):
            result["description"] = item.get("description", "")
        break

# 修复后
for item in builtin:
    if item["name"] == name:
        for k, v in item.items():
            if k not in result or not result[k]:
                result[k] = v
        break
```

**文件变更：** `src/heritage_master/data/crawler.py` 第432-439行

---

### 3. 知识库返回无关项目

**问题：** 搜索"采茶戏"时，知识库接口返回"昆曲"的内容。原因是 `_get_knowledge_from_meta` 在找不到匹配项目时，返回内置数据的前5项作为兜底。

**修复：** 移除 `items = builtin[:5]` 兜底逻辑，没有精确匹配时返回空字符串。

**文件变更：** `src/heritage_master/tools/knowledge_base.py` 第183-210行

---

### 4. `_LLM_SYSTEM_PROMPT` 未定义

**问题：** `_ask_llm` 函数引用了 `_LLM_SYSTEM_PROMPT` 变量但未定义，导致 LLM 调用时报 `NameError`。

**修复：** 在导入 `MASTER_SYSTEM_PROMPT` 后定义 `_LLM_SYSTEM_PROMPT = MASTER_SYSTEM_PROMPT`。

**文件变更：** `web/app.py` 第68行

---

## 三、数据扩充

### 内置数据新增项目

在 `crawler.py` 的 `_get_builtin_data()` 中新增以下项目：

| 项目名称 | 类别 | 地区 | 批次 |
|----------|------|------|------|
| 采茶戏 | 传统戏剧 | 江西,广东,福建,湖南 | 第二批 |
| 越剧 | 传统戏剧 | 浙江,上海,江苏 | 第一批 |
| 黄梅戏 | 传统戏剧 | 安徽,湖北,江西 | 第一批 |
| 豫剧 | 传统戏剧 | 河南,全国 | 第一批 |
| 中国书法 | 传统美术 | 全国 | 第一批 (UNESCO) |
| 少林功夫 | 传统体育 | 河南 | 第一批 |

**文件变更：** `src/heritage_master/data/crawler.py` 第797行之后

---

## 四、前端更新

### TripView 支持 URL 参数预填

旅行规划页面现在支持 `?city=广州` 参数，从搜索结果的路线建议跳转时自动填入城市。

**文件变更：** `web/frontend/src/views/TripView.vue`

### api.js 新增接口

```javascript
searchEnriched: (params) => http.get('/search/enriched', { params }).then(r => r.data),
getEvents: (params) => http.get('/events', { params }).then(r => r.data),
```

**文件变更：** `web/frontend/src/api.js`

---

## 五、测试验证

### 测试结果

| 测试项 | 结果 | 说明 |
|--------|------|------|
| `/api/search/enriched?query=刺绣&region=广东` | ✅ | 返回1个项目 |
| `/api/events` | ✅ | 端点正常，ihchina.cn不可达时返回空 |
| `/api/project/采茶戏` | ✅ | 返回完整信息（名称、类别、地区、批次、描述） |
| `/api/project/中国书法` | ✅ | 返回完整信息 |
| `/api/knowledge?name=昆曲` | ✅ | 返回181字符知识内容 |
| `/api/knowledge?name=采茶戏` | ✅ | 返回正确项目信息（不再返回昆曲） |
| `/api/ask` (粤剧) | ✅ | 返回结构化回答 |
| 前端构建 | ✅ | npm run build 成功 |

### 待配置功能

| 功能 | 配置项 | 说明 |
|------|--------|------|
| LLM 增强 | `HERITAGE_LLM_API_KEY` | 配置后搜索结果会用 AI 生成丰富描述 |
| 场馆搜索 | `AMAP_KEY` | 配置高德API Key后可搜索非遗场馆 |
| 实时活动 | 网络访问 ihchina.cn | 当前网络无法访问中国非遗网 |

---

## 六、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `web/app.py` | 修改 | 新增组合搜索接口、活动接口、LLM增强、修复 _LLM_SYSTEM_PROMPT |
| `src/heritage_master/data/crawler.py` | 修改 | 修复详情页降级逻辑、扩充内置数据 |
| `src/heritage_master/data/realtime.py` | 修改 | 新增活动分类和 `get_heritage_events` |
| `src/heritage_master/tools/knowledge_base.py` | 修改 | 修复知识库返回无关项目问题 |
| `web/frontend/src/views/SearchView.vue` | 修改 | 支持活动展示和路线建议 |
| `web/frontend/src/views/TripView.vue` | 修改 | 支持 URL 参数预填城市 |
| `web/frontend/src/api.js` | 修改 | 新增 searchEnriched 和 getEvents 接口 |
