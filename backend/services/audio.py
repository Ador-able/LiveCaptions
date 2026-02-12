import os
import subprocess
import torch
import demucs.separate
from loguru import logger

class AudioService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def extract_audio(self, video_path: str, output_path: str):
        """Extracts audio from video using ffmpeg."""
        logger.info(f"Extracting audio from {video_path} to {output_path}")
        try:
            command = [
                "ffmpeg", "-y", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                output_path
            ]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e}")
            raise

    def separate_vocals(self, audio_path: str, output_dir: str):
        """
        Uses Demucs to separate vocals from background.
        Returns the path to the isolated vocal track.
        """
        logger.info(f"Separating vocals for {audio_path} using Demucs on {self.device}")

        # Demucs command line interface wrapper
        # We can also use the python API: demucs.separate.main(["--two-stems", "vocals", "-n", "htdemucs", audio_path, "-o", output_dir, "-d", self.device])

        try:
            # Using htdemucs model (high quality, fast)
            # --two-stems vocals: only separate into vocals and non-vocals
            cmd = [
                "demucs",
                "--two-stems", "vocals",
                "-n", "htdemucs",
                "-d", self.device,
                "-o", output_dir,
                audio_path
            ]
            subprocess.run(cmd, check=True)

            # Construct expected output path
            # Demucs structure: <output_dir>/htdemucs/<filename_without_ext>/vocals.wav
            filename = os.path.splitext(os.path.basename(audio_path))[0]
            vocal_path = os.path.join(output_dir, "htdemucs", filename, "vocals.wav")

            if not os.path.exists(vocal_path):
                 raise FileNotFoundError(f"Demucs output not found at {vocal_path}")

            return vocal_path

        except Exception as e:
            logger.error(f"Demucs separation failed: {e}")
            raise

audio_service = AudioService()
