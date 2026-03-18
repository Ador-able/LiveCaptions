"""
Celery 应用配置

配置加载由 config 模块统一管理，这里只需导入即可。
"""
import sys
from celery import Celery
from loguru import logger

from ..config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TIMEZONE
from ..database import engine
from .. import models

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

# Create database tables when Celery app initializes
models.Base.metadata.create_all(bind=engine)

# Celery 应用配置
# 这里定义了 Celery 实例，并指定了任务模块
celery_app = Celery(
    "livecaptions",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["backend.worker.tasks"] # 包含任务模块
)

# 可选配置优化
# 提高任务处理效率和可靠性
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=CELERY_TIMEZONE,
    enable_utc=True,
    worker_prefetch_multiplier=1, # 对于长时间运行的任务 (ASR, LLM)，设置为 1 可以避免任务堆积
    task_acks_late=True, # 任务执行完成后再发送确认信号，防止崩溃导致任务丢失
    task_reject_on_worker_lost=True, # 如果 Worker 进程丢失，将任务重新放回队列
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=3,
    broker_transport_options = {
        "visibility_timeout": 3600,
        "socket_timeout": 5,
        "retry_policy": {
            "interval_start": 0,
            "interval_step": 1,
            "interval_max": 5,
            "max_retries": 3,
        },
    }
)
