import re
import spacy
from loguru import logger
from typing import List, Dict, Any

class AlignmentService:
    """
    对齐与合规性检查服务
    (Combined version: Segmentation logic from 'jules-alignment-segmentation' + Export logic from 'feat/backend-pipeline-enhancement')
    """
    def __init__(self):
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
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return 'zh'
        return 'en'

    def check_netflix_compliance(self, segments: List[Dict[str, Any]], max_cpl=42, max_cps=20, force_single_line=True) -> List[Dict[str, Any]]:
        logger.info(f"开始 Netflix 合规性检查 (max_cpl={max_cpl}, max_cps={max_cps}, single_line={force_single_line})")
        compliant_segments = []
        for segment in segments:
            text = segment.get('text', "")
            text = self._clean_text(text)
            segment['text'] = text
            if not text:
                continue
            if len(text) > max_cpl:
                 logger.debug(f"行过长 ({len(text)} > {max_cpl}): {text}，正在尝试分割...")
                 sub_segments = self._recursive_split(segment, max_cpl)
                 for sub_seg in sub_segments:
                     self._calculate_metrics(sub_seg, max_cps)
                     compliant_segments.append(sub_seg)
            else:
                 self._calculate_metrics(segment, max_cps)
                 compliant_segments.append(segment)
        logger.info(f"合规性检查完成，原 {len(segments)} 个片段 -> 现 {len(compliant_segments)} 个片段。")
        return compliant_segments

    def _calculate_metrics(self, segment: Dict[str, Any], max_cps: int):
        text = segment['text']
        duration = segment['end'] - segment['start']
        char_count = len(text.replace(" ", ""))
        cps = char_count / duration if duration > 0 else 0
        if cps > max_cps:
            logger.warning(f"阅读速度过快 ({cps:.2f} CPS > {max_cps}): {text}")
        segment['cps'] = cps
        segment['cpl'] = len(text)

    def _recursive_split(self, segment: Dict[str, Any], max_cpl: int) -> List[Dict[str, Any]]:
        text = segment['text']
        if len(text) <= max_cpl:
            return [segment]
        lang = self._detect_lang(text)
        nlp = self._get_nlp(lang)
        doc = nlp(text)
        sents = [sent.text.strip() for sent in doc.sents]
        if len(sents) <= 1:
            parts = self._split_by_punctuation(text, lang)
        else:
            parts = sents
        if len(parts) <= 1:
             parts = self._split_by_length(text, max_cpl, lang)
        new_segments = self._realign_timestamps(segment, parts)
        final_segments = []
        for new_seg in new_segments:
            if len(new_seg['text']) > max_cpl:
                if new_seg['text'] == text:
                     logger.warning(f"无法进一步分割且仍然过长: {text}")
                     final_segments.append(new_seg)
                else:
                     final_segments.extend(self._recursive_split(new_seg, max_cpl))
            else:
                final_segments.append(new_seg)
        return final_segments

    def _split_by_punctuation(self, text: str, lang: str) -> List[str]:
        if lang == 'zh':
            pattern = r'([，。；？！])'
        else:
            pattern = r'([,;?!])'
        parts = re.split(pattern, text)
        result = []
        current = ""
        for part in parts:
            if re.match(pattern, part):
                current += part
                result.append(current)
                current = ""
            else:
                current += part
        if current:
            result.append(current)
        return [p.strip() for p in result if p.strip()]

    def _split_by_length(self, text: str, max_cpl: int, lang: str) -> List[str]:
        parts = []
        while len(text) > max_cpl:
            split_idx = max_cpl
            if lang == 'en':
                found_space = text.rfind(' ', 0, max_cpl)
                if found_space != -1:
                    split_idx = found_space + 1
            parts.append(text[:split_idx].strip())
            text = text[split_idx:].strip()
        if text:
            parts.append(text)
        return parts

    def _realign_timestamps(self, original_segment: Dict[str, Any], text_parts: List[str]) -> List[Dict[str, Any]]:
        start_time = original_segment['start']
        end_time = original_segment['end']
        total_duration = end_time - start_time
        parts_total_len = sum(len(p) for p in text_parts)
        new_segments = []
        current_time = start_time
        for part in text_parts:
            part_len = len(part)
            if part_len == 0: continue
            weight = part_len / parts_total_len if parts_total_len > 0 else 0
            seg_duration = total_duration * weight
            seg_end = current_time + seg_duration
            new_segments.append({
                "start": current_time,
                "end": seg_end,
                "text": part,
                "words": []
            })
            current_time = seg_end
        return new_segments

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # Export methods (from feat)
    def to_srt(self, segments: List[Dict[str, Any]]) -> str:
        output = ""
        for i, seg in enumerate(segments):
            start = self._format_timestamp_srt(seg['start'])
            end = self._format_timestamp_srt(seg['end'])
            text = seg['text']
            output += f"{i+1}\n{start} --> {end}\n{text}\n\n"
        return output

    def to_vtt(self, segments: List[Dict[str, Any]]) -> str:
        output = "WEBVTT\n\n"
        for i, seg in enumerate(segments):
            start = self._format_timestamp_vtt(seg['start'])
            end = self._format_timestamp_vtt(seg['end'])
            text = seg['text']
            output += f"{i+1}\n{start} --> {end}\n{text}\n\n"
        return output

    def to_ass(self, segments: List[Dict[str, Any]]) -> str:
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
        ms = int((seconds % 1) * 1000)
        s = int(seconds)
        m = s // 60
        h = m // 60
        s = s % 60
        m = m % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        return self._format_timestamp_srt(seconds).replace(",", ".")

    def _format_timestamp_ass(self, seconds: float) -> str:
        ms = int((seconds % 1) * 100)
        s = int(seconds)
        m = s // 60
        h = m // 60
        s = s % 60
        m = m % 60
        return f"{h}:{m:02d}:{s:02d}.{ms:02d}"

_alignment_service = None

def get_alignment_service():
    global _alignment_service
    if _alignment_service is None:
        _alignment_service = AlignmentService()
    return _alignment_service
