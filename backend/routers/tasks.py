from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
from ..utils.file_ops import save_upload_file, ensure_directory
import os
import uuid
import shutil

router = APIRouter()
UPLOAD_DIR = "/data/uploads"

ensure_directory(UPLOAD_DIR)

@router.post("/", response_model=schemas.Task)
async def create_task(
    file: UploadFile = File(None),
    video_path: str = None,
    source_language: str = "auto",
    target_language: str = "zh",
    db: Session = Depends(get_db)
):
    """
    Create a new task. Can upload a file OR provide a local path.
    """
    if file:
        file_ext = os.path.splitext(file.filename)[1]
        task_id = str(uuid.uuid4())
        # Preserve original filename but ensure uniqueness
        safe_filename = f"{task_id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        save_upload_file(file, file_path)

        task_data = schemas.TaskCreate(
            video_path=file_path,
            source_language=source_language,
            target_language=target_language
        )
        # Override the ID generated in crud to match the one used for file
        # Actually crud generates a new ID. Let's fix that or just let crud handle it.
        # It's cleaner to let crud handle ID generation, but we needed ID for filename.
        # We can update the task record later if needed, or just let the file have a random UUID prefix.

        # To keep it simple: we already saved the file.
        # Now create the DB entry.
        return crud.create_task(db=db, task=task_data)

    elif video_path:
        if not os.path.exists(video_path):
             raise HTTPException(status_code=400, detail=f"File not found at path: {video_path}")

        task_data = schemas.TaskCreate(
            video_path=video_path,
            source_language=source_language,
            target_language=target_language
        )
        return crud.create_task(db=db, task=task_data)
    else:
        raise HTTPException(status_code=400, detail="Either file upload or video_path is required")


@router.get("/", response_model=list[schemas.Task])
def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_tasks(db, skip=skip, limit=limit)

@router.get("/{task_id}", response_model=schemas.Task)
def read_task(task_id: str, db: Session = Depends(get_db)):
    db_task = crud.get_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task

@router.post("/{task_id}/action")
def task_action(task_id: str, action: str, db: Session = Depends(get_db)):
    # Placeholder for pause/resume logic
    db_task = crud.get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if action == "pause":
        crud.update_task(db, task_id, {"status": models.TaskStatus.PAUSED})
        return {"message": "Task paused (signal sent)"}
    elif action == "resume":
        crud.update_task(db, task_id, {"status": models.TaskStatus.PENDING}) # Or PROCESSING
        return {"message": "Task resumed (signal sent)"}

    raise HTTPException(status_code=400, detail="Invalid action")
