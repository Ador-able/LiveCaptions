import os
from faster_whisper import WhisperModel
from loguru import logger
import torch
from typing import List, Dict, Any

class ASRService:
    """
    ASR 服务类

    使用 Faster Whisper 模型进行语音转文字。
    支持 CUDA 加速，自动回退到 CPU。
    """
    def __init__(self, model_size="large-v3", device="cuda", compute_type="float16"):
        """
        初始化 Whisper 模型。

        参数:
        - model_size: 模型大小 (如 "large-v3", "medium", "small")。
        - device: 运行设备 ("cuda" 或 "cpu")。
        - compute_type: 计算精度 ("float16" 用于 GPU, "int8" 用于 CPU)。
        """
        self.device = device
        self.compute_type = compute_type

        # 检查 CUDA 是否可用
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA 不可用，将回退到 CPU 模式运行。这可能会很慢。")
            self.device = "cpu"
            self.compute_type = "int8"

        logger.info(f"正在加载 Whisper 模型: {model_size} (设备: {self.device}, 精度: {self.compute_type})")
        # 加载模型 (首次运行会自动下载)
        self.model = WhisperModel(model_size, device=self.device, compute_type=self.compute_type)
        logger.info("Whisper 模型加载完成。")

    def transcribe(self, audio_path: str, language: str = None) -> (List[Dict[str, Any]], str):
        """
        转写音频文件。

        参数:
        - audio_path: 音频文件路径。
        - language: 指定源语言 (如 "zh", "en")，若为 None 则自动检测。

        返回:
        - segments: 转写片段列表，包含 start, end, text, words。
        - language: 检测到的或指定的语言代码。
        """
        logger.info(f"开始转写音频: {audio_path}")

        # 调用 transcribe 方法
        # vad_filter=True: 使用内置 VAD 过滤静音片段，避免幻觉
        # beam_size=5: 束搜索大小，越大越准但越慢
        # word_timestamps=True: 输出单词级时间戳，这对后续对齐至关重要
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500), # 最小静音时长 (毫秒)
            beam_size=5,
            word_timestamps=True
        )

        logger.info(f"检测到的语言: {info.language} (置信度: {info.language_probability:.2f})")

        # 将生成器转换为列表，确保所有片段都已生成
        result_segments = []
        for segment in segments:
            result_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                # 单词级详细信息，用于精细对齐
                "words": [{"start": w.start, "end": w.end, "word": w.word} for w in segment.words]
            })

        logger.info(f"转写完成，共生成 {len(result_segments)} 个片段。")
        return result_segments, info.language

# 单例实例 (供 worker 使用)
# 在 Celery 中，我们可能希望每个 worker 进程只初始化一次模型
_asr_service = None

def get_asr_service():
    """
    获取 ASR 服务单例。
    确保模型只加载一次，节省显存。
    """
    global _asr_service
    if _asr_service is None:
        _asr_service = ASRService()
    return _asr_service
