import os
import shutil
import subprocess
from loguru import logger

from ..config import HF_HOME, TORCH_HOME, DEMUCS_MODEL, DEMUCS_DEVICE, DEMUCS_SEGMENT

try:
    import static_ffmpeg

    static_ffmpeg.add_paths()
    logger.info("Static FFmpeg paths added.")
except ImportError:
    logger.warning("static_ffmpeg not found, relying on system PATH.")


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
        command = ["ffmpeg", "-y", "-i", video_path, "-ar", "16000", "-ac", "1", "-f", "wav", output_path]
        logger.info(f"正在提取音频: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True)

        if not os.path.exists(output_path):
            raise FileNotFoundError(f"FFmpeg reported success but file not created: {output_path}")
        if os.path.getsize(output_path) == 0:
            raise ValueError(f"FFmpeg created empty file: {output_path}")

        logger.info(f"音频提取成功: {output_path}, Size: {os.path.getsize(output_path)/1024/1024:.2f} MB")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"音频提取失败: {error_msg}")
        raise RuntimeError(f"FFmpeg 失败: {error_msg}")


def separate_vocals(audio_path: str, output_dir: str):
    """
    使用 Demucs 分离人声 (htdemucs_ft 模型)
    输出目录: output_dir/htdemucs_ft/audio_filename/vocals.wav
    返回: 分离后 vocals.wav 的绝对路径
    """
    logger.info(f"开始人声分离: {audio_path} -> {output_dir}")
    import sys
    import threading
    import time

    env = os.environ.copy()

    if "TORCH_HOME" not in env:
        env["TORCH_HOME"] = TORCH_HOME
    if "HF_HOME" not in env:
        env["HF_HOME"] = HF_HOME

    env["TQDM_DISABLE"] = "1"

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"输入音频文件不存在: {audio_path}")
    if os.path.getsize(audio_path) == 0:
        raise ValueError(f"输入音频文件大小为0: {audio_path}")
    logger.info(f"输入音频检查通过: {audio_path}, 大小: {os.path.getsize(audio_path)/1024/1024:.2f} MB")

    filename_wo_ext = os.path.splitext(os.path.basename(audio_path))[0]
    expected_out_dir = os.path.join(output_dir, DEMUCS_MODEL, filename_wo_ext)

    if os.path.exists(expected_out_dir):
        logger.warning(f"检测到旧的人声分离输出目录，正在清理以重新执行: {expected_out_dir}")
        shutil.rmtree(expected_out_dir)

    torch_home = env["TORCH_HOME"]
    expected_model_path = os.path.join(torch_home, "hub", "checkpoints", "f7e0c4bc-ba3fe64a.th")
    logger.info(f"DEBUG: TORCH_HOME set to: {torch_home}")
    if os.path.exists(expected_model_path):
        logger.info(f"DEBUG: Found model file at {expected_model_path}, size: {os.path.getsize(expected_model_path)}")
    else:
        logger.info(f"DEBUG: Model file NOT found at {expected_model_path}")
        checkpoints_dir = os.path.join(torch_home, "hub", "checkpoints")
        if os.path.exists(checkpoints_dir):
            logger.info(f"DEBUG: Contents of {checkpoints_dir}: {os.listdir(checkpoints_dir)}")
        else:
            logger.info(f"DEBUG: Directory {checkpoints_dir} does not exist.")

    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "-n",
        DEMUCS_MODEL,
        "--two-stems=vocals",
        "--shifts", "4",
        "--segment",
        DEMUCS_SEGMENT,
        "-d",
        DEMUCS_DEVICE,
        "-o",
        output_dir,
        audio_path,
    ]

    def monitor_progress():
        """监控 Demucs 输出目录的创建进度"""
        logger.info("Demucs 人声分离进行中，请稍候...")
        last_log = time.time()
        while not os.path.exists(expected_out_dir) or not any(
            f.endswith('.wav') for f in os.listdir(expected_out_dir) if os.path.exists(expected_out_dir)
        ):
            if time.time() - last_log >= 10:
                logger.info("Demucs 人声分离仍在处理中...")
                last_log = time.time()
            time.sleep(2)
        logger.info("Demucs 输出文件开始生成...")

    try:
        logger.info(f"执行 Demucs 命令 (Device={DEMUCS_DEVICE}): {' '.join(cmd)}")
        
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
        monitor_thread.start()
        
        subprocess.run(cmd, check=True, capture_output=True, env=env)

        vocals_path = os.path.join(expected_out_dir, "vocals.wav")

        if not os.path.exists(vocals_path):
            logger.warning(f"未找到预期路径: {vocals_path}")
            fallback_path = os.path.join(output_dir, "htdemucs", filename_wo_ext, "vocals.wav")
            if os.path.exists(fallback_path):
                vocals_path = fallback_path
            else:
                if os.path.exists(output_dir):
                    for root, dirs, files in os.walk(output_dir):
                        for file in files:
                            logger.debug(f"发现文件: {os.path.join(root, file)}")
                raise FileNotFoundError(f"未找到分离后的音频文件: {vocals_path}")

        logger.info(f"人声分离成功: {vocals_path}")
        return vocals_path

    except subprocess.CalledProcessError as e:
        stdout_msg = e.stdout.decode() if e.stdout else ""
        stderr_msg = e.stderr.decode() if e.stderr else ""
        error_details = (
            f"Command '{e.cmd}' returned non-zero exit status {e.returncode}.\n"
            f"STDOUT: {stdout_msg}\n"
            f"STDERR: {stderr_msg}"
        )
        logger.error(f"Demucs 失败: {error_details}")
        raise RuntimeError(f"Demucs 失败: {error_details}")
