from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Path
from sqlalchemy.orm import Session
from .. import crud, models, schemas
from ..database import get_db
from ..utils.file_ops import save_upload_file, ensure_directory
from ..worker.tasks import process_video_task
from ..config import UPLOAD_DIR
import os
import uuid
import shutil
from loguru import logger
from typing import Optional

router = APIRouter()

# 确保上传目录存在
ensure_directory(UPLOAD_DIR)

@router.post("/", response_model=schemas.Task, summary="创建新任务", description="上传文件或提供文件路径以创建新的字幕生成任务。")
def create_task(
    # 使用 Form 参数，因为文件上传只能用 form-data
    file: Optional[UploadFile] = File(None, description="要上传的视频文件"),
    video_path: Optional[str] = Form(None, description="服务器本地视频路径"),
    source_language: str = Form("auto", description="视频源语言 (例如: 'en', 'zh', 'auto')"),
    target_language: str = Form("zh", description="翻译目标语言 (例如: 'zh', 'en')"),
    api_key: Optional[str] = Form(None, description="LLM 服务 API Key (可选，留空则使用全局配置)"),
    base_url: Optional[str] = Form(None, description="LLM 服务 API 基础地址 (可选)"),
    model: Optional[str] = Form(None, description="使用的 LLM 模型名称 (留空则使用环境变量配置)"),
    video_description: Optional[str] = Form(None, description="视频简介/背景信息 (可选，用于提升翻译质量)"),
    auto_save_subtitle: Optional[str] = Form("true", description="字幕生成后是否自动保存至视频文件夹"),
    use_word_timestamps: Optional[str] = Form("true", description="ASR 是否使用词时间戳 (True: 词时间戳, False: 句时间戳)"),
    db: Session = Depends(get_db)
):
    """
    创建任务接口。
    """
    logger.info("收到创建任务请求")
    
    try:
        # 构造 TaskCreate 对象
        auto_save_bool = auto_save_subtitle.lower() in ("true", "1", "yes", "y", "on")
        use_word_timestamps_bool = use_word_timestamps.lower() in ("true", "1", "yes", "y", "on")
        task_data_dict = {
            "source_language": source_language,
            "target_language": target_language,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "video_description": video_description,
            "auto_save_subtitle": auto_save_bool,
            "use_word_timestamps": use_word_timestamps_bool
        }

        if file:
            logger.info(f"处理文件上传: {file.filename}")
            # 生成唯一文件名
            task_id_placeholder = str(uuid.uuid4())
            safe_filename = f"{task_id_placeholder}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, safe_filename)

            # 保存文件
            try:
                 save_upload_file(file, file_path)
            except PermissionError:
                 logger.warning(f"无法访问目录 {UPLOAD_DIR}，退而使用本地 ./uploads 目录")
                 local_upload_dir = "./uploads"
                 ensure_directory(local_upload_dir)
                 file_path = os.path.join(local_upload_dir, safe_filename)
                 save_upload_file(file, file_path)

            logger.info(f"文件保存至: {file_path}")
            task_data_dict["video_path"] = file_path

        elif video_path:
            logger.info(f"处理本地路径: {video_path}")
            if not os.path.exists(video_path):
                 raise HTTPException(status_code=400, detail=f"文件未找到: {video_path}")
            task_data_dict["video_path"] = video_path
        else:
            raise HTTPException(status_code=400, detail="必须上传文件或提供本地文件路径")

        # 创建 Pydantic 对象
        task_data = schemas.TaskCreate(**task_data_dict)

        # 调用 CRUD 创建任务
        db_task = crud.create_task(db=db, task=task_data)

        # 异步触发 Celery 任务
        process_video_task.delay(db_task.id)
        logger.info(f"Celery 任务已触发: {db_task.id}")

        return db_task
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise

@router.get("/", response_model=list[schemas.Task], summary="获取任务列表", description="获取所有历史任务，按创建时间倒序排列。")
def read_tasks(
    skip: int = Query(0, description="跳过的记录数量 (分页使用)"), 
    limit: int = Query(100, description="返回的最大记录数量 (分页使用)"), 
    db: Session = Depends(get_db)
):
    return crud.get_tasks(db, skip=skip, limit=limit)

@router.get("/{task_id}", response_model=schemas.Task, summary="获取任务详情", description="根据 ID 获取单个任务的详细信息，包括状态和日志。")
def read_task(
    task_id: str = Path(..., description="任务唯一标识符 (UUID)"), 
    db: Session = Depends(get_db)
):
    db_task = crud.get_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="任务未找到")
    return db_task

