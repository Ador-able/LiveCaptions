from .celery_app import celery_app
from ..database import SessionLocal, get_db
from .. import crud, models
import time
from sqlalchemy.orm import Session
from datetime import datetime
from loguru import logger

# Dependency helper for Celery tasks (since they run outside request context)
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_interrupt(task_id: str, db: Session) -> bool:
    """
    Checks if the task has been paused or cancelled.
    Returns True if execution should stop.
    """
    # Force a refresh from DB to get latest status
    db.expire_all()
    task = crud.get_task(db, task_id)
    if task and task.status == models.TaskStatus.PAUSED:
        logger.info(f"Task {task_id} paused by user.")
        return True
    return False

# Placeholder functions for pipeline steps
def step_audio_preprocessing(task_id: str, db: Session):
    logger.info(f"Task {task_id}: Starting Audio Pre-processing...")
    # TODO: Implement Demucs / VAD
    time.sleep(2) # Simulate work
    crud.update_task(db, task_id, {"progress": 10.0, "current_step": "Audio Pre-processing"})

def step_asr_diarization(task_id: str, db: Session):
    logger.info(f"Task {task_id}: Starting ASR & Diarization...")
    # TODO: Implement Whisper / Pyannote
    time.sleep(2)
    crud.update_task(db, task_id, {"progress": 40.0, "current_step": "ASR & Diarization"})

def step_alignment_cleaning(task_id: str, db: Session):
    logger.info(f"Task {task_id}: Starting Alignment & Cleaning...")
    # TODO: Implement Alignment
    time.sleep(1)
    crud.update_task(db, task_id, {"progress": 50.0, "current_step": "Alignment & Cleaning"})

def step_terminology_extraction(task_id: str, db: Session):
    logger.info(f"Task {task_id}: Starting Terminology Extraction...")
    # TODO: Implement LLM Extraction
    time.sleep(1)
    crud.update_task(db, task_id, {"progress": 60.0, "current_step": "Terminology Extraction"})

def step_translation(task_id: str, db: Session):
    logger.info(f"Task {task_id}: Starting Translation...")
    # TODO: Implement 3-Step Translation
    time.sleep(3)
    crud.update_task(db, task_id, {"progress": 90.0, "current_step": "Translation"})

@celery_app.task(bind=True, name="backend.worker.tasks.process_video_task")
def process_video_task(self, task_id: str):
    """
    Main workflow task for video processing.
    """
    db = SessionLocal()
    try:
        task = crud.get_task(db, task_id)
        if not task:
            logger.error(f"Task {task_id} not found.")
            return

        # Update status to PROCESSING
        logger.info(f"Processing Task {task_id}")
        crud.update_task(db, task_id, {"status": models.TaskStatus.PROCESSING, "progress": 0.0})

        # Main Pipeline Steps
        try:
            # 1. Audio Pre-processing (Vocal Isolation, VAD)
            if check_interrupt(task_id, db): return
            step_audio_preprocessing(task_id, db)

            # Check for pause/interrupt
            if check_interrupt(task_id, db): return

            # 2. ASR & Diarization
            step_asr_diarization(task_id, db)

            if check_interrupt(task_id, db): return

            # 3. Alignment & Cleaning
            step_alignment_cleaning(task_id, db)

            if check_interrupt(task_id, db): return

            # 4. Terminology Extraction
            step_terminology_extraction(task_id, db)

            if check_interrupt(task_id, db): return

            # 5. Translation (3-Step)
            step_translation(task_id, db)

            if check_interrupt(task_id, db): return

            # Mark Completed
            crud.update_task(db, task_id, {"status": models.TaskStatus.COMPLETED, "progress": 100.0})

        except Exception as e:
            logger.exception(f"Task {task_id} failed: {e}")
            # Ensure task exists before logging error to it
            current_task = crud.get_task(db, task_id)
            if current_task:
                current_logs = current_task.logs or []
                if isinstance(current_logs, list):
                     current_logs.append(f"Error: {str(e)}")
                else:
                     current_logs = [f"Error: {str(e)}"]

                crud.update_task(db, task_id, {
                    "status": models.TaskStatus.FAILED,
                    "logs": current_logs
                })
            # Re-raise to let Celery know it failed (or handle retry logic)
            raise e

    finally:
        db.close()
