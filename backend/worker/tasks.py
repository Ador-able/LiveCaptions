import os
import sys
import json
import gc
import torch
import time
import logging
from celery import Task
from sqlalchemy.orm import Session
from loguru import logger

from .celery_app import celery_app
from ..database import SessionLocal
from .. import crud, models
from ..config import RESULT_DIR
from ..utils.export import export_srt, export_vtt, export_ass
from ..services.audio import extract_audio, separate_vocals
from ..services.asr import get_asr_service
from ..services.alignment import get_alignment_service
from ..services.llm import LLMService

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)

logging.basicConfig()
logging.getLogger("faster_whisper").setLevel(logging.INFO)

def cleanup_gpu_memory():
    """清理GPU内存碎片"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.debug("GPU内存已清理")

# Celery Task Base Class
class LifecycleTask(Task):
    def before_start(self, task_id, args, kwargs):
        logger.info(f"Task {task_id} starting...")

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        logger.info(f"Task {task_id} finished with status {status}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")
        db = SessionLocal()
        try:
             crud.update_task_status(db, task_id, models.TaskStatus.FAILED)
             crud.append_log(db, task_id, f"Fatal error: {str(exc)}", "ERROR")
             
             # Record error message
             task = crud.get_task(db, task_id)
             if task:
                 task.error_message = str(exc)
                 db.add(task)
                 db.commit()
        finally:
            db.close()

@celery_app.task(bind=True, base=LifecycleTask, name="worker.process_video")
def process_video_task(self, task_id: str):
    db: Session = SessionLocal()
    try:
        process_video_logic(db, task_id)
    except Exception as e:
        logger.exception(f"Unhandled exception in process_video_task: {e}")
        # Re-raise to trigger on_failure
        raise e
    finally:
        db.close()

def process_video_logic(db: Session, task_id: str):
    """
    Main pipeline logic with checkpointing (resume capability).
    Refactored for workspace isolation and DB-first storage.
    """
    # SQLite 竞态条件处理：如果任务刚创建，Worker 还没能看到它，则重试几次
    max_retries = 5
    task_data = None
    for i in range(max_retries):
        task_data = crud.get_task(db, task_id)
        if task_data:
            break
        
        if i < max_retries - 1:
            logger.warning(f"Task {task_id} not found in DB, retrying ({i+1}/{max_retries})...")
            time.sleep(1)
            # 强制回滚会话，确保能读取到最新提交的数据（特别是 SQLite 事务隔离）
            db.rollback()
    
    if not task_data:
        raise ValueError(f"Task {task_id} not found in DB after {max_retries} retries")

    if task_data.status != models.TaskStatus.PROCESSING:
        crud.update_task_status(db, task_id, models.TaskStatus.PROCESSING)

    # ---------------------------------------------------------------------
    # Workspace Setup
    # ---------------------------------------------------------------------
    # Uploaded video might be in data/uploads or elsewhere.
    # We create a specific workspace for this task.
    task_work_dir = os.path.join(RESULT_DIR, task_id)
    
    if not os.path.exists(task_work_dir):
        os.makedirs(task_work_dir, exist_ok=True)
        # logger.info(f"Created workspace: {task_work_dir}")

    # Define paths
    video_path = task_data.video_path
    base_name = os.path.splitext(os.path.basename(task_data.video_path))[0]
    audio_output_path = os.path.join(task_work_dir, "audio_extracted.wav")
    
    # ---------------------------------------------------------------------
    # Step 1: Extract Audio
    # ---------------------------------------------------------------------
    if task_data.completed_step < 1:
        current_step = 1
        ensure_step(db, task_id, current_step, "开始提取音频...", level="INFO")
        try:
            if not os.path.exists(audio_output_path):
                 extract_audio(video_path, audio_output_path)
            ensure_step(db, task_id, current_step, "音频提取完成", level="SUCCESS")
        except Exception as e:
            ensure_step(db, task_id, current_step, f"音频提取失败: {str(e)}", level="ERROR")
            raise

    # ---------------------------------------------------------------------
    # Step 2: Separate Vocals (Demucs)
    # ---------------------------------------------------------------------
    vocals_path = audio_output_path
    
    if task_data.completed_step < 2:
        current_step = 2
        ensure_step(db, task_id, current_step, "开始人声分离 (Demucs)...", level="INFO")
        try:
            # Output dir for Demucs (inside workspace)
            demucs_output_dir = task_work_dir
            
            # This function returns the path to the vocals.wav
            # It usually creates htdemucs/model_name/vocals.wav inside output_dir
            vocals_path = separate_vocals(audio_output_path, demucs_output_dir)
            
            ensure_step(db, task_id, current_step, "人声分离完成", level="SUCCESS")
        except Exception as e:
            ensure_step(db, task_id, current_step, f"人声分离失败: {str(e)}", level="ERROR")
            raise
    else:
        # Try to locate existing vocals file if step finished
        # Heuristic: search in htdemucs subdir
        found = False
        for root, dirs, files in os.walk(task_work_dir):
            if "vocals.wav" in files:
                vocals_path = os.path.join(root, "vocals.wav")
                found = True
                break
        
        if not found:
             logger.warning("Vocals file missing despite step completion. Using extracted audio.")
             vocals_path = audio_output_path

    # ---------------------------------------------------------------------
    # Step 3: ASR (Faster-Whisper)
    # ---------------------------------------------------------------------
    asr_json_path = os.path.join(task_work_dir, "asr_segments.json")
    segments = []
    
    if task_data.completed_step < 3:
        current_step = 3
        ensure_step(db, task_id, current_step, "开始 ASR 语音识别...", level="INFO")
        try:
            ensure_step(db, task_id, current_step, f"正在加载 ASR 模型 (模型: {task_data.model})...", level="INFO")
            asr_service = get_asr_service(model=task_data.model)
            
            last_logged_progress = 0
            def asr_progress_callback(progress: float):
                nonlocal last_logged_progress
                progress_pct = int(progress * 100)
                if progress_pct - last_logged_progress >= 10:
                    last_logged_progress = progress_pct
                    ensure_step(db, task_id, current_step, f"ASR 识别进度: {progress_pct}%", level="INFO")
                    logger.info(f"ASR 识别进度: {progress_pct}%")
            
            asr_result, detected_language = asr_service.transcribe(
                vocals_path, 
                progress_callback=asr_progress_callback,
                use_word_timestamps=task_data.use_word_timestamps
            )
            segments = asr_result

            # Serialize locally
            with open(asr_json_path, 'w', encoding='utf-8') as f:
                json.dump(segments, f, ensure_ascii=False)

            # Save to DB metadata
            crud.update_task_metadata(db, task_id, {
                "detected_language": detected_language,
                "asr_segments": segments
            })

            try:
                asr_service.unload()
            except Exception as unload_err:
                logger.warning(f"ASR模型卸载时出错 (非致命,继续执行): {unload_err}")
            cleanup_gpu_memory()

            ensure_step(db, task_id, current_step, f"ASR 完成，检测语言: {detected_language}", level="SUCCESS")
        except Exception as e:
            ensure_step(db, task_id, current_step, f"ASR 失败: {str(e)}", level="ERROR")
            raise
    else:
        # Reload from DB or File
        task_data = crud.get_task(db, task_id)
        meta = task_data.task_metadata or {}
        if "asr_segments" in meta:
            segments = meta["asr_segments"]
        elif os.path.exists(asr_json_path):
             with open(asr_json_path, 'r', encoding='utf-8') as f:
                 segments = json.load(f)
        else:
             raise RuntimeError("ASR data missing. Please restart task.")

    # ---------------------------------------------------------------------
    # Step 4: Compliance Check with Timestamp Optimization
    # ---------------------------------------------------------------------
    compliant_json_path = os.path.join(task_work_dir, "compliant_segments.json")
    compliant_segments = []

    if task_data.completed_step < 4:
        current_step = 4
        ensure_step(db, task_id, current_step, "执行合规性检查与时间戳优化...", level="INFO")
        try:
            align_service = get_alignment_service()
            source_lang = "en" 
            if task_data.task_metadata and "detected_language" in task_data.task_metadata:
                source_lang = task_data.task_metadata["detected_language"]
            elif task_data.source_language and task_data.source_language != "auto":
                source_lang = task_data.source_language
            
            compliant_segments = align_service.check_netflix_compliance(
                segments, 
                lang=source_lang,
                use_word_timestamps=task_data.use_word_timestamps
            )
            
            with open(compliant_json_path, 'w', encoding='utf-8') as f:
                 json.dump(compliant_segments, f, ensure_ascii=False)

            # Save to DB
            crud.update_task_metadata(db, task_id, {
                "compliant_segments": compliant_segments
            })

            ensure_step(db, task_id, current_step, "合规性检查与时间戳优化完成", level="SUCCESS")
        except Exception as e:
            ensure_step(db, task_id, current_step, f"合规检查失败: {str(e)}", level="ERROR")
            raise
    else:
        task_data = crud.get_task(db, task_id)
        meta = task_data.task_metadata or {}
        if "compliant_segments" in meta:
             compliant_segments = meta["compliant_segments"]
        elif os.path.exists(compliant_json_path):
            with open(compliant_json_path, 'r', encoding='utf-8') as f:
                compliant_segments = json.load(f)

    # ---------------------------------------------------------------------
    # Step 5: Translation (LLM)
    # ---------------------------------------------------------------------
    translated_json_path = os.path.join(task_work_dir, "translated_segments.json")
    final_segments = []

    if task_data.completed_step < 5:
        current_step = 5
        ensure_step(db, task_id, current_step, "开始 LLM 滑窗三步翻译...", level="INFO")
        try:
            config = task_data.llm_config or {}
            llm_service = LLMService(
                api_key=config.get("api_key"),
                base_url=config.get("base_url"),
                model=config.get("model")
            )
            
            source_lang = "en"
            if task_data.task_metadata and "detected_language" in task_data.task_metadata:
                source_lang = task_data.task_metadata["detected_language"]
            
            last_logged_block = 0
            def llm_progress_callback(block_idx: int, total_blocks: int):
                nonlocal last_logged_block
                if block_idx - last_logged_block >= 1 or block_idx == total_blocks:
                    last_logged_block = block_idx
                    progress_pct = int((block_idx / total_blocks) * 100)
                    ensure_step(db, task_id, current_step, f"LLM 翻译进度: {progress_pct}% ({block_idx}/{total_blocks})", level="INFO")
                    logger.info(f"LLM 翻译进度: {progress_pct}% ({block_idx}/{total_blocks})")
            
            final_segments = llm_service.translate_full_text(
                compliant_segments, 
                source_lang=source_lang, 
                target_lang=task_data.target_language,
                video_description=getattr(task_data, 'video_description', ''),
                progress_callback=llm_progress_callback
            )
            
            with open(translated_json_path, 'w', encoding='utf-8') as f:
                json.dump(final_segments, f, ensure_ascii=False)

            # Save to metadata
            crud.update_task_metadata(db, task_id, {
                "translated_segments": final_segments
            })

            ensure_step(db, task_id, current_step, "翻译完成", level="SUCCESS")
        except Exception as e:
            ensure_step(db, task_id, current_step, f"翻译失败: {str(e)}", level="ERROR")
            raise
    else:
        task_data = crud.get_task(db, task_id)
        meta = task_data.task_metadata or {}
        if "translated_segments" in meta:
            final_segments = meta["translated_segments"]
        elif os.path.exists(translated_json_path):
            with open(translated_json_path, 'r', encoding='utf-8') as f:
                final_segments = json.load(f)

    # ---------------------------------------------------------------------
    # Step 6: Auto-save subtitles (if enabled)
    # ---------------------------------------------------------------------
    if task_data.auto_save_subtitle:
        current_step = 6
        ensure_step(db, task_id, current_step, "正在自动保存字幕到视频文件夹...", level="INFO")
        try:
            video_dir = os.path.dirname(task_data.video_path)
            base_name = os.path.splitext(os.path.basename(task_data.video_path))[0]
            lang_map = {
                'zh': 'cn',
                'en': 'en',
                'ja': 'ja',
                'ko': 'ko'
            }
            target_lang_code = lang_map.get(task_data.target_language, task_data.target_language)
            
            subtitle_formats = [
                ('srt', export_srt),
                ('vtt', export_vtt),
                ('ass', export_ass)
            ]
            
            saved_files = []
            for fmt, exporter in subtitle_formats:
                subtitle_filename = f"{base_name}.{target_lang_code}.default.{fmt}"
                subtitle_path = os.path.join(video_dir, subtitle_filename)
                try:
                    content = exporter(final_segments)
                    with open(subtitle_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    saved_files.append(subtitle_path)
                    logger.info(f"字幕已保存至: {subtitle_path}")
                except Exception as e:
                    logger.warning(f"保存 {fmt} 字幕失败: {e}")
            
            if saved_files:
                ensure_step(db, task_id, current_step, f"字幕已自动保存: {', '.join(saved_files)}", level="SUCCESS")
            else:
                ensure_step(db, task_id, current_step, "字幕自动保存失败", level="WARNING")
        except Exception as e:
            logger.error(f"自动保存字幕过程中出错: {e}")
            ensure_step(db, task_id, current_step, f"字幕自动保存过程出错: {str(e)}", level="WARNING")
    
    # ---------------------------------------------------------------------
    # Step 7: Cleanup (Files -> DB)
    # ---------------------------------------------------------------------
    # We NO LONGER generate subtitle files to disk.
    # Download endpoint will generate them on-the-fly from Metadata.
    
    current_step = 7 if task_data.auto_save_subtitle else 6
    ensure_step(db, task_id, current_step, "正在清理工作区...", level="INFO")
    
    try:
        # Cleanup Workspace
        # if os.path.exists(task_work_dir):
        #     shutil.rmtree(task_work_dir)
        #     logger.info(f"Cleaned up workspace: {task_work_dir}")
        
        # 为了支持"从指定步骤重新执行"，不再自动清理工作区文件
        logger.info(f"Task completed. Workspace preserved at: {task_work_dir}")
        ensure_step(db, task_id, current_step, "任务完成 (文件已保留)", level="SUCCESS")
    except Exception as e:
         logger.warning(f"Cleanup step failed: {e}")
         ensure_step(db, task_id, current_step, "任务完成 (有警告)", level="SUCCESS")

    # Finish
    crud.update_task_status(db, task_id, models.TaskStatus.COMPLETED)
    crud.append_log(db, task_id, "任务圆满完成！", "SUCCESS")

def ensure_step(db: Session, task_id: str, step_index: int, message: str, level: str = "INFO"):
    """
    Update step progress and log.
    Only updates 'completed_step' when level is SUCCESS.
    """
    # Calculate progress percentage (0-100)
    # Using 6 steps total now
    progress = int(((step_index - 1) / 6.0) * 100)
    if level == "SUCCESS":
        progress = int((step_index / 6.0) * 100)

    # First append log so it's included in any status snapshot
    crud.append_log(db, task_id, message, level)
    
    # When SUCCESS, update completed_step BEFORE broadcasting so the
    # WebSocket message contains the latest completed_step value.
    if level == "SUCCESS":
        db_task = crud.get_task(db, task_id)
        if db_task:
            if db_task.completed_step < step_index:
                db_task.completed_step = step_index
                db.add(db_task)
                db.commit()
    
    # Then update progress (which triggers status broadcast via WebSocket)
    crud.update_task_progress(db, task_id, progress=float(progress), current_step=f"Step {step_index}")
