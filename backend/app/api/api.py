from fastapi import APIRouter
from app.api.endpoints import chat, conversations, upload, embedding, vector_store, solo, memory, internal, admin_bench

api_router = APIRouter()
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(solo.router, tags=["solo"])
api_router.include_router(conversations.router, tags=["conversations"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(embedding.router, tags=["embedding"])
api_router.include_router(vector_store.router, tags=["vector_store"])
api_router.include_router(memory.router, tags=["memory"])  # P3.4 · durable memory 审计
# 内部端点（Celery worker 回调专用 · main.py 中间件拒绝非本机 IP）
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
# Benchmark 管理端点（bench runner 专用，受 InternalOnlyMiddleware 保护）
api_router.include_router(admin_bench.router, tags=["admin-bench"])
