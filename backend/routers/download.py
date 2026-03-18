from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
from ..services.alignment import get_alignment_service
from fastapi.responses import PlainTextResponse
import os
import json

router = APIRouter()

@router.get("/tasks/{task_id}/download/{format}", response_class=PlainTextResponse, summary="下载字幕文件", description="根据任务 ID 和指定格式下载生成的字幕文件。")
def download_subtitle(
    task_id: str = Path(..., description="任务唯一标识符 (UUID)"), 
    format: str = Path(..., description="导出的字幕格式: 'srt', 'vtt', 'ass'"), 
    db: Session = Depends(get_db)
):
    """
    下载字幕文件。
    支持格式: srt, vtt, ass
    直接从数据库 task_metadata 读取数据动态生成，不依赖磁盘文件。
    """
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 从 metadata 读取
    metadata = task.task_metadata or {}
    segments = metadata.get("translated_segments") or metadata.get("compliant_segments")

    if not segments:
         raise HTTPException(status_code=404, detail="No segments found (Task might be processing or failed)")

    alignment_service = get_alignment_service()

    if format == "srt":
        content = alignment_service.to_srt(segments)
        filename = f"{task.id}.srt"
    elif format == "vtt":
        content = alignment_service.to_vtt(segments)
        filename = f"{task.id}.vtt"
    elif format == "ass":
        content = alignment_service.to_ass(segments)
        filename = f"{task.id}.ass"
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")
        
    # Add Content-Disposition header to force download
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"'
    }
    return PlainTextResponse(content=content, headers=headers)
