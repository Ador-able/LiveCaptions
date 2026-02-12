import re
import math
from loguru import logger
from typing import List, Dict, Any, Optional
import spacy

class AlignmentService:
    """
    对齐与合规性检查服务

    负责：
    1. 根据 Netflix 字幕标准检查和分割字幕。
    2. 处理时间戳对齐。
    3. 清洗文本中的冗余字符。
    4. 导出多种字幕格式 (SRT, VTT, ASS)。
    """
    def __init__(self):
        logger.info("初始化 AlignmentService...")
        # 预加载 Spacy 模型
        try:
            self.nlp_zh = spacy.load("zh_core_web_sm")
            logger.info("加载中文 Spacy 模型成功")
        except OSError:
            logger.warning("未找到中文 Spacy 模型，将回退到简单分割")
            self.nlp_zh = None

        try:
            self.nlp_en = spacy.load("en_core_web_sm")
            logger.info("加载英文 Spacy 模型成功")
        except OSError:
            logger.warning("未找到英文 Spacy 模型，将回退到简单分割")
            self.nlp_en = None

    def check_netflix_compliance(self, segments: List[Dict[str, Any]], max_cpl=42, max_cps=20, force_single_line=True) -> List[Dict[str, Any]]:
        """
        检查并修复字幕以符合 Netflix 标准。

        参数:
        - segments: 原始字幕片段列表 (start, end, text)。
        - max_cpl: 每行最大字符数 (默认 42)。
        - max_cps: 每秒最大字符数 (默认 20)。
        - force_single_line: 是否强制单行字幕。

        返回:
        - compliant_segments: 处理后的字幕片段列表。
        """
        logger.info(f"开始 Netflix 合规性检查 (max_cpl={max_cpl}, max_cps={max_cps})")

        compliant_segments = []

        for segment in segments:
            text = segment['text']
            start = segment['start']
            end = segment['end']

            # 1. 基础文本清洗
            text = self._clean_text(text)
            if not text:
                continue

            # 2. 递归分割过长的行 (CPL 检查)
            split_segments = self._recursive_split(text, start, end, max_cpl)

            for sub_seg in split_segments:
                sub_text = sub_seg['text']
                sub_start = sub_seg['start']
                sub_end = sub_seg['end']
                duration = sub_end - sub_start

                # 3. CPS (阅读速度) 检查
                char_count = len(sub_text.replace(" ", ""))
                cps = char_count / duration if duration > 0.1 else 0

                # 如果 CPS 过高，尝试微调时间轴（如果允许重叠或微调）
                # 这里我们只标记，不自动拉长时间轴以免重叠
                if cps > max_cps:
                    logger.debug(f"阅读速度过快 ({cps:.2f} > {max_cps}): {sub_text}")

                sub_seg['cps'] = cps
                sub_seg['cpl'] = len(sub_text)

                compliant_segments.append(sub_seg)

        logger.info(f"合规性检查完成: {len(segments)} -> {len(compliant_segments)} 片段")
        return compliant_segments

    def _recursive_split(self, text: str, start: float, end: float, max_cpl: int) -> List[Dict[str, Any]]:
        """
        递归分割过长的文本片段，同时按比例分配时间轴。
        优先使用 NLP 分句，其次标点，最后强制截断。
        """
        if len(text) <= max_cpl:
            return [{"start": start, "end": end, "text": text}]

        # 尝试寻找最佳分割点
        split_index = self._find_best_split_point(text, max_cpl)

        if split_index == -1 or split_index >= len(text):
            # 无法找到好的分割点，或者分割点无效（未缩短文本），强制按 max_cpl 分割
            split_index = max_cpl

        part1_text = text[:split_index].strip()
        part2_text = text[split_index:].strip()

        # 按字符长度比例分配时间
        total_len = len(text)
        part1_len = len(part1_text)

        if total_len == 0:
            return []

        duration = end - start
        split_time = start + (duration * (part1_len / total_len))

        result = []
        # 递归处理两部分
        if part1_text:
            result.extend(self._recursive_split(part1_text, start, split_time, max_cpl))
        if part2_text:
            result.extend(self._recursive_split(part2_text, split_time, end, max_cpl))

        return result

    def _find_best_split_point(self, text: str, max_cpl: int) -> int:
        """
        寻找最佳分割点。优先寻找句子边界，然后是标点符号。
        """
        if len(text) <= max_cpl:
            return -1

        search_end = min(len(text), max_cpl + 10)
        search_text = text[:search_end]

        # 1. 尝试使用 Spacy 检测句子边界
        is_chinese = sum(1 for char in search_text if '\u4e00' <= char <= '\u9fff') > len(search_text) / 2
        nlp = self.nlp_zh if is_chinese else self.nlp_en

        best_split = -1

        if nlp:
            try:
                doc = nlp(search_text)
                for sent in doc.sents:
                    # 如果句子结束位置在 max_cpl 范围内，这是一个很好的分割点
                    if sent.end_char <= max_cpl:
                        best_split = sent.end_char
                    else:
                        break
            except Exception:
                pass

        if best_split > 0:
            return best_split

        # 2. 标点回退
        punctuations = ["。", "！", "？", ".", "!", "?", "；", ";", "，", ","]
        for i in range(min(len(text) - 1, max_cpl), 0, -1):
             if text[i] in punctuations:
                return i + 1

        # 3. 空格回退
        for i in range(min(len(text) - 1, max_cpl), 0, -1):
            if text[i] == " ":
                return i

        return -1

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def to_srt(self, segments: List[Dict[str, Any]]) -> str:
        """转换为 SRT 格式"""
        output = ""
        for i, seg in enumerate(segments):
            start = self._format_timestamp_srt(seg['start'])
            end = self._format_timestamp_srt(seg['end'])
            text = seg['text']
            output += f"{i+1}\n{start} --> {end}\n{text}\n\n"
        return output

    def to_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """转换为 WebVTT 格式"""
        output = "WEBVTT\n\n"
        for i, seg in enumerate(segments):
            start = self._format_timestamp_vtt(seg['start'])
            end = self._format_timestamp_vtt(seg['end'])
            text = seg['text']
            output += f"{i+1}\n{start} --> {end}\n{text}\n\n"
        return output

    def to_ass(self, segments: List[Dict[str, Any]]) -> str:
        """转换为 ASS 格式"""
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,1,1,1,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        output = header
        for seg in segments:
            start = self._format_timestamp_ass(seg['start'])
            end = self._format_timestamp_ass(seg['end'])
            text = seg['text']
            output += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
        return output

    def _format_timestamp_srt(self, seconds: float) -> str:
        """00:00:00,000"""
        ms = int((seconds % 1) * 1000)
        s = int(seconds)
        m = s // 60
        h = m // 60
        s = s % 60
        m = m % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """00:00:00.000"""
        return self._format_timestamp_srt(seconds).replace(",", ".")

    def _format_timestamp_ass(self, seconds: float) -> str:
        """0:00:00.00"""
        ms = int((seconds % 1) * 100) # ASS uses centiseconds
        s = int(seconds)
        m = s // 60
        h = m // 60
        s = s % 60
        m = m % 60
        return f"{h}:{m:02d}:{s:02d}.{ms:02d}"

# 单例
_alignment_service = None

def get_alignment_service():
    global _alignment_service
    if _alignment_service is None:
        _alignment_service = AlignmentService()
    return _alignment_service
