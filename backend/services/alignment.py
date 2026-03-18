
import os
import re
from loguru import logger
from typing import List, Dict, Any, Optional
from backend.services.llm import LLMService

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
        # 初始化 LLM 服务
        self.llm_service = LLMService()

    def check_netflix_compliance(self, segments: List[Dict[str, Any]], max_cpl=42, max_cps=20, lang: str = "en", use_word_timestamps: bool = True) -> List[Dict[str, Any]]:
        """
        检查并修复字幕以符合 Netflix 标准。
        使用批量 LLM 分句一次性处理所有超长行。
        重点优化时间戳准确性，确保字幕显示时间准确。

        参数:
        - segments: 原始字幕片段列表。
        - max_cpl: 每行最大字符数 (默认 42)。
        - max_cps: 每秒最大字符数 (默认 20)。
        - lang: 字幕语言 (如 'zh', 'en')。**必须传入**。
        - use_word_timestamps: 是否使用词时间戳 (True: 词时间戳, False: 句时间戳)。

        返回:
        - compliant_segments: 处理后的字幕片段列表。
        """
        logger.info(f"开始 Netflix 合规性检查与时间戳优化 (lang={lang}, max_cpl={max_cpl}, max_cps={max_cps}, use_word_timestamps={use_word_timestamps})")

        if use_word_timestamps:
            segments = self._optimize_timestamps_using_words(segments)
        else:
            logger.info("使用句时间戳模式")

        # 阶段 1: 清洗所有文本，收集超长行以供批量分割
        long_texts = []  # (segment_index, text)
        cleaned_segments = []
        
        for i, segment in enumerate(segments):
            text = segment.get('text', "")
            text = self._clean_text(text)
            segment['text'] = text
            cleaned_segments.append(segment)
            
            if text and len(text) > max_cpl:
                long_texts.append((i, text))
        
        # 阶段 2: 通过 LLM 一次性批量分割所有超长行
        pre_split_map = {}  # segment_index -> List[str] (分割结果)
        if long_texts:
            logger.info(f"批量分割 {len(long_texts)} 个超长行")
            texts_to_split = [t for _, t in long_texts]
            batch_results = self.llm_service.batch_split_texts(texts_to_split, lang, max_length=max_cpl)
            
            for batch_idx, (seg_idx, _) in enumerate(long_texts):
                splits = batch_results.get(batch_idx, None)
                if splits and len(splits) > 1:
                    pre_split_map[seg_idx] = splits
        
        # 阶段 3: 应用分割结果，构建合规片段
        compliant_segments = []
        for i, segment in enumerate(cleaned_segments):
            text = segment.get('text', "")
            if not text:
                continue

            if len(text) > max_cpl:
                logger.debug(f"行过长 ({len(text)} > {max_cpl}): {text}，正在尝试分割...")
                sub_segments = self._recursive_split(segment, max_cpl, lang, pre_split_map.get(i))

                for sub_seg in sub_segments:
                    self._calculate_metrics(sub_seg, max_cps)
                    compliant_segments.append(sub_seg)
            else:
                self._calculate_metrics(segment, max_cps)
                compliant_segments.append(segment)

        logger.info(f"合规性检查与时间戳优化完成，原 {len(segments)} 个片段 -> 现 {len(compliant_segments)} 个片段。")
        return compliant_segments

    def _optimize_timestamps_using_words(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        利用词级时间戳精确优化字幕的开始和结束时间。
        确保字幕在语音结束后立即消失，并且时间戳准确。
        """
        if not segments:
            return []
            
        optimized_segments = []
        
        for i, seg in enumerate(segments):
            seg = seg.copy()
            words = seg.get('words', [])
            
            # 如果有词级时间戳，利用它们精确调整
            if words and len(words) > 0:
                # 使用第一个词的开始时间作为字幕开始
                seg['start'] = words[0]['start']
                # 使用最后一个词的结束时间作为字幕结束
                seg['end'] = words[-1]['end']
            
            # 确保字幕有最小显示时间（至少 0.5 秒）
            duration = seg['end'] - seg['start']
            if duration < 0.5:
                seg['end'] = seg['start'] + 0.5
            
            # 确保字幕不会太长（最多 8 秒）
            if duration > 8.0:
                text_len = len(seg['text'].replace(' ', ''))
                # 根据文本长度计算合理时长
                ideal_duration = min(8.0, max(0.5, text_len / 12))  # 约 12 字符/秒
                seg['end'] = seg['start'] + ideal_duration
            
            optimized_segments.append(seg)
        
        # 确保字幕之间没有间隙或重叠
        for i in range(1, len(optimized_segments)):
            prev_seg = optimized_segments[i - 1]
            curr_seg = optimized_segments[i]
            
            # 如果前一个字幕结束时间晚于当前字幕开始时间，调整当前字幕开始时间
            if curr_seg['start'] < prev_seg['end']:
                # 给前一个字幕留 0.1 秒的缓冲
                curr_seg['start'] = prev_seg['end'] + 0.05
                # 确保当前字幕仍有足够的显示时间
                if curr_seg['end'] - curr_seg['start'] < 0.3:
                    curr_seg['end'] = curr_seg['start'] + 0.3
        
        return optimized_segments


    def _calculate_metrics(self, segment: Dict[str, Any], max_cps: int):
        """计算并更新片段的 CPL 和 CPS"""
        text = segment['text']
        duration = segment['end'] - segment['start']

        char_count = len(text.replace(" ", ""))
        cps = char_count / duration if duration > 0.1 else 0

        if cps > max_cps:
            logger.debug(f"阅读速度过快 ({cps:.2f} CPS > {max_cps}): {text}")

        segment['cps'] = cps
        segment['cpl'] = len(text)

    def _recursive_split(self, segment: Dict[str, Any], max_cpl: int, lang: str, pre_computed_splits: List[str] = None) -> List[Dict[str, Any]]:
        """
        递归分割过长的片段。
        
        参数:
        - lang: 强制指定语言，不再自动检测。
        - pre_computed_splits: 从批量处理预计算的 LLM 分割结果（仅首次调用时使用）
        """
        text = segment['text']
        if len(text) <= max_cpl:
            return [segment]

        if not lang:
            lang = "en" # 默认回退到英文
             
        parts = []
        
        # 尝试 1: 使用预计算的 LLM 分割结果（来自批量处理），否则单独调用 LLM
        if pre_computed_splits and len(pre_computed_splits) > 1:
            parts = pre_computed_splits
        else:
            try:
                sents = self.llm_service.split_text_into_sentences(text, lang)
                if len(sents) > 1:
                    parts = sents
            except Exception as e:
                logger.warning(f"LLM 分割失败: {e}")

        # 尝试 2: 标点分割
        if not parts:
            parts = self._split_by_punctuation(text, lang)

        # 尝试 3: 强制按长度分割
        if len(parts) <= 1:
            parts = self._split_by_length(text, max_cpl, lang)

        # 重新计算时间轴
        new_segments = self._realign_timestamps(segment, parts)

        # 递归检查结果（递归调用时不再使用预计算分割结果）
        final_segments = []
        for new_seg in new_segments:
            if len(new_seg['text']) > max_cpl:
                if new_seg['text'] == text:
                    logger.warning(f"无法进一步分割且仍然过长: {text}")
                    final_segments.append(new_seg)
                else:
                    final_segments.extend(self._recursive_split(new_seg, max_cpl, lang))
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
                # 往回找空格，避免切断单词
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
        
        # 计算总的有效字符长度
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
                "words": [] # 分割后暂时丢弃 words 详情，若需精确可以基于 words 列表重新划分
            })

            current_time = seg_end

        return new_segments

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
        # 构建基础头部和样式
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
            # 始终使用 Default 样式
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
