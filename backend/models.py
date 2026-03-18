from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Enum, JSON, Boolean
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

    # LLM 配置 (新增)
    # 存储本次任务使用的 LLM API Key 和 Base URL
    llm_config = Column(JSON, default=dict, doc="LLM 配置 (api_key, base_url)")

    # 错误日志
    error_message = Column(Text, nullable=True, doc="任务失败时的错误信息")

    # 结果文件路径集合
    result_files = Column(JSON, default=dict, doc="生成的结果文件路径 (srt, vtt, ass)")

    # 已完成步骤 (用于断点续传)
    # 0: Init, 1: Audio, 2: Vocals, 3: ASR, 4: Compliance, 5: Terms, 6: Trans, 7: Cleanup
    completed_step = Column(Integer, default=0, doc="已完成的步骤索引")

    # 视频简介，用于提升翻译质量
    video_description = Column(Text, nullable=True, doc="视频简介/背景信息")
    
    # 自动保存字幕选项
    auto_save_subtitle = Column(Boolean, default=True, doc="字幕生成后是否自动保存至视频文件夹")
    
    # ASR 词时间戳选项
    use_word_timestamps = Column(Boolean, default=True, doc="ASR 是否使用词时间戳 (True: 词时间戳, False: 句时间戳)")
