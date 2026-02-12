import os
import shutil
import traceback
from celery import Task
from sqlalchemy.orm import Session
from loguru import logger
from datetime import datetime

from .celery_app import celery_app
from ..database import SessionLocal
from .. import crud, models
from ..services.audio import extract_audio, separate_vocals
from ..services.asr import get_asr_service
from ..services.diarization import get_diarization_service
from ..services.alignment import get_alignment_service
from ..services.llm import LLMService

@celery_app.task(bind=True, name="process_video_task")
def process_video_task(self, task_id: str):
    """
    视频处理主任务流程
    """
    logger.info(f"Worker 开始处理任务: {task_id}")
    db: Session = SessionLocal()

    try:
        # 0. 获取任务
        task = crud.get_task(db, task_id)
        if not task:
            logger.error(f"Task {task_id} not found in DB")
            return

        crud.update_task(db, task_id, {
            "status": models.TaskStatus.PROCESSING,
            "progress": 5.0,
            "current_step": "Initializing"
        })

        # 准备路径
        video_path = task.video_path
        upload_dir = os.path.dirname(video_path)
        base_name = os.path.splitext(os.path.basename(video_path))[0]

        # 中间文件路径
        audio_path = os.path.join(upload_dir, f"{base_name}.wav")
        vocals_dir = os.path.join(upload_dir, "separated")

        # 1. 提取音频
        logger.info(f"Step 1: Extracting audio from {video_path}")
        crud.update_task(db, task_id, {"current_step": "Extracting Audio", "progress": 10.0})
        extract_audio(video_path, audio_path)

        # 2. 人声分离
        logger.info("Step 2: Separating vocals")
        crud.update_task(db, task_id, {"current_step": "Separating Vocals", "progress": 20.0})
        vocals_path = separate_vocals(audio_path, vocals_dir)

        # 3. ASR 转写
        logger.info("Step 3: ASR Transcription")
        crud.update_task(db, task_id, {"current_step": "ASR Transcription", "progress": 30.0})
        asr_service = get_asr_service()
        # 显存优化：ASR 完成后可以尝试释放模型，但这里我们使用单例，暂不释放
        asr_segments, detected_lang = asr_service.transcribe(vocals_path, language=task.source_language if task.source_language != "auto" else None)

        # 更新源语言 (如果检测出)
        if task.source_language == "auto":
            crud.update_task(db, task_id, {"source_language": detected_lang})

        # 4. 说话人分离
        logger.info("Step 4: Speaker Diarization")
        crud.update_task(db, task_id, {"current_step": "Speaker Diarization", "progress": 40.0})
        diarization_service = get_diarization_service()
        # 对原始音频进行分离，因为背景音可能有助于区分说话人环境，或者只用人声也可以。
        # 通常建议用原始音频或人声。这里用原始音频。
        speaker_segments = diarization_service.diarize(audio_path)

        # 5. 对齐与合并 (ASR + Diarization)
        logger.info("Step 5: Alignment & Merging")
        crud.update_task(db, task_id, {"current_step": "Alignment", "progress": 50.0})
        aligned_segments = _align_speakers(asr_segments, speaker_segments)

        # 6. Netflix 合规性检查 (分割)
        logger.info("Step 6: Compliance Check")
        crud.update_task(db, task_id, {"current_step": "Compliance Check", "progress": 55.0})
        alignment_service = get_alignment_service()
        compliant_segments = alignment_service.check_netflix_compliance(aligned_segments)

        # 保存中间结果到 metadata
        task_metadata = task.task_metadata or {}
        task_metadata["compliant_segments"] = compliant_segments
        crud.update_task(db, task_id, {"task_metadata": task_metadata})

        # 7. 术语提取 (LLM)
        logger.info("Step 7: Terminology Extraction")
        crud.update_task(db, task_id, {"current_step": "Terminology Extraction", "progress": 60.0})

        llm_config = task.llm_config or {}
        llm_service = LLMService(
            api_key=llm_config.get("api_key"),
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model", "gpt-4o")
        )

        full_text = "\n".join([s["text"] for s in compliant_segments])
        terminology_json = llm_service.extract_terminology(
            full_text,
            task.source_language or detected_lang,
            task.target_language
        )

        task_metadata["terminology"] = terminology_json
        crud.update_task(db, task_id, {"task_metadata": task_metadata})

        # 8. 三步翻译 (LLM)
        logger.info("Step 8: Translation")
        crud.update_task(db, task_id, {"current_step": "Translation", "progress": 65.0})

        translated_segments = []
        total_segs = len(compliant_segments)

        # 批量处理或逐句处理。这里逐句处理，实际生产可能需要并发或批量。
        for i, seg in enumerate(compliant_segments):
            source_text = seg["text"]
            # 只有当有文本时才翻译
            if source_text.strip():
                trans_text = llm_service.three_step_translation(
                    source_text,
                    task.source_language or detected_lang,
                    task.target_language,
                    terminology_json
                )
            else:
                trans_text = ""

            new_seg = seg.copy()
            new_seg["text"] = trans_text
            new_seg["original_text"] = source_text
            translated_segments.append(new_seg)

            # 进度更新 65% -> 90%
            if i % 5 == 0:
                prog = 65.0 + (25.0 * (i / total_segs))
                crud.update_task(db, task_id, {"progress": prog})

        task_metadata["translated_segments"] = translated_segments
        crud.update_task(db, task_id, {"task_metadata": task_metadata})

        # 9. 生成字幕文件
        logger.info("Step 9: Generating Files")
        crud.update_task(db, task_id, {"current_step": "Finalizing", "progress": 95.0})

        srt_content = alignment_service.to_srt(translated_segments)
        vtt_content = alignment_service.to_vtt(translated_segments)
        ass_content = alignment_service.to_ass(translated_segments)

        srt_path = os.path.join(upload_dir, f"{base_name}.srt")
        vtt_path = os.path.join(upload_dir, f"{base_name}.vtt")
        ass_path = os.path.join(upload_dir, f"{base_name}.ass")

        with open(srt_path, "w", encoding="utf-8") as f: f.write(srt_content)
        with open(vtt_path, "w", encoding="utf-8") as f: f.write(vtt_content)
        with open(ass_path, "w", encoding="utf-8") as f: f.write(ass_content)

        # 10. 完成
        crud.update_task(db, task_id, {
            "status": models.TaskStatus.COMPLETED,
            "progress": 100.0,
            "current_step": "Completed",
            "result_files": {
                "srt": srt_path,
                "vtt": vtt_path,
                "ass": ass_path
            }
        })
        logger.info(f"Task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        logger.error(traceback.format_exc())
        crud.update_task(db, task_id, {
            "status": models.TaskStatus.FAILED,
            "error_message": str(e)
        })
    finally:
        db.close()

def _align_speakers(asr_segments, diarization_segments):
    """
    将 ASR 单词/片段与说话人片段对齐。
    简单策略：对于 ASR 的每个片段，找到时间重叠最大的说话人。
    如果 ASR 提供了单词级时间戳，可以做得更细，但这里先按 ASR 片段级对齐。
    """
    aligned = []

    # 将说话人片段按开始时间排序
    diarization_segments.sort(key=lambda x: x["start"])

    for seg in asr_segments:
        start = seg["start"]
        end = seg["end"]

        # 寻找重叠最多的说话人
        best_speaker = "Unknown"
        max_overlap = 0

        for diag in diarization_segments:
            d_start = diag["start"]
            d_end = diag["end"]

            # 计算重叠
            overlap_start = max(start, d_start)
            overlap_end = min(end, d_end)
            overlap = max(0, overlap_end - overlap_start)

            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = diag["speaker"]

            # 优化：如果说话人片段开始时间已经超过了 ASR 片段结束时间，后面的都不用看了
            if d_start > end:
                break

        new_seg = seg.copy()
        new_seg["speaker"] = best_speaker
        aligned.append(new_seg)

    return aligned
