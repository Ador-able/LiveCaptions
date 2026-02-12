import os
from loguru import logger
import openai
from pydantic import BaseModel
from typing import List, Optional, Dict

class LLMService:
    """
    LLM 翻译服务

    负责：
    1. 调用 OpenAI API 或兼容 API。
    2. 执行三步翻译流程 (直译 -> 反思 -> 意译)。
    3. 提取术语表。
    """
    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-4o"):
        """
        初始化 LLM 客户端。

        参数:
        - api_key: API 密钥 (默认从环境变量获取)。
        - base_url: API 基础地址 (默认 https://api.openai.com/v1)。
        - model: 使用的模型名称 (默认 gpt-4o)。
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model

        if not self.api_key:
            logger.warning("未配置 OPENAI_API_KEY，LLM 功能将无法工作。")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def extract_terminology(self, text_chunk: str, source_lang: str, target_lang: str) -> str:
        """
        术语提取功能。
        从源文本片段中提取关键术语，生成 JSON 格式的术语表。

        参数:
        - text_chunk: 待提取的文本片段 (最好是全文，或者长片段)。
        - source_lang: 源语言代码。
        - target_lang: 目标语言代码。

        返回:
        - JSON 字符串，包含术语和对应翻译。
        """
        if not self.client:
            logger.error("LLM 未初始化，无法提取术语。")
            return "[]"

        logger.info(f"开始提取术语 (源: {source_lang} -> 目标: {target_lang})")

        system_prompt = f"""
        你是一名专业的视频字幕翻译专家。
        你的任务是从提供的 {source_lang} 字幕文本中提取重要的专有名词（人名、地名、机构名、特定称谓）和专业术语。
        并为这些术语提供准确、统一的 {target_lang} 翻译。

        输出格式必须是严格的 JSON 列表，每一项包含 "term" (原文) 和 "translation" (译文)。
        例如:
        [
            {{"term": "OpenAI", "translation": "OpenAI"}},
            {{"term": "Transformer model", "translation": "Transformer 模型"}}
        ]
        如果文本中没有专有名词，请直接输出空列表 []。
        """

        try:
            # 限制输入长度，避免超出 token 上限
            input_text = text_chunk[:10000] if len(text_chunk) > 10000 else text_chunk

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"文本内容:\n{input_text}"}
                ],
                response_format={"type": "json_object"}, # 强制 JSON 输出
                temperature=0.1 # 低温度确保确定性
            )
            content = response.choices[0].message.content
            logger.debug(f"提取到的术语表: {content}")
            return content
        except Exception as e:
            logger.error(f"术语提取失败: {e}")
            return "[]"

    def three_step_translation(self, source_text: str, source_lang: str, target_lang: str, terminology: str = "[]") -> str:
        """
        执行标准的三步翻译流程。
        这一过程确保翻译既准确又符合语境，且读起来自然流畅。

        步骤:
        1. 直译 (Literal): 准确保留原意，不要遗漏。
        2. 反思 (Reflection): 自我检查直译中的错误、生硬表达或不一致之处。
        3. 意译 (Polishing): 根据反思结果，重写最终译文，使其符合 Netflix 影视字幕标准。

        参数:
        - source_text: 待翻译的源文本片段。
        - source_lang: 源语言。
        - target_lang: 目标语言。
        - terminology: 术语表 (JSON 字符串)，用于指导翻译。

        返回:
        - 最终润色后的译文。
        """
        if not self.client:
            logger.error("LLM 未初始化，无法进行翻译。")
            return source_text # 原样返回

        logger.info(f"开始翻译片段 ({len(source_text)} 字符)...")

        # 步骤 1: 直译
        step1_prompt = f"""
        将以下 {source_lang} 字幕文本逐句直译为 {target_lang}。
        要求：
        1. 保持原始句式结构，不要遗漏任何信息。
        2. 参考以下术语表进行翻译：{terminology}

        待翻译文本:
        {source_text}
        """
        literal_trans = self._call_llm(step1_prompt, temp=0.3)
        if literal_trans == "Error": return source_text
        logger.debug("直译完成。")

        # 步骤 2: 反思
        step2_prompt = f"""
        请校对以下 {target_lang} 直译文本。
        指出其中的错译、不通顺、不符合 {target_lang} 表达习惯的地方。
        特别注意术语的一致性。

        原文:
        {source_text}
        直译:
        {literal_trans}

        请列出修改建议。
        """
        reflection = self._call_llm(step2_prompt, temp=0.5)
        if reflection == "Error": return literal_trans # 如果反思失败，返回直译
        logger.debug("反思完成。")

        # 步骤 3: 意译 (润色)
        step3_prompt = f"""
        根据以下信息，重写最终的 {target_lang} 字幕。
        要求：
        1. 翻译信达雅，符合影视级字幕标准。
        2. 语言通顺，连贯性强，语气自然。
        3. 符合 Netflix 字幕规范（简洁有力，避免过长句子）。

        原文: {source_text}
        直译: {literal_trans}
        校对意见: {reflection}

        只输出最终的翻译结果，不要包含任何解释或前缀。确保行数与原文对应。
        """
        final_trans = self._call_llm(step3_prompt, temp=0.3)
        if final_trans == "Error": return literal_trans
        logger.info("意译润色完成。")

        return final_trans

    def _call_llm(self, prompt: str, temp: float = 0.3) -> str:
        """
        调用 LLM 的通用辅助方法。
        处理异常和重试逻辑 (简单版)。
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temp
            )
            content = response.choices[0].message.content.strip()
            return content
        except Exception as e:
            logger.error(f"LLM API 调用失败: {e}")
            return "Error"
