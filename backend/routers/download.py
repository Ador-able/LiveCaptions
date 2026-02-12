from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
from ..utils.export import export_srt, export_vtt, export_ass
from fastapi.responses import PlainTextResponse

router = APIRouter()

@router.get("/tasks/{task_id}/download/{format}", response_class=PlainTextResponse)
def download_subtitle(task_id: str, format: str, db: Session = Depends(get_db)):
    """
    下载字幕文件。
    支持格式: srt, vtt, ass
    """
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != models.TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task not completed yet")

    metadata = task.task_metadata or {}
    segments = metadata.get("translated_segments") or metadata.get("compliant_segments")

    if not segments:
         raise HTTPException(status_code=404, detail="No segments found")

    if format == "srt":
        return export_srt(segments)
    elif format == "vtt":
        return export_vtt(segments)
    elif format == "ass":
        return export_ass(segments, title=task.original_filename)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
