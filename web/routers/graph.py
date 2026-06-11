"""知识图谱 API 路由"""

from fastapi import Query, APIRouter
from fastapi.responses import JSONResponse

from heritage_master.data import knowledge_graph

router = APIRouter()


@router.get("/api/graph/search")
async def api_graph_search(q: str = Query(""), type: str = Query(""), limit: int = Query(20)):
    """搜索图谱节点"""
    if not q:
        return {"nodes": [], "total": 0}
    results = knowledge_graph.search_nodes(q, node_type=type or None, limit=limit)
    return {"nodes": results, "total": len(results)}


@router.get("/api/graph/node/{node_id:path}")
async def api_graph_node(node_id: str):
    """获取节点详情及邻居"""
    node = knowledge_graph.get_node(node_id)
    if not node:
        return JSONResponse({"error": "节点不存在"}, status_code=404)
    neighbors = knowledge_graph.get_neighbors(node_id)
    return {"node": {"node_id": node_id, **node}, "neighbors": neighbors}


@router.get("/api/graph/path")
async def api_graph_path(from_id: str = Query(...), to_id: str = Query(...)):
    """查找两个节点之间的路径"""
    paths = knowledge_graph.find_path(from_id, to_id)
    return {"paths": paths}


@router.get("/api/graph/chain")
async def api_graph_chain(person: str = Query(...)):
    """获取师承链"""
    person_id = person if ":" in person else f"person:{person}"
    chain = knowledge_graph.get_inheritance_chain(person_id)
    return {"chain": chain}


@router.get("/api/graph/stats")
async def api_graph_stats():
    """获取图谱统计"""
    return knowledge_graph.get_graph_stats()


@router.get("/api/graph/explore")
async def api_graph_explore(node_id: str = Query(...), depth: int = Query(2, ge=1, le=3)):
    """从某节点探索图谱"""
    result = knowledge_graph.explore_node(node_id, depth=depth)
    return result


@router.get("/api/graph/by-type")
async def api_graph_by_type(type: str = Query(...), limit: int = Query(50)):
    """获取指定类型的所有节点"""
    results = knowledge_graph.get_nodes_by_type(type, limit=limit)
    return {"nodes": results, "total": len(results)}
