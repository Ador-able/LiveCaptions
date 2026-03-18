from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
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
    video_path: Optional[str] = Field(None, description="视频源文件的绝对路径")
    source_language: str = Field("auto", description="视频源语言代码 (例如 'en', 'zh', 'auto')")
    target_language: str = Field("zh", description="翻译目标语言代码 (例如 'zh', 'en')")

class TaskCreate(TaskBase):
    """
    创建任务时的请求体 Schema
    """
    # 新增 LLM 配置字段
    api_key: Optional[str] = Field(None, description="LLM 服务 API 密钥")
    base_url: Optional[str] = Field(None, description="LLM 服务 API 基础地址")
    model: Optional[str] = Field(None, description="使用的 LLM 模型名称")
    
    # 视频简介字段
    video_description: Optional[str] = Field(None, description="视频简介/背景信息，用于提升翻译质量")
    
    # 自动保存字幕选项
    auto_save_subtitle: Optional[bool] = Field(True, description="字幕生成后是否自动保存至视频文件夹")
    
    # ASR 词时间戳选项
    use_word_timestamps: Optional[bool] = Field(True, description="ASR 是否使用词时间戳 (True: 词时间戳, False: 句时间戳)")

class TaskUpdate(BaseModel):
    """
    更新任务时的请求体 Schema
    支持部分更新
    """
    status: Optional[TaskStatus] = Field(None, description="任务当前状态")
    progress: Optional[float] = Field(None, description="任务处理进度 (0.0 - 1.0)")
    current_step: Optional[str] = Field(None, description="当前正在执行的步骤描述")
    logs: Optional[List[Any]] = Field(None, description="任务处理日志列表")

class Task(TaskBase):
    """
    任务响应 Schema
    包含完整的任务信息，用于 API 返回。
    """
    id: str = Field(..., description="任务唯一标识符 (UUID)")
    original_filename: Optional[str] = Field(None, description="上传时的原始文件名")
    status: TaskStatus = Field(..., description="任务当前状态")
    progress: float = Field(..., description="任务处理进度 (0.0 - 1.0)")
    current_step: str = Field(..., description="当前正在执行的步骤描述")
    completed_step: int = Field(0, description="已完成的步骤索引 (0-9)")
    created_at: datetime = Field(..., description="任务创建时间 (UTC)")
    updated_at: datetime = Field(..., description="任务最后更新时间 (UTC)")
    
    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def set_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v
    
    logs: List[Any] = Field(default_factory=list, description="任务详细处理日志记录")
    task_metadata: Any = Field(default_factory=dict, description="任务各步骤产生的中间元数据")
    
    # 新增字段
    result_files: Optional[Dict[str, str]] = Field(None, description="生成的结果文件路径映射 (srt, vtt, ass)")
    error_message: Optional[str] = Field(None, description="任务失败时的错误详细信息")
    
    # LLM 配置信息
    llm_config: Optional[Any] = Field(None, description="本次任务使用的 LLM 配置信息")
    video_description: Optional[str] = Field(None, description="视频简介/背景信息")
    auto_save_subtitle: Optional[bool] = Field(None, description="字幕生成后是否自动保存至视频文件夹")
    use_word_timestamps: Optional[bool] = Field(None, description="ASR 是否使用词时间戳 (True: 词时间戳, False: 句时间戳)")

    class Config:
        """
        Pydantic 配置
        from_attributes = True: 允许从 SQLAlchemy 模型创建 Pydantic 模型
        """
        from_attributes = True

