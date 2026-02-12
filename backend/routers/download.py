from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
from ..services.alignment import get_alignment_service
from fastapi.responses import PlainTextResponse

router = APIRouter()

@router.get("/tasks/{task_id}/download/{format}", response_class=PlainTextResponse)
def download_subtitle(task_id: str, format: str, db: Session = Depends(get_db)):
    """
    下载字幕文件。
    支持格式: srt, vtt, ass
    (Adapted to use AlignmentService)
    """
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Allow downloading even if not fully completed? Ideally yes if segments exist.
    # But for safety, check if completed or partially done.
    # The logic checks for segments.
    metadata = task.task_metadata or {}
    segments = metadata.get("translated_segments") or metadata.get("compliant_segments")

    if not segments:
         raise HTTPException(status_code=404, detail="No segments found (Task might be processing)")

    alignment_service = get_alignment_service()

    if format == "srt":
        return alignment_service.to_srt(segments)
    elif format == "vtt":
        return alignment_service.to_vtt(segments)
    elif format == "ass":
        return alignment_service.to_ass(segments)
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