@router.post("/{task_id}/retry", response_model=schemas.Task, summary="重试任务", description="重新开始处理失败或暂停的任务。")
def retry_task(
    task_id: str = Path(..., description="任务唯一标识符 (UUID)"), 
    db: Session = Depends(get_db)
):
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    # 重置任务进度，从头开始重试，清理所有旧日志和中间数据
    crud.update_task(db, task_id, {
        "status": models.TaskStatus.PENDING,
        "completed_step": 0,
        "progress": 0.0,
        "current_step": "queued",
        "error_message": None,
        "logs": [],
        "task_metadata": {}
    })
    crud.append_log(db, task_id, "用户请求重试。任务已重置，正在从头开始重新处理...", "INFO")
    
    # 重新触发 Celery 任务
    process_video_task.delay(task_id)
    
    return task

# 步骤号 -> 该步骤产生的 metadata key 映射
STEP_METADATA_KEYS: dict[int, list[str]] = {
    3: ["detected_language", "asr_segments"],
    4: ["compliant_segments"],
    5: ["translated_segments"],
}

@router.post("/{task_id}/restart-from-step", response_model=schemas.Task, summary="从指定步骤重新执行", description="将任务回退到指定步骤并重新执行，该步骤必须已经执行过。")
def restart_from_step(
    task_id: str = Path(..., description="任务唯一标识符 (UUID)"),
    step: int = Query(..., ge=1, le=6, description="要重新开始的步骤号 (1-6)"),
    db: Session = Depends(get_db)
):
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")

    if task.status == models.TaskStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="任务正在处理中，无法回退步骤")

    if task.completed_step < step:
        raise HTTPException(status_code=400, detail=f"步骤 {step} 尚未执行过 (当前已完成到步骤 {task.completed_step})")

    # 收集需要清除的 metadata key（从 step 到 6）
    keys_to_remove: list[str] = []
    for s in range(step, 7):
        keys_to_remove.extend(STEP_METADATA_KEYS.get(s, []))

    # 清理 metadata
    cleaned_metadata = dict(task.task_metadata) if task.task_metadata else {}
    for key in keys_to_remove:
        cleaned_metadata.pop(key, None)

    # 重置任务状态
    crud.update_task(db, task_id, {
        "status": models.TaskStatus.PENDING,
        "completed_step": step - 1,
        "progress": float(((step - 1) / 6.0) * 100),
        "current_step": "queued",
        "error_message": None,
        "logs": [],
        "task_metadata": cleaned_metadata
    })

    step_names = {1: "音频提取", 2: "人声分离", 3: "语音识别", 4: "合规检查与时间戳优化", 5: "智能翻译", 6: "清理工作区"}
    crud.append_log(db, task_id, f"用户请求从步骤 {step} ({step_names.get(step, '')}) 重新开始执行", "INFO")

    # 重新触发 Celery 任务
    process_video_task.delay(task_id)
    logger.info(f"Task {task_id} restart from step {step}")

    return crud.get_task(db, task_id)

@router.delete("/{task_id}", status_code=204, summary="删除任务", description="从数据库中删除任务记录及其相关文件。")
def delete_task(
    task_id: str = Path(..., description="任务唯一标识符 (UUID)"), 
    db: Session = Depends(get_db)
):
    """
    删除任务及其相关文件。
    """
    task = crud.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
        
    crud.delete_task(db, task_id)
    return None

@router.post("/{task_id}/action", summary="任务操作", description="对任务执行特定动作，如暂停、恢复。")
def task_action(
    task_id: str = Path(..., description="任务唯一标识符 (UUID)"), 
    action: str = Query(..., description="操作动作: 'pause' (暂停), 'resume' (恢复)"), 
    db: Session = Depends(get_db)
):
    logger.info(f"收到任务操作请求: {task_id}, 动作: {action}")

    db_task = crud.get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="任务未找到")

    if action == "pause":
        crud.update_task(db, task_id, {"status": models.TaskStatus.PAUSED})
        return {"message": "任务暂停指令已发送"}
    elif action == "resume":
        # 如果是 PENDING，说明可能是在队列中，或者是重启后卡在 PENDING
        # 强制更新为 PENDING 以触发 UI 状态统一（如果已经是 PENDING 也没关系）
        # 但我们需要确保任务真的重新投入了 Celery
        previous_status = db_task.status
        crud.update_task(db, task_id, {"status": models.TaskStatus.PENDING})
        
        # 记录操作
        crud.append_log(db, task_id, f"用户请求恢复任务。当前状态: {previous_status}", "INFO")

        # 触发 Celery 任务：除非它已经在处理中
        if previous_status != models.TaskStatus.PROCESSING and previous_status != models.TaskStatus.COMPLETED:
             logger.info(f"Re-triggering task {task_id} via resume action")
             process_video_task.delay(task_id)
        else:
             logger.warning(f"Task {task_id} is in {previous_status} state, skip re-triggering")

        return {"message": "任务恢复指令已发送"}

    raise HTTPException(status_code=400, detail="无效的操作指令")

