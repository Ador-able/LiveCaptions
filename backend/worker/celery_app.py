import os
from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Celery 应用配置
# 这里定义了 Celery 实例，并指定了任务模块
celery_app = Celery(
    "livecaptions",
    broker=broker_url,
    backend=result_backend,
    include=["backend.worker.tasks"] # 包含任务模块
)

# 可选配置优化
# 提高任务处理效率和可靠性
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai", # 使用上海时区
    enable_utc=True,
    worker_prefetch_multiplier=1, # 对于长时间运行的任务 (ASR, LLM)，设置为 1 可以避免任务堆积
    task_acks_late=True, # 确保任务即使 worker 崩溃也不会丢失，必须等到任务完成后才确认
)
