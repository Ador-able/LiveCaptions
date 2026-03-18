#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：剪取指定任务的16-18分钟音频并单独测试ASR
"""
import os
import sys
import json
from pathlib import Path

# 添加项目路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import RESULT_DIR
from backend.services.asr import ASRService

TASK_DIR = r"E:\Projects\LiveCaptions\build\LiveCaptions-Portable\data\results\c8990eb6-bdf9-4b77-972b-556bee413cd5"
START_MIN = 16
END_MIN = 18


def find_vocals_file(task_dir: Path):
    """在任务目录中查找 vocals.wav"""
    for root, _, files in os.walk(task_dir):
        if "vocals.wav" in files:
            return Path(root) / "vocals.wav"
    return None


def clip_audio_with_ffmpeg(input_path: Path, output_path: Path, start_sec: float, end_sec: float):
    """使用 ffmpeg 剪取音频"""
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
    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 错误: {result.stderr}")
        return False
    print("音频剪取完成!")
    return True


def transcribe_audio(audio_path: Path):
    """使用当前项目配置进行ASR转写"""
    print("\n" + "=" * 60)
    print("开始ASR转写...")
    print("=" * 60)
    
    asr_service = ASRService()
    
    def progress_callback(progress):
        print(f"进度: {progress*100:.1f}%", end="\r")
    
    segments, detected_lang = asr_service.transcribe(
        str(audio_path),
        language="ja",  # 假设是日语
        progress_callback=progress_callback
    )
    
    print("\n" + "=" * 60)
    print(f"转写完成! 检测语言: {detected_lang}")
    print(f"共 {len(segments)} 个片段")
    print("=" * 60)
    
    for i, seg in enumerate(segments, 1):
        print(f"\n[{i}] {seg['start']:.2f} - {seg['end']:.2f}")
        print(f"    文本: {seg['text']}")
        if seg.get('words'):
            print(f"    词级: {', '.join([w['word'] for w in seg['words']])}")
    
    return segments


def main():
    print(f"测试任务目录: {TASK_DIR}")
    print(f"时间范围: {START_MIN}:00 - {END_MIN}:00")
    
    task_dir = Path(TASK_DIR)
    if not task_dir.exists():
        print(f"错误: 任务目录不存在: {task_dir}")
        return
    
    print(f"任务目录: {task_dir}")
    
    vocals_path = find_vocals_file(task_dir)
    if not vocals_path:
        print(f"错误: 未找到 vocals.wav 在 {task_dir}")
        return
    
    print(f"找到音频文件: {vocals_path}")
    
    output_path = Path(__file__).resolve().parent / "test_clip.wav"
    start_sec = START_MIN * 60
    end_sec = END_MIN * 60
    
    if not clip_audio_with_ffmpeg(vocals_path, output_path, start_sec, end_sec):
        print("尝试使用 pydub 作为备选方案...")
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(str(vocals_path))
            clip = audio[start_sec*1000 : end_sec*1000]
            clip.export(str(output_path), format="wav")
            print("pydub 剪取完成!")
        except Exception as e:
            print(f"pydub 也失败了: {e}")
            return
    
    if output_path.exists():
        print(f"剪取的音频保存至: {output_path}")
        segments = transcribe_audio(output_path)
        
        output_json = Path(__file__).resolve().parent / "test_result.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存至: {output_json}")
    else:
        print("错误: 剪取的音频文件不存在")


if __name__ == "__main__":
    main()
