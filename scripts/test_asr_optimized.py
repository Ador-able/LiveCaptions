#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：剪取指定任务的16-18分钟音频并单独测试ASR（优化配置版）
"""
import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import RESULT_DIR, WHISPER_MODEL_PATH
from loguru import logger
import torch
from faster_whisper import WhisperModel

TASK_DIR = r"E:\Projects\LiveCaptions\build\LiveCaptions-Portable\data\results\58b0d1ae-8684-48d3-884b-199565811bed"
START_MIN = 3
END_MIN = 5


def find_vocals_file(task_dir: Path):
    for root, _, files in os.walk(task_dir):
        if "vocals.wav" in files:
            return Path(root) / "vocals.wav"
    return None


def clip_audio_with_ffmpeg(input_path: Path, output_path: Path, start_sec: float, end_sec: float):
    import subprocess
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-c", "copy",
        str(output_path)
    ]
    logger.info(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"ffmpeg 错误: {result.stderr}")
        return False
    logger.info("音频剪取完成!")
    return True


def format_time(seconds: float):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


def transcribe_audio_optimized(audio_path: Path):
    logger.info("\n" + "=" * 80)
    logger.info("开始ASR转写（优化配置）...")
    logger.info("=" * 80)
    
    model_size = WHISPER_MODEL_PATH
    device = "cuda"
    compute_type = "float16"
    
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, falling back to CPU.")
        device = "cpu"
        compute_type = "int8"
    
    logger.info(f"正在加载 Whisper 模型: {model_size} (设备: {device}, 精度: {compute_type})")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    logger.info("Whisper 模型加载完成。")
    
    logger.info("开始调用 model.transcribe()...")
    segments, info = model.transcribe(
        str(audio_path),
        language="ja",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=1000,
            speech_pad_ms=400
        ),
        word_timestamps=False,
        condition_on_previous_text=True,
        initial_prompt="以下は日常的な会話です。句読点（、。）を適切に補って、自然な日本語で書き起こしてください。",
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0
    )
    logger.info(f"model.transcribe() 返回，开始迭代 segments，音频总时长: {info.duration:.2f}秒")
    
    result_segments = []
    for segment in segments:
        result_segments.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        })
    
    logger.info("\n" + "=" * 80)
    logger.info(f"转写完成! 检测语言: {info.language}")
    logger.info(f"共 {len(result_segments)} 个片段")
    logger.info("=" * 80)
    
    for i, seg in enumerate(result_segments, 1):
        start_fmt = format_time(seg["start"])
        end_fmt = format_time(seg["end"])
        logger.info(f"\n[{i}] {start_fmt} - {end_fmt} ({seg['start']:.2f}s - {seg['end']:.2f}s)")
        logger.info(f"    文本: {seg['text']}")
    
    return result_segments


def main():
    logger.info(f"测试任务目录: {TASK_DIR}")
    logger.info(f"时间范围: {START_MIN}:00 - {END_MIN}:00")
    
    task_dir = Path(TASK_DIR)
    if not task_dir.exists():
        logger.error(f"错误: 任务目录不存在: {task_dir}")
        return
    
    logger.info(f"任务目录: {task_dir}")
    
    vocals_path = find_vocals_file(task_dir)
    if not vocals_path:
        logger.error(f"错误: 未找到 vocals.wav 在 {task_dir}")
        return
    
    logger.info(f"找到音频文件: {vocals_path}")
    
    output_path = Path(__file__).resolve().parent / "test_clip.wav"
    start_sec = START_MIN * 60
    end_sec = END_MIN * 60
    
    if not clip_audio_with_ffmpeg(vocals_path, output_path, start_sec, end_sec):
        logger.info("尝试使用 pydub 作为备选方案...")
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(str(vocals_path))
            clip = audio[start_sec*1000 : end_sec*1000]
            clip.export(str(output_path), format="wav")
            logger.info("pydub 剪取完成!")
        except Exception as e:
            logger.error(f"pydub 也失败了: {e}")
            return
    
    if output_path.exists():
        logger.info(f"剪取的音频保存至: {output_path}")
        segments = transcribe_audio_optimized(output_path)
        
        output_json = Path(__file__).resolve().parent / "test_result_optimized.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        logger.info(f"\n结果已保存至: {output_json}")
    else:
        logger.error("错误: 剪取的音频文件不存在")


if __name__ == "__main__":
    main()
