from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TaskBase(BaseModel):
    video_path: Optional[str] = None
    source_language: str = "auto"
    target_language: str = "zh"

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    progress: Optional[float] = None
    current_step: Optional[str] = None
    logs: Optional[List[Any]] = None

class Task(TaskBase):
    id: str
    original_filename: Optional[str] = None
    status: TaskStatus
    progress: float
    current_step: str
    created_at: datetime
    updated_at: datetime
    logs: List[Any]
    task_metadata: Any

    class Config:
        orm_mode = True
