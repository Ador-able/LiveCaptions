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
    """
    def __init__(self):
        # 懒加载 NLP 模型
        self.nlp_models = {}

    def _get_nlp(self, lang: str):
        if lang not in self.nlp_models:
            model_name = "zh_core_web_sm" if lang == "zh" else "en_core_web_sm"
            try:
                logger.info(f"正在加载 Spacy 模型: {model_name}")
                self.nlp_models[lang] = spacy.load(model_name)
            except OSError:
                logger.error(f"Spacy 模型 {model_name} 未找到，请确保已下载。")
                raise
        return self.nlp_models[lang]

    def _detect_lang(self, text: str) -> str:
        """简单的语言检测: 包含中文字符则视为中文"""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return 'zh'
        return 'en'

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
            text = segment.get('text', "")
            # 1. 基础文本清洗
            text = self._clean_text(text)
            segment['text'] = text # 更新清洗后的文本

            if not text:
                continue

            # 2. CPL (字符长度) 检查与分割
            if len(text) > max_cpl:
                 logger.debug(f"行过长 ({len(text)} > {max_cpl}): {text}，正在尝试分割...")
                 sub_segments = self._recursive_split(segment, max_cpl)

                 # 对分割后的片段进行后处理（计算 CPS 等）
                 for sub_seg in sub_segments:
                     self._calculate_metrics(sub_seg, max_cps)
                     compliant_segments.append(sub_seg)
            else:
                 self._calculate_metrics(segment, max_cps)
                 compliant_segments.append(segment)

        logger.info(f"合规性检查完成，原 {len(segments)} 个片段 -> 现 {len(compliant_segments)} 个片段。")
        return compliant_segments

    def _calculate_metrics(self, segment: Dict[str, Any], max_cps: int):
        """计算并更新片段的 CPL 和 CPS"""
        text = segment['text']
        duration = segment['end'] - segment['start']

        # 3. CPS (阅读速度) 检查
        char_count = len(text.replace(" ", ""))
        cps = char_count / duration if duration > 0 else 0

        if cps > max_cps:
            logger.warning(f"阅读速度过快 ({cps:.2f} CPS > {max_cps}): {text}")
            # TODO: 可以考虑适当延长持续时间，或者提示人工简化文本

        segment['cps'] = cps
        segment['cpl'] = len(text)

    def _recursive_split(self, segment: Dict[str, Any], max_cpl: int) -> List[Dict[str, Any]]:
        """
        递归分割过长的片段。
        策略优先级：
        1. Spacy 句子分割
        2. 标点符号分割 (Clause)
        3. 强制截断 (Fallback)
        """
        text = segment['text']
        if len(text) <= max_cpl:
            return [segment]

        lang = self._detect_lang(text)
        nlp = self._get_nlp(lang)

        # 尝试 1: 按句子分割 (Spacy)
        doc = nlp(text)
        sents = [sent.text.strip() for sent in doc.sents]

        # 如果 Spacy 认为只有一句话，或者分割无效（没有减少长度压力），则尝试标点分割
        if len(sents) <= 1:
            parts = self._split_by_punctuation(text, lang)
        else:
            parts = sents

        # 如果标点分割也无效（比如一句话很长且没标点），尝试按空格/长度强制分割
        if len(parts) <= 1:
             parts = self._split_by_length(text, max_cpl, lang)

        # 重新计算时间轴
        new_segments = self._realign_timestamps(segment, parts)

        # 递归检查结果，如果拆分后的部分仍然过长，继续拆分
        final_segments = []
        for new_seg in new_segments:
            if len(new_seg['text']) > max_cpl:
                # 防止无限递归：如果拆分没有产生任何变化，则停止拆分
                if new_seg['text'] == text:
                     logger.warning(f"无法进一步分割且仍然过长: {text}")
                     final_segments.append(new_seg)
                else:
                     final_segments.extend(self._recursive_split(new_seg, max_cpl))
            else:
                final_segments.append(new_seg)

        return final_segments

    def _split_by_punctuation(self, text: str, lang: str) -> List[str]:
        """按标点符号分割"""
        if lang == 'zh':
            # 中文标点
            pattern = r'([，。；？！])'
        else:
            # 英文标点
            pattern = r'([,;?!])'

        # split 包含分隔符
        parts = re.split(pattern, text)
        # parts 如 ['你好', '，', '世界', '。', '']

        result = []
        current = ""
        for part in parts:
            if re.match(pattern, part):
                current += part # 将标点附在上一句末尾
                result.append(current)
                current = ""
            else:
                current += part

        if current:
            result.append(current)

        return [p.strip() for p in result if p.strip()]

    def _split_by_length(self, text: str, max_cpl: int, lang: str) -> List[str]:
        """按长度强制分割"""
        parts = []
        while len(text) > max_cpl:
            # 寻找最佳截断点（空格）
            split_idx = max_cpl
            if lang == 'en':
                # 往回找空格
                found_space = text.rfind(' ', 0, max_cpl)
                if found_space != -1:
                    split_idx = found_space + 1 # 保留空格或切掉

            parts.append(text[:split_idx].strip())
            text = text[split_idx:].strip()

        if text:
            parts.append(text)
        return parts

    def _realign_timestamps(self, original_segment: Dict[str, Any], text_parts: List[str]) -> List[Dict[str, Any]]:
        """
        根据分割后的文本重新对齐时间戳。
        暂时使用字符长度线性插值。
        """
        start_time = original_segment['start']
        end_time = original_segment['end']
        total_duration = end_time - start_time
        original_text = original_segment['text']

        # 计算总的有效字符长度（去除空格可能更准，但这里简化）
        # 使用 parts 的总长度作为分母，确保时间轴填满
        parts_total_len = sum(len(p) for p in text_parts)

        new_segments = []
        current_time = start_time

        for part in text_parts:
            part_len = len(part)
            if part_len == 0: continue

            # 线性插值
            weight = part_len / parts_total_len if parts_total_len > 0 else 0
            seg_duration = total_duration * weight
            seg_end = current_time + seg_duration

            new_segments.append({
                "start": current_time,
                "end": seg_end,
                "text": part,
                "words": [] # 分割后暂时丢弃 words 详情
            })

            current_time = seg_end

        return new_segments

    def _clean_text(self, text: str) -> str:
        """
        文本基础清洗。
        去除多余空格、换行符等。
        """
        if not text:
            return ""
        # 替换多个空白字符为一个空格
        text = re.sub(r'\s+', ' ', text).strip()
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
