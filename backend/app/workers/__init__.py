"""Celery 异步任务队列模块（运行时可开关 · 默认 off）。

架构：
  - worker 容器（Docker · 仅 celery+redis+requests · ~100MB）从 Redis 取任务
  - task 执行 = HTTP POST 到 backend 的 /api/internal/vectorize/{file_id}
  - backend 主进程保持 BGE-M3 单一实例，worker 零 ML 依赖

本模块只在 celery_enabled=True 时被导入 + 使用。默认关闭时完全惰性。
"""
