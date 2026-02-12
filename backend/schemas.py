from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

# 任务状态枚举 (Schema 用)
class TaskStatus(str, Enum):
    """
    任务状态枚举
    """
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskBase(BaseModel):
    """
    任务基础 Schema
    包含创建和更新任务时所需的公共字段。
    """
    video_path: Optional[str] = None
    source_language: str = "auto"
    target_language: str = "zh"

class TaskCreate(TaskBase):
    """
    创建任务时的请求体 Schema
    """
    # 新增 LLM 配置字段
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = "gpt-4o"

class TaskUpdate(BaseModel):
    """
    更新任务时的请求体 Schema
    支持部分更新
    """
    status: Optional[TaskStatus] = None
    progress: Optional[float] = None
    current_step: Optional[str] = None
    logs: Optional[List[Any]] = None

class Task(TaskBase):
    """
    任务响应 Schema
    包含完整的任务信息，用于 API 返回。
    """
    id: str
    original_filename: Optional[str] = None
    status: TaskStatus
    progress: float
    current_step: str
    created_at: datetime
    updated_at: datetime
    logs: List[Any]
    task_metadata: Any
    # LLM 配置信息 (返回给前端时可能需要隐藏 API Key，这里简单起见先包含，但前端不展示 Key 比较安全)
    llm_config: Optional[Any] = None

    class Config:
        """
        Pydantic 配置
        orm_mode = True: 允许从 SQLAlchemy 模型创建 Pydantic 模型
        """
        orm_mode = True
