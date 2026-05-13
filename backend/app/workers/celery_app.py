"""Celery app 工厂。

环境变量（worker 容器里由 docker-compose 注入；backend 侧由 .env 或默认值）：
  CELERY_BROKER_URL       默认 redis://localhost:6379/0
  CELERY_RESULT_BACKEND   默认 redis://localhost:6379/1
  BACKEND_URL             默认 http://localhost:8000（worker 容器里改为 http://host.docker.internal:8000）

同一实例 Redis 用 db0 当 broker，db1 存 result，互不干扰。
"""
import os
from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "xuanjian",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # ── 序列化 ──────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,

    # ── 超时 ────────────────────────────────
    # 单 task 硬超时 30 分钟（极端大文档也够），软超时 25 分钟触发 SoftTimeLimitExceeded
    task_time_limit=1800,
    task_soft_time_limit=1500,

    # ── 重试 / 可靠性 ───────────────────────
    task_acks_late=True,              # worker 崩溃时任务重新入队（exactly-once 的关键）
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,     # 一次只取一个任务，避免批量丢失

    # ── 结果 TTL ─────────────────────────────
    result_expires=3600,              # 结果保留 1 小时，释放 Redis 内存

    # ── 路由 ────────────────────────────────
    task_default_queue="xuanjian.vectorize",
    task_default_exchange="xuanjian",
    task_default_routing_key="xuanjian.vectorize",
)
