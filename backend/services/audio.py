import os
import shutil
import subprocess
from loguru import logger
from fastapi import HTTPException

# Audio Processing Service
# Responsibilities: Video to Audio extraction, Vocal Separation (Demucs)

def extract_audio(video_path: str, output_path: str):
    """
    Extract audio from video using ffmpeg (wav format, 16k sample rate, mono)
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
        logger.info(f"Extracting audio: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True)
        logger.info(f"Audio extracted successfully: {output_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Audio extraction failed: {e.stderr.decode()}")
        raise RuntimeError(f"FFmpeg failed: {e.stderr.decode()}")

def separate_vocals(audio_path: str, output_dir: str):
    """
    Separate vocals using Demucs (htdemucs model, fast and effective)
    """
    try:
        # Demucs command line call
        # -n htdemucs: Use htdemucs model
        # --two-stems=vocals: Only output vocals and non_vocals
        command = [
            "demucs",
            "-n", "htdemucs",
            "--two-stems=vocals",
            "-o", output_dir,
            audio_path
        ]
        logger.info(f"Separating vocals: {' '.join(command)}")
        subprocess.run(command, check=True, capture_output=True)

        # Locate the separated vocal file path
        # Default structure: output_dir/htdemucs/{input_filename_wo_ext}/vocals.wav
        filename_wo_ext = os.path.splitext(os.path.basename(audio_path))[0]
        # Demucs creates a folder with the input filename (without extension) inside the model folder (htdemucs)
        vocals_path = os.path.join(output_dir, "htdemucs", filename_wo_ext, "vocals.wav")

        if not os.path.exists(vocals_path):
             # Debugging log if path structure is unexpected
             logger.warning(f"Expected path not found: {vocals_path}")
             # Check if output directory has content
             if os.path.exists(output_dir):
                 for root, dirs, files in os.walk(output_dir):
                     logger.debug(f"Found file: {os.path.join(root, file)} for file in files")

             raise FileNotFoundError(f"Demucs output not found at {vocals_path}")

        logger.info(f"Vocals separated successfully: {vocals_path}")
        return vocals_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Demucs failed: {e.stderr.decode()}")
        raise RuntimeError(f"Demucs failed: {e.stderr.decode()}")
