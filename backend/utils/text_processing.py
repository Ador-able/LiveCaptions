import re
import spacy
from typing import List, Dict, Any

class TextProcessor:
    """
    文本处理工具类 (支持中文和英文)
    用于处理字幕文本的分割、标点修复和格式化。
    """
    def __init__(self, lang: str = "zh"):
        self.lang = lang
        self.nlp = None
        try:
            if lang == "zh":
                self.nlp = spacy.load("zh_core_web_sm")
            else:
                self.nlp = spacy.load("en_core_web_sm")
        except:
            pass

    def split_sentences(self, text: str) -> List[str]:
        """
        基于 NLP 的分句逻辑。
        """
        if self.nlp:
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents]
        else:
            # 回退到简单的标点分割
            return re.split(r'[.!?。！？]+', text)
