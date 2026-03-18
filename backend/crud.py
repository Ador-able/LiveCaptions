from sqlalchemy.orm import Session
from typing import Any, List, Dict, Optional
from . import models, schemas
import uuid
from datetime import datetime
from loguru import logger
import copy
import json
from .redis_client import sync_redis

def get_task(db: Session, task_id: str):
    """
    根据任务 ID 获取单个任务信息。
    """
    logger.debug(f"Fetching task with ID: {task_id}")
    return db.query(models.Task).filter(models.Task.id == task_id).first()

def _publish_task_update(task: models.Task):
    """
    内部辅助函数：将任务状态发布到 Redis
    """
    try:
        task_id_str = str(task.id)
        msg = {
            "task_id": task_id_str,
            "type": "status",
            "data": {
                "id": task_id_str,
                "status": task.status.value if hasattr(task.status, 'value') else task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "completed_step": task.completed_step,
                "updated_at": task.updated_at.isoformat() + "Z" if task.updated_at else datetime.utcnow().isoformat() + "Z",
                "result_files": task.result_files,
                "video_path": task.video_path,
                "created_at": task.created_at.isoformat() + "Z" if task.created_at else datetime.utcnow().isoformat() + "Z",
                "error_message": task.error_message,
                "original_filename": task.original_filename,
                "source_language": task.source_language,
                "target_language": task.target_language,
                "logs": task.logs or []
            }
        }
        sync_redis.publish("task_updates", json.dumps(msg))
    except Exception as e:
        logger.error(f"Failed to publish task update to Redis: {e}")

def get_tasks(db: Session, skip: int = 0, limit: int = 100):
    """
    获取任务列表 (分页)。
    """
    logger.debug(f"Fetching tasks list (skip={skip}, limit={limit})")
    return db.query(models.Task).order_by(models.Task.created_at.desc()).offset(skip).limit(limit).all()

def create_task(db: Session, task: schemas.TaskCreate):
    """
    创建一个新的任务并保存到数据库。
    """
    logger.info(f"Creating new task for file: {task.video_path} (src={task.source_language}, tgt={task.target_language})")

    # 使用 UUID 作为任务 ID
    new_task_id = str(uuid.uuid4())

    # 提取 LLM 配置
    llm_config = {
        "api_key": task.api_key,
        "base_url": task.base_url,
        "model": task.model
    }

    db_task = models.Task(
        id=new_task_id,
        video_path=task.video_path,
        source_language=task.source_language,
        target_language=task.target_language,
        status=models.TaskStatus.PENDING,
        progress=0.0,
        current_step="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        llm_config=llm_config, # 存储 LLM 配置
        video_description=task.video_description,
        auto_save_subtitle=task.auto_save_subtitle
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    logger.info(f"Task created successfully. ID: {db_task.id}")
    return db_task

def update_task(db: Session, task_id: str, updates: dict):
    """
    更新任务信息。
    支持部分更新 (字典格式)。
    """
    db_task = get_task(db, task_id)
    if db_task:
        for key, value in updates.items():
            # 特殊处理状态字段，确保其为枚举值
            if key == "status" and isinstance(value, str):
                try:
                    value = models.TaskStatus(value.upper())
                except ValueError:
                    logger.error(f"Invalid status string in update_task: {value}")
                    raise
            setattr(db_task, key, value)
        db_task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_task)
        logger.debug(f"Task {task_id} updated: {updates}")
        
        # 发布更新到 Redis
        _publish_task_update(db_task)
    else:
        logger.warning(f"Task {task_id} not found during update.")
    return db_task

def delete_task(db: Session, task_id: str):
    """
    删除任务。
    """
    db_task = get_task(db, task_id)
    if db_task:
        db.delete(db_task)
        db.commit()
        logger.info(f"Task {task_id} deleted.")
        return True
    return False

def append_log(db: Session, task_id: str, message: str, level: str = "INFO"):
    """
    向任务日志追加一条记录。
    """
    db_task = get_task(db, task_id)
    if not db_task:
        return

    new_log = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "message": message,
        "step": db_task.current_step
    }
    
    # SQLAlchemy JSON 字段追加需要重新赋值一个新的对象才能触发更新
    current_logs = list(db_task.logs) if db_task.logs else []
    current_logs.append(new_log)
    db_task.logs = copy.deepcopy(current_logs)
    db.commit()
    
    # 发布日志到 Redis
    msg = {
        "task_id": task_id,
        "type": "log",
        "data": new_log
    }
    sync_redis.publish("task_updates", json.dumps(msg))


def update_task_metadata(db: Session, task_id: str, metadata_update: dict):
    """
    更新任务的元数据 (JSON 字段)。
    使用 deepcopy 确保 SQLAlchemy 能够识别到字典内部的变化并触发数据库更新。
    """
    db_task = get_task(db, task_id)
    if not db_task:
        return None
    
    current_meta = dict(db_task.task_metadata) if db_task.task_metadata else {}
    current_meta.update(metadata_update)
    
    db_task.task_metadata = copy.deepcopy(current_meta)
    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    
    # 发布更新
    _publish_task_update(db_task)
    return db_task
    
def update_task_status(db: Session, task_id: str, new_status: models.TaskStatus):
    """
    更新任务主要状态 (使用 models.TaskStatus 枚举)
    """
    db_task = get_task(db, task_id)
    if not db_task:
        return None
        
    # 强制将字符串转换为枚举 (如果由于某种原因传入了字符串)
    if isinstance(new_status, str):
        try:
            new_status = models.TaskStatus(new_status.upper())
        except ValueError:
            logger.error(f"Invalid status string: {new_status}")
            raise
        
    db_task.status = new_status
    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    
    # 发布更新
    _publish_task_update(db_task)
    return db_task

def update_task_progress(db: Session, task_id: str, progress: float, current_step: str = None):
    """
    更新任务进度和当前步骤描述
    """
    db_task = get_task(db, task_id)
    if not db_task:
        return None
    
    db_task.progress = progress
    if current_step:
        db_task.current_step = current_step
        
    db_task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    
    # 发布更新
    _publish_task_update(db_task)
    return db_task

def cleanup_stuck_tasks(db: Session) -> List[str]:
    """
    清理在处理中（PROCESSING）但 Worker 可能已离线的任务。
    将它们重置为 PENDING，并返回这些任务的 ID 列表。
    """
    stuck_tasks = db.query(models.Task).filter(models.Task.status == models.TaskStatus.PROCESSING).all()
    if not stuck_tasks:
        return []
        
    logger.info(f"Checking for stuck tasks. Found {len(stuck_tasks)} tasks in PROCESSING state.")
    
    reset_ids = []
    for task in stuck_tasks:
        logger.info(f"Resetting stuck task: {task.id}")
        task.status = models.TaskStatus.PENDING
        reset_ids.append(task.id)
        
        # 追加一条自动恢复的日志
        append_log(db, task.id, "检测到系统重启，正在尝试自动恢复任务...", "WARNING")
        
        # 发布更新
        _publish_task_update(task)
        
    db.commit()
    logger.info(f"Stuck tasks cleanup completed. {len(reset_ids)} tasks reset.")
    return reset_ids

