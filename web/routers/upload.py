"""图片上传 API 路由"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()

_UPLOAD_DIR = Path(__file__).parent.parent / "static" / "uploads"
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """上传图片，返回可访问的 URL"""
    if file.content_type not in _ALLOWED_TYPES:
        return JSONResponse({"error": "仅支持 jpg/png/gif/webp 格式"}, status_code=400)
    data = await file.read()
    if len(data) > _MAX_SIZE:
        return JSONResponse({"error": "文件大小不能超过 5MB"}, status_code=400)
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    unique = hashlib.md5(data[:1024]).hexdigest()[:8] + "_" + uuid.uuid4().hex[:8]
    filename = f"{unique}.{ext}"
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (_UPLOAD_DIR / filename).write_bytes(data)
    return {"url": f"/static/uploads/{filename}"}
