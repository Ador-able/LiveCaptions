from .celery_app import celery_app
from ..database import SessionLocal, get_db
from .. import crud, models
from ..services.audio import extract_audio, separate_vocals
from ..services.asr import get_asr_service
from ..services.alignment import get_alignment_service
from ..services.llm import LLMService
import time
import os
import shutil
from sqlalchemy.orm import Session
from datetime import datetime
from loguru import logger

# 数据库会话依赖 (用于 worker 内部)
def get_db_session():
    """
    获取独立的数据库会话，供 worker 使用。
    Celery worker 运行在不同进程中，无法直接使用 FastAPI 的 Depends。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_interrupt(task_id: str, db: Session) -> bool:
    """
    检查任务是否被用户暂停或中断。

    参数:
        task_id: 任务 ID
        db: 数据库会话

    返回:
        bool: 如果需要中断 (已暂停/已取消)，返回 True。
    """
    # 强制从数据库刷新状态
    db.expire_all()
    task = crud.get_task(db, task_id)
    if task and task.status == models.TaskStatus.PAUSED:
        logger.info(f"任务 {task_id} 已被用户暂停。")
        return True
    return False

# 步骤 1: 音频预处理 (Demucs / VAD)
def step_audio_preprocessing(task_id: str, db: Session, video_path: str):
    logger.info(f"任务 {task_id}: 开始音频预处理...")

    # 准备输出目录
    task_dir = os.path.dirname(video_path)
    audio_output = os.path.join(task_dir, "audio_original.wav")

    # 提取音频
    if not os.path.exists(audio_output):
        extract_audio(video_path, audio_output)

    # 人声分离 (Demucs)
    # 分离结果将位于 task_dir/htdemucs/...
    try:
        vocals_path = separate_vocals(audio_output, task_dir)
        # 更新任务元数据，保存人声路径
        task = crud.get_task(db, task_id)
        metadata = dict(task.task_metadata or {})
        metadata["vocals_path"] = vocals_path
        metadata["original_audio_path"] = audio_output
        crud.update_task(db, task_id, {
            "progress": 20.0,
            "current_step": "音频预处理完成",
            "task_metadata": metadata
        })
    except Exception as e:
        logger.error(f"人声分离失败: {e}")
        raise e

# 步骤 2: ASR 识别与说话人分离 (Whisper)
def step_asr_diarization(task_id: str, db: Session):
    logger.info(f"任务 {task_id}: 开始 ASR 识别...")

    task = crud.get_task(db, task_id)
    metadata = task.task_metadata or {}
    vocals_path = metadata.get("vocals_path")

    if not vocals_path or not os.path.exists(vocals_path):
        raise FileNotFoundError("未找到人声分离后的音频文件")

    asr_service = get_asr_service()
    # 使用源语言进行转写，如果未指定则自动检测
    segments, detected_lang = asr_service.transcribe(vocals_path, language=task.source_language if task.source_language != "auto" else None)

    # 保存 Whisper 原始结果
    metadata["asr_segments"] = segments
    metadata["detected_language"] = detected_lang

    crud.update_task(db, task_id, {
        "progress": 40.0,
        "current_step": "ASR 识别完成",
        "task_metadata": metadata,
        # 如果源语言是 auto，更新为检测到的语言
        "source_language": detected_lang if task.source_language == "auto" else task.source_language
    })

# 步骤 3: 字幕对齐与清洗 (Netflix 标准检查)
def step_alignment_cleaning(task_id: str, db: Session):
    logger.info(f"任务 {task_id}: 开始字幕对齐与清洗...")

    task = crud.get_task(db, task_id)
    metadata = task.task_metadata or {}
    segments = metadata.get("asr_segments", [])

    alignment_service = get_alignment_service()
    compliant_segments = alignment_service.check_netflix_compliance(segments)

    metadata["compliant_segments"] = compliant_segments

    crud.update_task(db, task_id, {
        "progress": 50.0,
        "current_step": "对齐与清洗完成",
        "task_metadata": metadata
    })

# 步骤 4: 术语提取 (LLM)
def step_terminology_extraction(task_id: str, db: Session):
    logger.info(f"任务 {task_id}: 开始术语提取...")

    task = crud.get_task(db, task_id)
    metadata = task.task_metadata or {}
    segments = metadata.get("compliant_segments", [])

    # 将所有文本合并，用于术语提取
    full_text = "\n".join([s["text"] for s in segments])

    llm_service = LLMService()
    terminology_json = llm_service.extract_terminology(full_text, task.source_language, task.target_language)

    metadata["terminology"] = terminology_json

    crud.update_task(db, task_id, {
        "progress": 60.0,
        "current_step": "术语提取完成",
        "task_metadata": metadata
    })

# 步骤 5: 三步翻译 (LLM)
def step_translation(task_id: str, db: Session):
    logger.info(f"任务 {task_id}: 开始三步翻译流程...")

    task = crud.get_task(db, task_id)
    metadata = task.task_metadata or {}
    segments = metadata.get("compliant_segments", [])
    terminology = metadata.get("terminology", "[]")

    llm_service = LLMService()

    translated_segments = []
    total_segments = len(segments)

    # 逐句或逐批翻译
    # 为了演示，这里逐句翻译。实际生产中应按上下文窗口批量处理 (Context Window Batching)
    for i, segment in enumerate(segments):
        source_text = segment["text"]
        translated_text = llm_service.three_step_translation(
            source_text,
            task.source_language,
            task.target_language,
            terminology
        )

        new_segment = segment.copy()
        new_segment["text"] = translated_text
        new_segment["original_text"] = source_text
        translated_segments.append(new_segment)

        # 更新进度 (60% -> 90%)
        current_progress = 60.0 + (30.0 * (i + 1) / total_segments)
        # 每 10% 更新一次数据库，避免过于频繁
        if i % max(1, total_segments // 10) == 0:
            crud.update_task(db, task_id, {"progress": current_progress})

    metadata["translated_segments"] = translated_segments

    crud.update_task(db, task_id, {
        "progress": 90.0,
        "current_step": "翻译完成",
        "task_metadata": metadata
    })

@celery_app.task(bind=True, name="backend.worker.tasks.process_video_task")
def process_video_task(self, task_id: str):
    """
    视频处理的主工作流任务。
    由 Celery Worker 执行。
    """
    db = SessionLocal()
    try:
        # 获取任务信息
        task = crud.get_task(db, task_id)
        if not task:
            logger.error(f"任务 {task_id} 未找到，无法开始处理。")
            return

        # 更新状态为处理中
        logger.info(f"正在处理任务: {task_id}")
        crud.update_task(db, task_id, {"status": models.TaskStatus.PROCESSING, "progress": 0.0})

        # 主处理管线
        try:
            # 1. 音频预处理
            if check_interrupt(task_id, db): return
            step_audio_preprocessing(task_id, db, task.video_path)

            # 2. ASR & 说话人分离
            if check_interrupt(task_id, db): return
            step_asr_diarization(task_id, db)

            # 3. 对齐与清洗
            if check_interrupt(task_id, db): return
            step_alignment_cleaning(task_id, db)

            # 4. 术语提取
            if check_interrupt(task_id, db): return
            step_terminology_extraction(task_id, db)

            # 5. 翻译
            if check_interrupt(task_id, db): return
            step_translation(task_id, db)

            # 完成
            if check_interrupt(task_id, db): return
            logger.info(f"任务 {task_id} 处理完成。")
            crud.update_task(db, task_id, {"status": models.TaskStatus.COMPLETED, "progress": 100.0, "current_step": "完成"})

        except Exception as e:
            # 捕获所有异常并记录日志
            logger.exception(f"任务 {task_id} 处理失败: {e}")

            # 将错误信息写入任务日志
            current_task = crud.get_task(db, task_id)
            if current_task:
                current_logs = current_task.logs or []
                if not isinstance(current_logs, list):
                     current_logs = []
                current_logs.append(f"错误: {str(e)}")

                crud.update_task(db, task_id, {
                    "status": models.TaskStatus.FAILED,
                    "logs": current_logs
                })
            # 重新抛出异常，让 Celery 知道任务失败 (用于重试或监控)
            raise e

    finally:
        # 确保关闭数据库连接
        db.close()
