from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
from ..utils.file_ops import save_upload_file, ensure_directory
from ..worker.tasks import process_video_task
import os
import uuid
import shutil
from loguru import logger
from typing import Optional

router = APIRouter()
UPLOAD_DIR = "/data/uploads" # 默认上传目录

# 确保上传目录存在
ensure_directory(UPLOAD_DIR)

@router.post("/", response_model=schemas.Task, summary="创建新任务", description="上传文件或提供文件路径以创建新的字幕生成任务。")
async def create_task(
    # 使用 Form 参数，因为文件上传只能用 form-data
    file: Optional[UploadFile] = File(None, description="要上传的视频文件"),
    video_path: Optional[str] = Form(None, description="本地视频路径"),
    source_language: str = Form("auto", description="源语言"),
    target_language: str = Form("zh", description="目标语言"),
    api_key: Optional[str] = Form(None, description="OpenAI API Key (可选)"),
    base_url: Optional[str] = Form(None, description="OpenAI Base URL (可选)"),
    model: str = Form("gpt-4o", description="LLM 模型名称"),
    db: Session = Depends(get_db)
):
    """
    创建任务接口。

    参数:
    - file: 可选，上传的视频文件。
    - video_path: 可选，本地文件路径（如果直接挂载了本地目录）。
    - source_language: 源语言 (默认 auto)。
    - target_language: 目标语言 (默认 zh)。
    - api_key: LLM API Key (如果不填则尝试使用环境变量)。
    - base_url: LLM Base URL (如果不填则尝试使用环境变量)。

    返回:
    - Task: 创建的任务对象。
    """
    logger.info("收到创建任务请求")

    # 构造 TaskCreate 对象
    task_data_dict = {
        "source_language": source_language,
        "target_language": target_language,
        "api_key": api_key,
        "base_url": base_url,
        "model": model
    }

    if file:
        logger.info(f"处理文件上传: {file.filename}")
        # 获取文件扩展名
        file_ext = os.path.splitext(file.filename)[1]

        # 生成唯一文件名，防止重名覆盖
        task_id_placeholder = str(uuid.uuid4())
        safe_filename = f"{task_id_placeholder}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        # 保存文件到挂载目录
        save_upload_file(file, file_path)
        logger.info(f"文件保存至: {file_path}")

        task_data_dict["video_path"] = file_path

    elif video_path:
        logger.info(f"处理本地路径: {video_path}")
        # 验证文件是否存在
        if not os.path.exists(video_path):
             logger.error(f"文件未找到: {video_path}")
             raise HTTPException(status_code=400, detail=f"文件未找到: {video_path}")

        task_data_dict["video_path"] = video_path
    else:
        logger.error("未提供文件或路径")
        raise HTTPException(status_code=400, detail="必须上传文件或提供本地文件路径")

    # 创建 Pydantic 对象
    task_data = schemas.TaskCreate(**task_data_dict)

    # 调用 CRUD 创建任务
    db_task = crud.create_task(db=db, task=task_data)

    # 异步触发 Celery 任务
    process_video_task.delay(db_task.id)
    logger.info(f"Celery 任务已触发: {db_task.id}")

    return db_task


@router.get("/", response_model=list[schemas.Task], summary="获取任务列表", description="获取所有历史任务，按创建时间倒序排列。")
def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    获取任务列表接口 (分页)。
    """
    return crud.get_tasks(db, skip=skip, limit=limit)

@router.get("/{task_id}", response_model=schemas.Task, summary="获取任务详情", description="根据 ID 获取单个任务的详细信息，包括状态和日志。")
def read_task(task_id: str, db: Session = Depends(get_db)):
    """
    获取单个任务详情接口。
    """
    db_task = crud.get_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task

@router.post("/{task_id}/action", summary="任务操作", description="对任务执行操作，如暂停、恢复。")
def task_action(task_id: str, action: str, db: Session = Depends(get_db)):
    """
    任务操作接口。

    参数:
    - action: "pause" (暂停) 或 "resume" (恢复)
    """
    logger.info(f"收到任务操作请求: {task_id}, 动作: {action}")

    db_task = crud.get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if action == "pause":
        crud.update_task(db, task_id, {"status": models.TaskStatus.PAUSED})
        return {"message": "任务已暂停 (信号已发送)"}
    elif action == "resume":
        crud.update_task(db, task_id, {"status": models.TaskStatus.PENDING}) # 或者 PROCESSING，取决于具体逻辑
        return {"message": "任务已恢复 (信号已发送)"}

    raise HTTPException(status_code=400, detail="无效的操作指令")
