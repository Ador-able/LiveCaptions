import os
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
import openai
from typing import List, Optional, Dict, Any, Type, TypeVar, Callable
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, Field
import instructor

from ..config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL

T = TypeVar("T", bound=BaseModel)


class TranslationResponse(BaseModel):
    translations: Dict[str, str] = Field(..., description="ID到译文的映射 (Key must be ID string)")


class PolishResponse(BaseModel):
    updates: Dict[str, str] = Field(..., description="字幕编号到润色后文本的映射 (只返回需要修改的条目)")


class SentenceSplitResponse(BaseModel):
    sentences: List[str] = Field(..., description="分割后的句子列表")


class BatchSentenceSplitResponse(BaseModel):
    results: Dict[str, List[str]] = Field(..., description="ID到分割后句子列表的映射")


class LLMService:
    """
    LLM 翻译服务

    核心特性：
    1. 滑窗翻译：使用大上下文窗口进行翻译，确保连贯性
    2. 三步翻译：直译 -> 反思 -> 意译
    3. 重试机制：使用 tenacity 保证稳定性
    4. 结构化输出：使用 Instructor + Pydantic 验证响应格式
    5. 并发翻译：使用 ThreadPoolExecutor 并发翻译
    """

    # 语言对特定的翻译指南配置
    LANG_PAIR_GUIDES = {
        (
            "ja",
            "zh",
        ): """
        [日语→中文翻译核心原则]
        1. 敬语不必逐字译，转化为自然中文语气
        2. 口语语气词（ね、よ、な等）转化为中文口语表达
        3. 调整语序为主谓宾结构
        4. 避免生硬直译，理解意思后用地道中文表达
        """,
        (
            "en",
            "zh",
        ): """
        [英语→中文翻译特别注意]
        1. **文化差异**：注意文化背景差异，适当意译而非直译。
        2. **专有名词**：人名、地名、品牌名使用常见译名。
        3. **口语表达**：英语中的缩略语（don't, can't, gonna等）转换为自然的中文口语。
        4. **长句拆分**：英语长句可适当拆分为多个中文短句，提高可读性。
        """,
        (
            "zh",
            "en",
        ): """
        [中文→英语翻译特别注意]
        1. **文化特色**：中国特色词汇（如成语、歇后语）可采用意译或加注的方式。
        2. **名字拼音**：中文人名使用标准拼音，姓在前名在后。
        3. **简洁表达**：中文的修饰语较多，英语中可适当简化，保持核心意思。
        """,
    }

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base_url or OPENAI_BASE_URL
        self.model = model or LLM_MODEL

        if not self.api_key:
            logger.warning("未配置 OPENAI_API_KEY，LLM 功能将无法工作。")
            self.client = None
        else:
            headers = {"x-ark-moderation-scene": "skip-ark-moderation"}
            openai_client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url, default_headers=headers)
            self.client = instructor.from_openai(openai_client)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_llm(self, messages: List[Dict[str, str]], temp: float = 0.3, json_mode: bool = False) -> str:
        if not self.client:
            raise RuntimeError("LLM client not initialized")

        logger.info(f"LLM Request Messages:\n{json.dumps(messages, ensure_ascii=False, indent=2)}")

        kwargs = {"model": self.model, "messages": messages, "temperature": temp, "timeout": 300}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_llm_structured(self, messages: List[Dict[str, str]], response_model: Type[T], temp: float = 0.1) -> T:
        try:
            logger.info(f"LLM Structured Request Messages:\n{json.dumps(messages, ensure_ascii=False, indent=2)}")
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, response_model=response_model, temperature=temp, timeout=300
            )
            return response
        except Exception as e:
            logger.error(f"Structured LLM call failed: {e}")
            raise e

    def translate_full_text(
        self,
        segments: List[Dict[str, Any]],
        source_lang: str,
        target_lang: str,
        video_description: str = "",
        progress_callback: Callable[[int, int], None] = None,
    ) -> List[Dict[str, Any]]:
        """
        使用滑窗机制并发翻译所有片段

        Args:
            segments: 原始字幕片段列表
            source_lang: 源语言代码 (如 'en', 'ja')
            target_lang: 目标语言代码 (如 'zh', 'en')
            video_description: 视频简介/背景信息，帮助AI更好地理解内容
            progress_callback: 可选的进度回调函数，回调参数为 (已完成块数, 总块数)

        Returns:
            翻译后的字幕片段列表
        """
        if not segments:
            return []

        logger.info(f"开始滑窗翻译，共 {len(segments)} 个片段。")

        # 步骤1：为每个片段添加唯一ID（1-based），方便后续映射
        all_segments = []
        for i, seg in enumerate(segments):
            seg_copy = seg.copy()
            seg_copy["_id"] = i + 1
            all_segments.append(seg_copy)

        # 步骤2：将片段切分为多个翻译块
        # 每个块包含：核心待翻译内容 + 上文上下文 + 下文上下文
        TARGET_CORE_SIZE = 1200  # 核心内容字符数目标
        TARGET_CONTEXT_SIZE = 500  # 上下文字符数目标

        blocks = []
        current_idx = 0

        while current_idx < len(all_segments):
            # 2.1 确定当前块的核心内容
            core_ids = []
            core_char_count = 0
            start_core_idx = current_idx
            end_core_idx = current_idx

            while end_core_idx < len(all_segments):
                seg = all_segments[end_core_idx]
                seg_len = len(seg["text"])
                # 如果加入当前片段会超过目标大小，且已有内容，则停止
                if core_char_count + seg_len > TARGET_CORE_SIZE and core_char_count > 0:
                    break
                core_ids.append(seg["_id"])
                core_char_count += seg_len
                end_core_idx += 1

            # 2.2 收集上文（Pre-Context）
            pre_ids = []
            pre_char_count = 0
            pre_idx = start_core_idx - 1
            while pre_idx >= 0:
                seg = all_segments[pre_idx]
                seg_len = len(seg["text"])
                if pre_char_count + seg_len > TARGET_CONTEXT_SIZE:
                    break
                pre_ids.insert(0, seg["_id"])  # 插入到开头保持顺序
                pre_char_count += seg_len
                pre_idx -= 1

            # 2.3 收集下文（Post-Context）
            post_ids = []
            post_char_count = 0
            post_idx = end_core_idx
            while post_idx < len(all_segments):
                seg = all_segments[post_idx]
                seg_len = len(seg["text"])
                if post_char_count + seg_len > TARGET_CONTEXT_SIZE:
                    break
                post_ids.append(seg["_id"])
                post_char_count += seg_len
                post_idx += 1

            # 2.4 将块加入列表
            blocks.append({"core": core_ids, "pre": pre_ids, "post": post_ids})

            # 移动到下一个块的起始位置
            current_idx = end_core_idx

        logger.info(f"生成了 {len(blocks)} 个翻译任务块。")

        # 步骤3：并发翻译所有块
        translation_map = {}  # 存储翻译结果: {segment_id: translated_text}
        video_context = video_description.strip() if video_description else "无"

        def _translate_block(idx, block):
            """
            翻译单个块的内部函数

            Args:
                idx: 块索引（用于日志）
                block: 块数据 {"core": [...], "pre": [...], "post": [...]}

            Returns:
                {segment_id: translated_text} 字典
            """
            core_ids = block["core"]
            pre_ids = block["pre"]
            post_ids = block["post"]

            logger.info(f"翻译块 {idx+1}/{len(blocks)}: Core ID {core_ids[0]}-{core_ids[-1]}")

            # 构建ID到片段的映射，方便快速查找
            all_needed_ids = set(core_ids + pre_ids + post_ids)
            ui_map = {s["_id"]: s for s in all_segments if s["_id"] in all_needed_ids}

            def format_seg(sid):
                """格式化单个片段为 <ID> 文本 的形式"""
                s = ui_map[sid]
                return f"<{sid}> {s['text']}"

            # 格式化上下文和核心内容
            pre_text = "\n".join([format_seg(sid) for sid in pre_ids])
            core_text = "\n".join([format_seg(sid) for sid in core_ids])
            post_text = "\n".join([format_seg(sid) for sid in post_ids])

            # 针对特定语言对的翻译指南（从配置字典中获取）
            lang_specific_guide = self.LANG_PAIR_GUIDES.get((source_lang, target_lang), "")

            prompt = f"""
            你是一名资深的影视字幕翻译专家，曾在知名字幕组工作多年。请将以下 {source_lang} 字幕片段的核心部分翻译成地道、自然的 {target_lang}。

            [视频背景信息] (仅供参考)
            {video_context}

            [上文 Context] (仅供参考，无需翻译)
            {pre_text if pre_text else "(无)"}

            [核心待翻译内容] (***** 请翻译这部分 *****)
            {core_text}

            [下文 Context] (仅供参考，无需翻译)
            {post_text if post_text else "(无)"}

            {lang_specific_guide}

            [核心翻译要求 - 字幕组标准]
            1. **先理解，再翻译**：不要逐字直译！先阅读完整上下文，理解当前场景和对话逻辑，再用最自然的中文表达出来。
            2. **场景化翻译**：
               - 根据上下文判断这是什么场景（综艺、访谈、戏剧等）
               - 理解人物关系和说话语气
               - 翻译要符合该场景下的说话方式
            3. **智能润色与重构**：
               - ASR 语音识别的原文往往是混乱的、碎片化的
               - 根据上下文构建场景画面，理解当前正在发生什么
               - 结合凌乱的碎片文字，边推测边补全，还原说话人的真实意图
               - 对于只有一两个字的碎片条目，将其含义合并到相邻条目中，该条目译文输出空字符串 ""
               - 最终输出的每条字幕都必须是通顺、自然、易懂的完整表达
            4. **避免生硬直译的反例**：
               - ❌ "标题呼叫" → ✅ "报幕"
            5. **口语化处理**：
               - 字幕是给人看的，要像真实说话一样
               - 适当使用语气词（"哦"、"啊"、"呢"、"吧"、"啦"）
               - 避免过于书面化的表达
            6. **保持原意**：虽然要意译，但不能改变原文的核心意思
            7. **符合 Netflix 字幕标准**
            """

            result = {}
            try:
                # 调用 LLM 进行翻译
                response: TranslationResponse = self._call_llm_structured(
                    [{"role": "user", "content": prompt}], response_model=TranslationResponse
                )

                data = response.translations

                # 收集翻译结果，只保留核心部分的翻译
                for id_str, text in data.items():
                    try:
                        id_int = int(id_str)
                        if id_int in core_ids:
                            result[id_int] = text
                    except ValueError:
                        pass

            except Exception as e:
                logger.error(f"块 {idx+1} 翻译失败: {e}")
                # 失败策略：保留原文
                for cid in core_ids:
                    result[cid] = ui_map.get(cid, {}).get("text", "")

            return result

        # 确定并发数（最多10个）
        max_workers = min(10, max(1, len(blocks)))
        logger.info(f"使用 {max_workers} 并发翻译 {len(blocks)} 个块")

        # 使用线程池并发执行翻译
        completed_blocks = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_translate_block, idx, block): idx for idx, block in enumerate(blocks)}
            # 收集完成的结果
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    block_result = future.result()
                    translation_map.update(block_result)
                    completed_blocks += 1
                    if progress_callback:
                        progress_callback(completed_blocks, len(blocks))
                except Exception as e:
                    logger.error(f"块 {idx+1} 并发翻译异常: {e}")

        # 步骤4：组装最终结果
        final_segments = []
        for seg in all_segments:
            sid = seg["_id"]
            trans_text = translation_map.get(sid, seg["text"])  # 如果没有翻译结果则回退到原文

            # 跳过空译文（LLM标记为已合并到相邻条目的碎片）
            if trans_text is not None and trans_text.strip() == "":
                continue

            # 构建最终片段
            new_seg = seg.copy()
            del new_seg["_id"]  # 清理临时ID
            new_seg["original_text"] = seg["text"]
            new_seg["text"] = trans_text
            final_segments.append(new_seg)

        logger.info(f"翻译完成，共 {len(final_segments)} 个片段。")

        # 翻译后整体润色阶段（通用）
        if len(final_segments) > 0:
            logger.info("开始翻译后整体润色阶段...")
            final_segments = self._polish_translation(final_segments, source_lang, target_lang)

        return final_segments

    def split_text_into_sentences(self, text: str, lang: str = "en") -> List[str]:
        if not text:
            return []

        results = self.batch_split_texts([text], lang)
        return results.get(0, [text])

    def _check_and_simplify_repetitive_text(self, text: str) -> Optional[List[str]]:
        if not text or len(text) < 6:
            return None

        try:
            match = re.fullmatch(r"(.+?)\1+$", text)
            if match:
                unit = match.group(1)
                if not unit:
                    return None
                count = len(text) // len(unit)
                if count >= 3:
                    logger.info(f"检测到重复文本 (长度 {len(text)}), 简化为 3 次重复:Prefix '{unit}'")
                    return [unit * 3]
        except Exception:
            pass

        return None

    def batch_split_texts(
        self, texts: List[str], lang: str = "en", batch_size: int = 20, max_workers: int = 10, max_length: int = None
    ) -> Dict[int, List[str]]:
        if not texts:
            return {}

        all_results: Dict[int, List[str]] = {}
        batch_ready_texts = []

        for i, t in enumerate(texts):
            if not t or not t.strip():
                continue

            simplified = self._check_and_simplify_repetitive_text(t)
            if simplified:
                all_results[i] = simplified
                continue

            batch_ready_texts.append((i, t))

        if not batch_ready_texts:
            return all_results

        logger.info(
            f"批量 LLM 分割句子: {len(batch_ready_texts)} 条需 LLM 处理 (共 {len(texts)} 条), lang={lang}, batch_size={batch_size}"
        )

        batches = []
        for start in range(0, len(batch_ready_texts), batch_size):
            batches.append(batch_ready_texts[start : start + batch_size])

        def _process_batch(batch: list) -> Dict[int, List[str]]:
            items_text = ""
            id_to_orig_idx = {}
            for batch_idx, (orig_idx, text) in enumerate(batch):
                bid = str(batch_idx + 1)
                id_to_orig_idx[bid] = orig_idx
                items_text += f"\n<{bid}> {text}"

            len_rule = ""
            if max_length:
                len_rule = f"3. 适度拆分长句：如果单句明显超过 {max_length} 个字符，请在逻辑停顿处（逗号、分号）或连接两个完整子句的连词（如 '但是'、'然后'、'so'、'but'）前进行拆分。切勿强行拆分短句。"
            else:
                len_rule = "3. 不要把句子拆得太碎（例如不要在逗号处强行拆分，除非句子太长）。"

            prompt = f"""
任务：将以下编号文本各自分割成自然的句子或子句列表。

核心原则：只在语义转折或不同动作切换时才拆分，严禁破坏短语完整性。

要求：
1. 保持原意不变，不增删内容。
2. 识别句子自然边界（句号、问号、感叹号）。
{len_rule}
4. [重要] 禁止过度拆分：
   - 禁止在 "A和B"、"A and B" 这种名词并列结构中间拆分。
   - 禁止把单个连词（如 "和"、"与"、"and"、"but"、"so"）单独拆出来做为一句。
   - 只有当连词连接的是两个完整的句子或动作时（例如 "他去了超市，然后买了很多东西"），才建议拆分。

示例：
- [错误] "Gavan", "和", "Jell互相舔哦" -> [正确] "Gavan和Jell互相舔哦"
- [错误] "我喜欢", "苹果和香蕉" -> [正确] "我喜欢苹果和香蕉"
- [错误] "Although it rained", "but", "we went out" -> [正确] "Although it rained", "but we went out"

待分割文本：
{items_text}
"""

            batch_results = {}
            try:
                response: BatchSentenceSplitResponse = self._call_llm_structured(
                    [{"role": "user", "content": prompt}], response_model=BatchSentenceSplitResponse
                )

                for bid, sentences in response.results.items():
                    orig_idx = id_to_orig_idx.get(str(bid))
                    if orig_idx is not None:
                        batch_results[orig_idx] = [s.strip() for s in sentences if s.strip()]

            except Exception as e:
                logger.error(f"批量 LLM 分句失败: {e}")

            for bid, orig_idx in id_to_orig_idx.items():
                if orig_idx not in batch_results:
                    for _, (oi, ot) in enumerate(batch):
                        if oi == orig_idx:
                            batch_results[orig_idx] = [ot]
                            break

            return batch_results

        if len(batches) == 1:
            all_results = _process_batch(batches[0])
        else:
            actual_workers = min(max_workers, len(batches))
            logger.info(f"使用 {actual_workers} 并发处理 {len(batches)} 个分句批次")

            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                futures = {executor.submit(_process_batch, batch): batch_idx for batch_idx, batch in enumerate(batches)}
                for future in as_completed(futures):
                    try:
                        batch_result = future.result()
                        all_results.update(batch_result)
                    except Exception as e:
                        logger.error(f"并发分句批次异常: {e}")

        for orig_idx, text in enumerate(texts):
            if text and text.strip() and orig_idx not in all_results:
                all_results[orig_idx] = [text]

        logger.info(f"批量分句完成，共处理 {len(all_results)} 条")
        return all_results

    def _polish_translation(
        self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str
    ) -> List[Dict[str, Any]]:
        """
        翻译后整体润色阶段：检查连贯性、术语一致性、自然度优化

        Args:
            segments: 已翻译的片段列表
            source_lang: 源语言
            target_lang: 目标语言

        Returns:
            润色后的片段列表
        """
        if not segments or len(segments) < 3:
            return segments

        logger.info(f"整体润色阶段：处理 {len(segments)} 个片段")

        # 将片段分成多个润色块（每个块约2000字符）
        TARGET_BLOCK_CHARS = 2000
        polish_blocks = []
        current_block = []
        current_chars = 0

        for seg in segments:
            seg_chars = len(seg["text"])
            if current_block and (current_chars + seg_chars > TARGET_BLOCK_CHARS):
                polish_blocks.append(current_block)
                current_block = []
                current_chars = 0
            current_block.append(seg)
            current_chars += seg_chars

        if current_block:
            polish_blocks.append(current_block)

        polished_results = []

        for block_idx, block in enumerate(polish_blocks):
            logger.info(f"润色块 {block_idx + 1}/{len(polish_blocks)} (约 {sum(len(s['text']) for s in block)} 字符)")

            # 构建润色提示词
            formatted_segs = []
            for idx, seg in enumerate(block):
                formatted_segs.append(f"<{idx + 1}> {seg['text']}")

            polish_prompt = f"""
            你是一位专业的字幕编审专家。请检查并润色以下翻译后的字幕。

            [源语言] {source_lang}
            [目标语言] {target_lang}

            [待润色字幕]
            {'\n'.join(formatted_segs)}

            [润色要求]
            1. **连贯性检查**：确保字幕之间逻辑连贯，对话自然流畅
            2. **术语一致性**：相同的术语、名称、短语在整个字幕中保持一致
            3. **自然度优化**：
               - 去掉生硬或过于直译的表达
               - 让对话听起来像真实的人在说话
               - 使用符合目标语言习惯的口语化表达
            4. **保持原意**：不要改变原文的核心意思
            5. **[非常重要] 只返回修改项**：
               - 只有当字幕确实需要修改时才返回
               - 如果某条字幕已经很好，不需要修改，就不要包含在结果中
               - 如果润色后和原文完全一样，绝对不要返回
            """

            try:
                response: PolishResponse = self._call_llm_structured(
                    [{"role": "user", "content": polish_prompt}], response_model=PolishResponse
                )
                polish_data = response.updates

                # 应用润色结果
                for idx_str, new_text in polish_data.items():
                    try:
                        idx = int(idx_str) - 1
                        if 0 <= idx < len(block):
                            old_text = block[idx]["text"]
                            if old_text != new_text:
                                block[idx]["text"] = new_text
                                logger.info(f"润色更新 <{idx + 1}>:\n  [前] {old_text}\n  [后] {new_text}")
                    except (ValueError, IndexError):
                        pass

            except Exception as e:
                logger.warning(f"润色块 {block_idx + 1} 失败: {e}")

            polished_results.extend(block)

        logger.info(f"整体润色完成")
        return polished_results
