import os
import shutil
import subprocess
from loguru import logger
from fastapi import HTTPException

# 音频处理服务
# 职责：视频转音频，人声分离 (Demucs)

def extract_audio(video_path: str, output_path: str):
    """
    使用 ffmpeg 从视频中提取音频 (wav 格式，16k 采样率，单声道)。
    """
    try:
        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            output_path
        ]
        logger.info(f"正在提取音频: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True)
        logger.info(f"音频提取成功: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"音频提取失败: {e.stderr.decode()}")
        raise RuntimeError(f"FFmpeg 执行失败: {e.stderr.decode()}")

def separate_vocals(audio_path: str, output_dir: str):
    """
    使用 Demucs 分离人声 (htdemucs 模型，快速且效果好)。
    这对于处理背景音乐嘈杂的视频至关重要，能显著提高 Whisper 的识别率。
    """
    try:
        # Demucs 命令行调用
        # -n htdemucs: 使用 htdemucs 模型
        # --two-stems=vocals: 只输出 vocals 和 non_vocals
        command = [
            "demucs",
            "-n", "htdemucs",
            "--two-stems=vocals",
            "-o", output_dir,
            audio_path
        ]
        logger.info(f"正在进行人声分离: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True)

        # 定位分离后的人声文件路径
        # 默认结构: output_dir/htdemucs/{input_filename_wo_ext}/vocals.wav
        filename_wo_ext = os.path.splitext(os.path.basename(audio_path))[0]
        # Demucs 会在模型文件夹 (htdemucs) 下创建一个以输入文件名命名的文件夹
        vocals_path = os.path.join(output_dir, "htdemucs", filename_wo_ext, "vocals.wav")

        if not os.path.exists(vocals_path):
             # 调试日志：如果路径结构不符合预期
             logger.warning(f"预期路径未找到: {vocals_path}")
             # 检查输出目录内容
             if os.path.exists(output_dir):
                 for root, dirs, files in os.walk(output_dir):
                     logger.debug(f"发现文件: {os.path.join(root, file)} for file in files")

             raise FileNotFoundError(f"Demucs 输出文件未找到: {vocals_path}")

        logger.info(f"人声分离成功: {vocals_path}")
        return vocals_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Demucs 执行失败: {e.stderr.decode()}")
        raise RuntimeError(f"Demucs 执行失败: {e.stderr.decode()}")
