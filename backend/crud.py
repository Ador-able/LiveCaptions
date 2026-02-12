from sqlalchemy.orm import Session
from . import models, schemas
import uuid
from datetime import datetime
from loguru import logger

def get_task(db: Session, task_id: str):
    """
    根据任务 ID 获取单个任务信息。
    """
    logger.debug(f"Fetching task with ID: {task_id}")
    return db.query(models.Task).filter(models.Task.id == task_id).first()

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

    db_task = models.Task(
        id=new_task_id,
        video_path=task.video_path,
        source_language=task.source_language,
        target_language=task.target_language,
        status=models.TaskStatus.PENDING,
        progress=0.0,
        current_step="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
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
            setattr(db_task, key, value)
        db_task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_task)
        logger.debug(f"Task {task_id} updated: {updates}")
    else:
        logger.warning(f"Task {task_id} not found during update.")
    return db_task
