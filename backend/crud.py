from sqlalchemy.orm import Session
from . import models, schemas
import uuid
from datetime import datetime

def get_task(db: Session, task_id: str):
    return db.query(models.Task).filter(models.Task.id == task_id).first()

def get_tasks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Task).offset(skip).limit(limit).all()

def create_task(db: Session, task: schemas.TaskCreate):
    db_task = models.Task(
        id=str(uuid.uuid4()),
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
    return db_task

def update_task(db: Session, task_id: str, updates: dict):
    db_task = get_task(db, task_id)
    if db_task:
        for key, value in updates.items():
            setattr(db_task, key, value)
        db_task.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_task)
    return db_task
