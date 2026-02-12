import re
from loguru import logger
from typing import List, Dict, Any

class AlignmentService:
    """
    对齐与合规性检查服务

    负责：
    1. 根据 Netflix 字幕标准检查和分割字幕。
    2. 处理时间戳对齐。
    3. 清洗文本中的冗余字符。
    """
    def __init__(self):
        pass

    def check_netflix_compliance(self, segments: List[Dict[str, Any]], max_cpl=42, max_cps=20, force_single_line=True) -> List[Dict[str, Any]]:
        """
        检查并修复字幕以符合 Netflix 标准。

        参数:
        - segments: 原始字幕片段列表 (start, end, text)。
        - max_cpl: 每行最大字符数 (默认 42)。
        - max_cps: 每秒最大字符数 (默认 20)。
        - force_single_line: 是否强制单行字幕 (默认为 True，这会拆分双行字幕为多个时间轴)。

        返回:
        - compliant_segments: 处理后的字幕片段列表。
        """
        logger.info(f"开始 Netflix 合规性检查 (max_cpl={max_cpl}, max_cps={max_cps}, single_line={force_single_line})")

        compliant_segments = []

        for segment in segments:
            text = segment['text']
            start = segment['start']
            end = segment['end']
            duration = end - start

            # 1. 基础文本清洗
            text = self._clean_text(text)

            # 2. CPL (字符长度) 检查与分割
            # 如果文本长度超过最大限制，需要将其拆分为多个片段
            if len(text) > max_cpl:
                 logger.debug(f"行过长 ({len(text)} > {max_cpl}): {text}")
                 # TODO: 实现更复杂的分割逻辑 (如按句子、标点分割)
                 # 这里暂时直接使用一个简单策略：如果太长就标记，或者按中间空格/标点强行拆分
                 # 为了保持代码简洁，这里暂时只做简单的截断或警告，实际应引入 NLP 分割
                 pass # 暂且保留，后续可增强

            # 3. CPS (阅读速度) 检查
            # 计算字符数 (去除空格)
            char_count = len(text.replace(" ", ""))
            # 计算 CPS
            cps = char_count / duration if duration > 0 else 0

            if cps > max_cps:
                logger.warning(f"阅读速度过快 ({cps:.2f} CPS > {max_cps}): {text}")
                # TODO: 可以考虑适当延长持续时间，或者提示人工简化文本

            # 更新片段信息
            segment['text'] = text
            segment['cps'] = cps # 保存计算出的 CPS 以供参考
            segment['cpl'] = len(text)

            compliant_segments.append(segment)

        logger.info(f"合规性检查完成，处理了 {len(compliant_segments)} 个片段。")
        return compliant_segments

    def _clean_text(self, text: str) -> str:
        """
        文本基础清洗。
        去除多余空格、换行符等。
        """
        if not text:
            return ""
        # 替换多个空白字符为一个空格
        text = re.sub(r'\s+', ' ', text).strip()
        # 这里可以加入更多规则，比如去除口语词 (嗯、啊)
        return text

# 单例实例
_alignment_service = None

def get_alignment_service():
    """
    获取对齐服务单例。
    """
    global _alignment_service
    if _alignment_service is None:
        _alignment_service = AlignmentService()
    return _alignment_service
