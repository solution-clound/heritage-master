"""端到端测试 — 非遗大师助手 API"""
import requests
import json
import sys
import time

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0

def test(name, func):
    global PASS, FAIL
    try:
        func()
        PASS += 1
        print(f"  PASS  {name}")
    except Exception as e:
        FAIL += 1
        print(f"  FAIL  {name}: {e}")

def test_categories():
    r = requests.get(f"{BASE}/api/categories", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert len(data["categories"]) == 10
    assert "传统戏剧" in data["categories"]

def test_search():
    r = requests.get(f"{BASE}/api/search", params={"query": "昆曲", "limit": 3}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    assert "昆曲" in data["items"][0]["name"]

def test_graph_search():
    r = requests.get(f"{BASE}/api/graph/search", params={"q": "醒狮"}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    assert any("醒狮" in n["name"] for n in data["nodes"])

def test_graph_chain():
    r = requests.get(f"{BASE}/api/graph/chain", params={"person": "叶汉钟"}, timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "chain" in data

def test_venues():
    r = requests.get(f"{BASE}/api/venues", params={"city": "广州", "keyword": "非遗", "limit": 3}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert len(data["venues"]) > 0
    assert data["city"] == "广州"

def test_masters():
    r = requests.get(f"{BASE}/api/masters", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert len(data["masters"]) > 0

def test_agent_sync():
    """测试原有同步 Agent 接口"""
    r = requests.post(f"{BASE}/api/agent", json={
        "message": "广州有什么非遗？",
        "history": [],
        "user_id": "test_e2e",
        "session_id": "test_e2e_session"
    }, timeout=90)
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    print(f"    reply长度: {len(data['reply'])}字")
    print(f"    panels数: {len(data.get('panels', []))}")
    # 检查是否有工具调用结果
    if data.get("panels"):
        for p in data["panels"]:
            print(f"    panel: {p.get('type')}")

def test_agent_graph():
    """测试 LangGraph Agent 接口"""
    r = requests.post(f"{BASE}/api/agent/graph", json={
        "message": "醒狮是什么？",
        "history": [],
        "user_id": "test_e2e",
        "session_id": "test_e2e_graph"
    }, timeout=90)
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert len(data["reply"]) > 0
    print(f"    reply长度: {len(data['reply'])}字")
    print(f"    panels数: {len(data.get('panels', []))}")

def test_agent_stream():
    """测试 LangGraph 流式接口"""
    r = requests.post(f"{BASE}/api/agent/graph/stream", json={
        "message": "传统戏剧有哪些？",
        "history": [],
        "user_id": "test_e2e",
        "session_id": "test_e2e_stream"
    }, timeout=90, stream=True)
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")

    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            try:
                event = json.loads(line[6:])
                events.append(event)
                print(f"    event: {event.get('type')} ", end="")
                if event.get("type") == "tool_start":
                    print(f"({event.get('tool')})", end="")
                elif event.get("type") == "text_delta":
                    print(f"[{len(event.get('content', ''))}字]", end="")
                elif event.get("type") == "done":
                    print(f"reply={len(event.get('reply', ''))}字", end="")
                print()
            except json.JSONDecodeError:
                pass

    assert len(events) > 0
    # 检查是否有 done 事件
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) > 0, "缺少 done 事件"
    assert len(done_events[0].get("reply", "")) > 0, "done 事件中 reply 为空"

def test_forum_list():
    r = requests.get(f"{BASE}/api/forum/posts", params={"limit": 3}, timeout=5)
    assert r.status_code == 200

def test_knowledge():
    r = requests.get(f"{BASE}/api/knowledge", params={"name": "昆曲", "aspect": "overview"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "content" in data


print("=" * 50)
print("  非遗大师助手 — 端到端测试")
print("=" * 50)

print("\n--- 基础接口 ---")
test("GET /api/categories", test_categories)
test("GET /api/search", test_search)
test("GET /api/graph/search", test_graph_search)
test("GET /api/graph/chain", test_graph_chain)
test("GET /api/venues", test_venues)
test("GET /api/masters", test_masters)
test("GET /api/forum/posts", test_forum_list)
test("GET /api/knowledge", test_knowledge)

print("\n--- Agent 接口 ---")
test("POST /api/agent (同步)", test_agent_sync)
test("POST /api/agent/graph (LangGraph)", test_agent_graph)
test("POST /api/agent/graph/stream (SSE流式)", test_agent_stream)

print("\n" + "=" * 50)
print(f"  结果: {PASS} 通过, {FAIL} 失败")
print("=" * 50)

sys.exit(1 if FAIL > 0 else 0)
