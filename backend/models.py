from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    video_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    source_language = Column(String, default="auto")
    target_language = Column(String, default="zh")
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    progress = Column(Float, default=0.0)
    current_step = Column(String, default="queued")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Store logs as a JSON list of strings or objects
    logs = Column(JSON, default=list)

    # Store intermediate results/checkpoints
    # metadata is reserved in sqlalchemy, so we use task_metadata
    task_metadata = Column(JSON, default=dict)
