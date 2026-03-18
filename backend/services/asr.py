# -*- coding: utf-8 -*-
import os
import gc
import time
import logging
from faster_whisper import WhisperModel
from loguru import logger
import torch
from typing import List, Dict, Any, Tuple

from ..config import WHISPER_MODEL_PATH

logging.basicConfig()
logging.getLogger("faster_whisper").setLevel(logging.INFO)

class ASRService:
    """
    ASR 服务类

    使用 Faster Whisper 模型进行语音转文字。
    支持 CUDA 加速，自动回退到 CPU。
    """
    def __init__(self, model_size=None, device="cuda", compute_type="float16"):
        """
        Initialize Whisper Model.
        """
        if model_size is None:
            if os.path.exists(WHISPER_MODEL_PATH):
                 model_size = WHISPER_MODEL_PATH
                 logger.info(f"Using local model: {model_size}")
            else:
                 model_size = WHISPER_MODEL_PATH

        self.device = device
        self.compute_type = compute_type
        
        # Check CUDA availability
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU.")
            self.device = "cpu"
            self.compute_type = "int8"
        logger.info(f"正在加载 Whisper 模型: {model_size} (设备: {self.device}, 精度: {self.compute_type})")
        try:
            # 加载模型 (首次运行会自动下载)
            self.model = WhisperModel(model_size, device=self.device, compute_type=self.compute_type)
            self._gpu_unloaded = False  # 跟踪GPU资源是否已释放
            logger.info("Whisper 模型加载完成。")
        except Exception as e:
            logger.error(f"Whisper 模型加载失败: {e}")
            raise RuntimeError(f"ASR Model load failed: {e}")

    @property
    def is_available(self) -> bool:
        """模型是否可用于推理（已加载且GPU资源未释放）"""
        return hasattr(self, 'model') and self.model is not None and not self._gpu_unloaded

    def transcribe(self, audio_path: str, language: str = None, progress_callback=None, use_word_timestamps: bool = True) -> Tuple[List[Dict[str, Any]], Any]:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio file
            language: Target language code (e.g. "zh", "en"), None for auto-detect
            progress_callback: Optional callback function(progress: float)
            
        Returns:
            Tuple containing list of segments and info object
        """
        if not self.is_available:
            raise RuntimeError("Model not initialized or GPU resources unloaded")
            
        if not os.path.exists(audio_path):
            logger.error(f"音频文件未找到: {audio_path}")
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Starting ASR for {audio_path}, lang={language}")
        
        try:
            logger.info("开始调用 model.transcribe()...")
            segments, info = self.model.transcribe(
                audio_path, 
                language=language,
                beam_size=10,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=1000,
                    speech_pad_ms=400
                ),
                word_timestamps=use_word_timestamps,
                condition_on_previous_text=False,
                # temperature=0.2,
                compression_ratio_threshold=2.2,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0
            )
            logger.info(f"model.transcribe() 返回，开始迭代 segments，音频总时长: {info.duration:.2f}秒")
            
            result_segments = []
            total_duration = info.duration
            segment_count = 0
            
            for segment in segments:
                segment_count += 1
                segment_data = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                }
                if use_word_timestamps and segment.words:
                    segment_data["words"] = [{"start": w.start, "end": w.end, "word": w.word} for w in segment.words]
                result_segments.append(segment_data)
                
                if progress_callback and total_duration > 0:
                    current_progress = min(1.0, segment.end / total_duration)
                    progress_callback(current_progress)
                    if segment_count % 10 == 0:
                        logger.info(f"已处理 {segment_count} 个片段，进度: {current_progress*100:.0f}%")

            logger.info(f"转写完成，共生成 {len(result_segments)} 个片段. Detected language: {info.language}")
            return result_segments, info.language
        except Exception as e:
            logger.error(f"ASR 转写失败: {e}")
            raise RuntimeError(f"ASR Transcription failed: {e}")

    def unload(self):
        """
        释放GPU显存，但不销毁Python对象。

        *** 重要 ***
        CTranslate2 (faster-whisper 底层) 的 C++ 析构函数在 Windows + CUDA 环境下
        会导致 SEGFAULT 静默崩溃。任何触发析构的操作 (del / 置 None / gc) 都不安全。
        
        解决方案：
        使用 CTranslate2 自带的 unload_model() API，它只释放模型权重占用的
        GPU/CPU 内存，但保持 C++ 对象骨架存活，不会触发析构函数。
        """
        if not hasattr(self, 'model') or self.model is None:
            logger.info("Whisper 模型不存在，跳过卸载")
            return
        
        if self._gpu_unloaded:
            logger.info("Whisper 模型GPU资源已经释放过，跳过")
            return

        logger.info("正在释放 Whisper 模型GPU显存...")

        try:
            # Step 1: 同步 CUDA，确保所有异步 GPU 操作完成
            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.synchronize()
                logger.debug("CUDA 同步完成")

            # Step 2: 使用 CTranslate2 的 unload_model() 安全释放显存
            # WhisperModel 内部有一个 self.model (ctranslate2.models.Whisper)
            # 该对象有 unload_model() 方法可以安全释放权重而不触发 C++ 析构
            ct2_model = getattr(self.model, 'model', None)
            if ct2_model is not None and hasattr(ct2_model, 'unload_model'):
                ct2_model.unload_model()
                logger.info("CTranslate2 模型权重已通过 unload_model() 安全释放")
            else:
                logger.warning("未找到 CTranslate2 的 unload_model() 方法，跳过显存释放")

            # Step 3: 清理 PyTorch 的 GPU 缓存
            gc.collect()
            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("PyTorch GPU缓存已清理")

        except Exception as e:
            logger.warning(f"释放GPU显存时遇到异常: {e}")

        # 标记为已卸载，下次 get_asr_service() 会重新创建实例
        self._gpu_unloaded = True
        logger.info("Whisper 模型GPU显存已释放完毕（对象保持存活，避免C++析构崩溃）")

# 单例实例 (供 worker 使用)
_asr_service = None

def get_asr_service():
    """
    获取 ASR 服务单例。
    确保模型只加载一次，节省显存。
    如果之前 GPU 资源被释放了，会重新创建实例。
    """
    global _asr_service
    if _asr_service is None or not _asr_service.is_available:
        _asr_service = ASRService()
    return _asr_service
