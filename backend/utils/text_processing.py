import re
from typing import List, Optional, Any

class TextProcessor:
    """
    文本处理工具类 (支持中文和英文)
    用于处理字幕文本的分割、标点修复和格式化。
    """
    def __init__(self, lang: str = "zh", llm_service: Any = None):
        self.lang = lang
        self.llm_service = llm_service

    def split_sentences(self, text: str) -> List[str]:
        """
        基于 LLM 或 Regex 的分句逻辑。
        """
        if self.llm_service:
            return self.llm_service.split_text_into_sentences(text, self.lang)
        else:
            # 回退到简单的标点分割
            return re.split(r'[.!?。！？]+', text)
