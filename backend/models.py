from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

class TaskStatus(str, enum.Enum):
    """
    任务状态枚举类
    """
    PENDING = "PENDING"     # 等待处理
    PROCESSING = "PROCESSING" # 正在处理
    PAUSED = "PAUSED"       # 已暂停
    COMPLETED = "COMPLETED" # 处理完成
    FAILED = "FAILED"       # 处理失败

class Task(Base):
    """
    任务数据模型
    存储视频处理任务的所有元数据和状态信息。
    """
    __tablename__ = "tasks"

    # 主键 ID (UUID 字符串)
    id = Column(String, primary_key=True, index=True, doc="任务唯一标识符 (UUID)")

    # 视频文件路径 (本地路径或挂载卷路径)
    video_path = Column(String, nullable=False, doc="视频源文件的绝对路径")

    # 原始文件名 (用于显示)
    original_filename = Column(String, nullable=True, doc="上传时的原始文件名")

    # 源语言 (默认为 auto，自动检测)
    source_language = Column(String, default="auto", doc="视频源语言代码 (如 'en', 'zh', 'auto')")

    # 目标语言 (默认为 zh，中文)
    target_language = Column(String, default="zh", doc="翻译目标语言代码 (如 'zh', 'en')")

    # 任务状态
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, doc="当前任务状态")

    # 进度百分比 (0.0 - 100.0)
    progress = Column(Float, default=0.0, doc="任务进度百分比")

    # 当前执行步骤描述
    current_step = Column(String, default="queued", doc="当前正在执行的步骤描述 (如 'ASR', 'Translation')")

    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow, doc="任务创建时间 (UTC)")

    # 更新时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, doc="任务最后更新时间 (UTC)")

    # 日志记录 (JSON 列表)
    # 用于存储前端显示的详细处理日志
    logs = Column(JSON, default=list, doc="任务处理日志列表")

    # 任务中间数据/元数据 (JSON 对象)
    # 用于存储各个步骤产生的中间结果，如 Whisper 识别结果、术语表等
    # 这允许任务中断后恢复，或用于调试
    task_metadata = Column(JSON, default=dict, doc="任务元数据存储 (包含各步骤中间结果)")
