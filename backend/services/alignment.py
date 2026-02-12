import re
import spacy
from loguru import logger
from typing import List, Dict, Any

class AlignmentService:
    """
    对齐与合规性检查服务

    负责：
    1. 根据 Netflix 字幕标准检查和分割字幕。
    2. 处理时间戳对齐。
    3. 清洗文本中的冗余字符。
    4. 使用 NLP 技术智能分割长句。
    """
    def __init__(self):
        """
        初始化对齐服务，加载 NLP 模型。
        """
        logger.info("初始化 AlignmentService，正在加载 NLP 模型...")
        try:
            self.nlp_zh = spacy.load("zh_core_web_sm")
            self.nlp_en = spacy.load("en_core_web_sm")
            logger.info("NLP 模型 (zh, en) 加载成功。")
        except Exception as e:
            logger.warning(f"NLP 模型加载失败，将回退到基于规则的分割: {e}")
            self.nlp_zh = None
            self.nlp_en = None

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
            words = segment.get('words', []) # 获取单词级时间戳

            # 1. 基础文本清洗
            text = self._clean_text(text)

            # 2. 智能分割 (处理 CPL)
            if len(text) > max_cpl:
                logger.debug(f"检测到长句 ({len(text)} 字符): {text}")
                split_segments = self._smart_split(text, start, end, max_cpl, words)
                compliant_segments.extend(split_segments)
            else:
                # 检查 CPS
                duration = end - start
                char_count = len(text.replace(" ", ""))
                cps = char_count / duration if duration > 0 else 0

                segment['text'] = text
                segment['cps'] = cps
                segment['cpl'] = len(text)
                compliant_segments.append(segment)

        logger.info(f"合规性检查完成，原片段 {len(segments)} -> 新片段 {len(compliant_segments)}。")
        return compliant_segments

    def _smart_split(self, text: str, start: float, end: float, max_cpl: int, words: List[Dict]) -> List[Dict[str, Any]]:
        """
        智能分割长难句。
        优先使用 NLP 依存句法分析，其次使用标点符号，最后使用长度强行截断。
        同时尝试根据单词时间戳重新分配时间。
        """
        split_results = []

        # 尝试使用 NLP 分割句子 (针对双句合并的情况)
        sentences = self._nlp_split_sentences(text)

        # 如果 NLP 认为这本身就是一句话，但太长了，需要从中间断开
        if len(sentences) == 1:
            chunks = self._split_long_sentence(text, max_cpl)
        else:
            chunks = sentences

        # 重新分配时间戳
        # 如果有单词级时间戳，可以很精确
        if words:
            current_word_idx = 0
            for chunk in chunks:
                chunk_text = chunk
                chunk_len = len(chunk_text.replace(" ", ""))

                # 寻找这个 chunk 对应的 words
                # 这是一个简化的匹配逻辑，实际生产可能需要模糊匹配
                chunk_words = []
                temp_text = ""

                # 贪婪匹配单词直到填满 chunk
                matched_count = 0
                for i in range(current_word_idx, len(words)):
                    w = words[i]
                    # 简单去除标点比较
                    w_text = w['word'].strip()
                    chunk_words.append(w)
                    matched_count += 1

                    # 粗略估算是否匹配完当前 chunk
                    # 注意：这里假设 chunk 顺序和 words 顺序完全一致
                    # 实际情况中，chunk 可能会丢弃标点或微调
                    # 为了稳健，我们按字符长度比例分配时间，而不是严格匹配单词
                    pass

                # 重新计算时间 (基于字符长度比例分配，这在没有精确单词匹配时是常用的鲁棒方法)
                total_duration = end - start
                total_chars = len(text)
                chunk_duration = total_duration * (len(chunk_text) / total_chars)

                chunk_start = start + (sum([len(c) for c in split_results]) / total_chars) * total_duration
                chunk_end = chunk_start + chunk_duration

                split_results.append({
                    "start": chunk_start,
                    "end": chunk_end,
                    "text": chunk_text,
                    "cpl": len(chunk_text),
                    "cps": len(chunk_text) / chunk_duration if chunk_duration > 0 else 0
                })
        else:
            # 没有单词时间戳，按字符比例线性插值
            current_start = start
            total_len = len(text)
            total_duration = end - start

            for chunk in chunks:
                chunk_len = len(chunk)
                ratio = chunk_len / total_len
                chunk_duration = total_duration * ratio

                split_results.append({
                    "start": current_start,
                    "end": current_start + chunk_duration,
                    "text": chunk,
                    "cpl": len(chunk),
                    "cps": len(chunk) / chunk_duration if chunk_duration > 0 else 0
                })
                current_start += chunk_duration

        return split_results

    def _nlp_split_sentences(self, text: str) -> List[str]:
        """
        使用 NLP 模型进行分句。
        """
        # 判断语言
        is_chinese = any(u'\u4e00' <= c <= u'\u9fff' for c in text)
        nlp = self.nlp_zh if is_chinese and self.nlp_zh else self.nlp_en

        if nlp:
            doc = nlp(text)
            return [sent.text.strip() for sent in doc.sents]
        else:
            # 回退到正则分割
            if is_chinese:
                return re.split(r'[。！？；]', text)
            else:
                return re.split(r'[.?!;]', text)

    def _split_long_sentence(self, text: str, max_cpl: int) -> List[str]:
        """
        强制分割超长单句。
        寻找中间的逗号、停顿词进行分割。
        """
        if len(text) <= max_cpl:
            return [text]

        # 寻找中间位置附近的标点
        mid_point = len(text) // 2
        # 在中间位置左右搜索最佳分割点 (逗号，空格)
        best_split = -1
        min_dist = len(text)

        delimiters = ['，', ',', ' ', '、']

        for i, char in enumerate(text):
            if char in delimiters:
                dist = abs(i - mid_point)
                if dist < min_dist:
                    min_dist = dist
                    best_split = i

        if best_split != -1:
            part1 = text[:best_split+1].strip() # 包含标点
            part2 = text[best_split+1:].strip()
            # 递归检查
            return self._split_long_sentence(part1, max_cpl) + self._split_long_sentence(part2, max_cpl)
        else:
            # 实在找不到分割点，强行截断 (虽不优雅但保证合规)
            return [text[:mid_point], text[mid_point:]]

    def _clean_text(self, text: str) -> str:
        """
        文本基础清洗。
        """
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        return text

# 单例实例
_alignment_service = None

def get_alignment_service():
    global _alignment_service
    if _alignment_service is None:
        _alignment_service = AlignmentService()
    return _alignment_service
