import os
import torch
from pyannote.audio import Pipeline
from loguru import logger
from typing import List, Dict, Any

class DiarizationService:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.pipeline = None

        # 尝试从环境变量获取 HF Token
        self.hf_token = os.getenv("HF_TOKEN")
        if not self.hf_token:
            logger.warning("未找到 HF_TOKEN 环境变量，Diarization 可能无法初始化 (除非已经本地缓存)。")

    def load_pipeline(self):
        if self.pipeline:
            return

        logger.info(f"正在加载 Diarization 模型 (设备: {self.device})...")
        try:
            # 默认使用 3.1 版本，这需要 HF Token
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            if self.pipeline:
                self.pipeline.to(self.device)
                logger.info("Diarization 模型加载成功。")
            else:
                logger.error("Diarization 模型加载失败 (Pipeline is None). 请检查 HF_TOKEN。")
        except Exception as e:
            logger.error(f"Diarization 模型加载出错: {e}")
            # 如果加载失败，可能需要回退或者抛出异常。这里选择抛出异常让 Task 处理。
            raise RuntimeError(f"Diarization init failed: {e}")

    def diarize(self, audio_path: str, num_speakers=None, min_speakers=None, max_speakers=None) -> List[Dict[str, Any]]:
        """
        执行说话人分离。
        返回片段列表: [{"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"}, ...]
        """
        if not self.pipeline:
            self.load_pipeline()

        if not self.pipeline:
            logger.error("Diarization pipeline 未就绪")
            raise RuntimeError("Diarization pipeline not initialized")

        logger.info(f"开始说话人分离: {audio_path}")

        try:
            # 构建参数
            params = {}
            if num_speakers: params["num_speakers"] = int(num_speakers)
            if min_speakers: params["min_speakers"] = int(min_speakers)
            if max_speakers: params["max_speakers"] = int(max_speakers)

            diarization = self.pipeline(audio_path, **params)

            result_segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                result_segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })

            logger.info(f"分离完成，共 {len(result_segments)} 个片段。")
            return result_segments

        except Exception as e:
            logger.error(f"说话人分离失败: {e}")
            raise RuntimeError(f"Diarization failed: {e}")

# 单例
_diarization_service = None

def get_diarization_service():
    global _diarization_service
    if _diarization_service is None:
        _diarization_service = DiarizationService()
    return _diarization_service
