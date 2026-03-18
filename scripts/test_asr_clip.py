#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：剪取指定任务的音频并使用 v2、v3 两种模型测试 ASR，对比结果
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Any

# 添加项目路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import RESULT_DIR
from backend.services.asr import get_asr_service

TASK_DIR = r"E:\Projects\LiveCaptions\build\LiveCaptions-Portable\data\results\7ceacdc1-d837-4012-b10e-41d611c7e1f7"
START_MIN = 0
END_MIN = 2

MODELS_TO_TEST = ["v2", "v3"]

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


def transcribe_audio(audio_path: Path, model_name: str):
    """使用指定模型进行 ASR 转写"""
    print("\n" + "=" * 60)
    print(f"开始使用 {model_name.upper()} 模型进行 ASR 转写...")
    print("=" * 60)
    
    asr_service = get_asr_service(model=model_name)
    
    start_time = time.time()
    
    def progress_callback(progress):
        print(f"进度：{progress*100:.1f}%", end="\r")
    
    segments, detected_lang = asr_service.transcribe(
        str(audio_path),
        language="ja",  # 假设是日语
        progress_callback=progress_callback,
        use_word_timestamps=False,
    )
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 60)
    print(f"转写完成！模型：{model_name.upper()}, 检测语言：{detected_lang}")
    print(f"耗时：{elapsed_time:.2f}秒")
    print(f"共 {len(segments)} 个片段")
    print("=" * 60)
    
    for i, seg in enumerate(segments, 1):
        print(f"\n[{i}] {seg['start']:.2f} - {seg['end']:.2f}")
        print(f"    文本：{seg['text']}")
        if seg.get('words'):
            print(f"    词级：{', '.join([w['word'] for w in seg['words']])}")
    
    return segments, elapsed_time, detected_lang


def compare_results(results: Dict[str, Dict[str, Any]]):
    """对比不同模型的转写结果"""
    print("\n\n" + "=" * 80)
    print("模型对比结果")
    print("=" * 80)
    
    print("\n【性能对比】")
    print(f"{'模型':<15} {'耗时 (秒)':<15} {'片段数':<10} {'检测语言':<10}")
    print("-" * 80)
    
    for model_name, data in results.items():
        print(f"{model_name.upper():<15} {data['elapsed_time']:<15.2f} {data['segment_count']:<10} {data['detected_lang']:<10}")
    
    print("\n【文本内容对比】")
    print("-" * 80)
    
    models = list(results.keys())
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            model1, model2 = models[i], models[j]
            text1 = " ".join([seg['text'] for seg in results[model1]['segments']])
            text2 = " ".join([seg['text'] for seg in results[model2]['segments']])
            
            print(f"\n{model1.upper()} vs {model2.upper()}:")
            print(f"  {model1.upper()} 文本长度：{len(text1)} 字符")
            print(f"  {model2.upper()} 文本长度：{len(text2)} 字符")
            
            if text1 == text2:
                print(f"  文本内容：完全相同")
            else:
                print(f"  文本内容：存在差异")
                
            print(f"\n  {model1.upper()} 全部文本：{text1}")
            print(f"  {model2.upper()} 全部文本：{text2}")


def main():
    print(f"测试任务目录：{TASK_DIR}")
    print(f"时间范围：{START_MIN}:00 - {END_MIN}:00")
    print(f"测试模型：{', '.join(MODELS_TO_TEST)}")
    
    task_dir = Path(TASK_DIR)
    if not task_dir.exists():
        print(f"错误：任务目录不存在：{task_dir}")
        return
    
    print(f"任务目录：{task_dir}")
    
    vocals_path = find_vocals_file(task_dir)
    if not vocals_path:
        print(f"错误：未找到 vocals.wav 在 {task_dir}")
        return
    
    print(f"找到音频文件：{vocals_path}")
    
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
            print(f"pydub 也失败了：{e}")
            return
    
    if not output_path.exists():
        print("错误：剪取的音频文件不存在")
        return
    
    print(f"剪取的音频保存至：{output_path}")
    
    results = {}
    
    for model_name in MODELS_TO_TEST:
        print(f"\n\n{'='*80}")
        print(f"开始测试模型：{model_name.upper()}")
        print(f"{'='*80}\n")
        
        segments, elapsed_time, detected_lang = transcribe_audio(output_path, model_name)
        
        results[model_name] = {
            "segments": segments,
            "elapsed_time": elapsed_time,
            "segment_count": len(segments),
            "detected_lang": detected_lang
        }
        
        output_json = Path(__file__).resolve().parent / f"test_result_{model_name}.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)
        print(f"\n{model_name.upper()} 结果已保存至：{output_json}")
        
        try:
            asr_service = get_asr_service(model=model_name)
            asr_service.unload()
        except Exception as e:
            print(f"卸载 {model_name} 模型时出错：{e}")
    
    compare_results(results)
    
    overall_output = Path(__file__).resolve().parent / "test_comparison_summary.json"
    summary = {
        "models_tested": MODELS_TO_TEST,
        "audio_file": str(output_path),
        "results": {
            model_name: {
                "elapsed_time": data["elapsed_time"],
                "segment_count": data["segment_count"],
                "detected_lang": data["detected_lang"]
            }
            for model_name, data in results.items()
        }
    }
    with open(overall_output, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n对比摘要已保存至：{overall_output}")


if __name__ == "__main__":
    main()
