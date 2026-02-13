import os
import shutil
import subprocess
from loguru import logger
from fastapi import HTTPException

# 音频处理服务
# 职责：视频转音频提取，人声分离 (Demucs)

def _check_command(cmd: str):
    """Ensure the external command exists in PATH."""
    if not shutil.which(cmd):
        logger.error(f"Command not found: {cmd}")
        raise RuntimeError(f"External dependency missing: {cmd}")

def extract_audio(video_path: str, output_path: str):
    """
    使用 ffmpeg 从视频中提取音频 (wav 格式, 16k 采样率, 单声道)
    """
    _check_command("ffmpeg")

    try:
        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ar", "16000",
            "-ac", "1",
            "-f", "wav",
            output_path
        ]
<<<<<<< HEAD
        logger.info(f"Extracting audio: {' '.join(command)}")
        # capture_output=True creates stderr in e.stderr
=======
        logger.info(f"正在提取音频: {' '.join(command)}")
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738
        subprocess.run(command, check=True, capture_output=True)
        logger.info(f"音频提取成功: {output_path}")
    except subprocess.CalledProcessError as e:
<<<<<<< HEAD
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"Audio extraction failed: {error_msg}")
        raise RuntimeError(f"FFmpeg failed: {error_msg}")

def separate_vocals(audio_path: str, output_dir: str):
    """
    Separate vocals using Demucs (mdx_extra_q model, high quality for complex background)
=======
        logger.error(f"音频提取失败: {e.stderr.decode()}")
        raise RuntimeError(f"FFmpeg 失败: {e.stderr.decode()}")

def separate_vocals(audio_path: str, output_dir: str):
    """
    使用 Demucs 分离人声 (htdemucs 模型, 快速且有效)
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738
    """
    _check_command("demucs")

    try:
<<<<<<< HEAD
        # Demucs command line call
        # -n mdx_extra_q: Use mdx_extra_q model
        # --two-stems=vocals: Only output vocals and non_vocals
=======
        # Demucs 命令行调用
        # -n htdemucs: 使用 htdemucs 模型
        # --two-stems=vocals: 仅输出人声和非人声
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738
        command = [
            "demucs",
            "-n", "mdx_extra_q",
            "--two-stems=vocals",
            "-o", output_dir,
            audio_path
        ]
        logger.info(f"正在分离人声: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True)

<<<<<<< HEAD
        # Locate the separated vocal file path
        # Default structure: output_dir/mdx_extra_q/{input_filename_wo_ext}/vocals.wav
        filename_wo_ext = os.path.splitext(os.path.basename(audio_path))[0]
        # Demucs creates a folder with the input filename (without extension) inside the model folder (htdemucs)
        # Note: Demucs behavior might vary slightly by version, but this is standard for v4
=======
        # 定位分离后的人声文件路径
        # 默认结构: output_dir/htdemucs/{input_filename_wo_ext}/vocals.wav
        filename_wo_ext = os.path.splitext(os.path.basename(audio_path))[0]
        # Demucs 会在模型文件夹 (htdemucs) 内创建一个以输入文件名 (无扩展名) 命名的文件夹
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738
        vocals_path = os.path.join(output_dir, "htdemucs", filename_wo_ext, "vocals.wav")

        if not os.path.exists(vocals_path):
             # 如果路径结构不符合预期，记录调试日志
             logger.warning(f"未找到预期路径: {vocals_path}")
             # 检查输出目录是否有内容
             if os.path.exists(output_dir):
                 for root, dirs, files in os.walk(output_dir):
                     for file in files:
<<<<<<< HEAD
                        logger.debug(f"Found file: {os.path.join(root, file)}")
=======
                         logger.debug(f"发现文件: {os.path.join(root, file)}")
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738

             raise FileNotFoundError(f"在 {vocals_path} 未找到 Demucs 输出")

        logger.info(f"人声分离成功: {vocals_path}")
        return vocals_path
    except subprocess.CalledProcessError as e:
<<<<<<< HEAD
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"Demucs failed: {error_msg}")
        raise RuntimeError(f"Demucs failed: {error_msg}")
=======
        logger.error(f"Demucs 失败: {e.stderr.decode()}")
        raise RuntimeError(f"Demucs 失败: {e.stderr.decode()}")
>>>>>>> origin/jules-alignment-segmentation-13533857260951222738
