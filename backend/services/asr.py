from faster_whisper import WhisperModel
import os
import torch
import ffmpeg
from loguru import logger
from typing import List, Dict, Any, Optional

class ASRService:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.whisper_model_size = "large-v3"
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading Faster Whisper ({self.whisper_model_size}) on {self.device}...")
            # Ensure model is downloaded if not present.
            # faster-whisper handles downloading automatically.
            self._model = WhisperModel(
                self.whisper_model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, audio_path: str, language: str = None) -> List[Dict[str, Any]]:
        """
        Transcribes audio using Faster Whisper with VAD.
        Returns a list of segments.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Starting transcription for {audio_path}...")

        # 'language' parameter: if None, auto-detects.
        segments_generator, info = self.model.transcribe(
            audio_path,
            beam_size=5,
            language=None if language == "auto" else language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        segments = []
        for segment in segments_generator:
            segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "confidence": segment.avg_logprob
            })

        logger.info(f"Transcription complete. Detected Language: {info.language} (Probability: {info.language_probability})")
        return segments, info.language

asr_service = ASRService()
