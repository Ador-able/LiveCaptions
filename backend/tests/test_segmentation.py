import sys
import os
import unittest
from loguru import logger

# Add backend to path to allow importing services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.alignment import get_alignment_service

class TestAlignmentService(unittest.TestCase):
    def setUp(self):
        self.service = get_alignment_service()

    def test_short_sentence(self):
        segments = [{"start": 0, "end": 2, "text": "Hello world"}]
        result = self.service.check_netflix_compliance(segments, max_cpl=20)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], "Hello world")

    def test_long_english_sentence(self):
        text = "This is a very long sentence that should be split into multiple parts because it exceeds the maximum characters per line limit set by Netflix standards."
        # Length is ~148 chars. Max CPL 42.
        segments = [{"start": 0, "end": 10, "text": text}]
        result = self.service.check_netflix_compliance(segments, max_cpl=42)

        logger.info(f"Original text length: {len(text)}")
        logger.info(f"Result segments: {len(result)}")
        for i, seg in enumerate(result):
            logger.info(f"Seg {i}: {seg['text']} (len={len(seg['text'])})")
            self.assertLessEqual(len(seg['text']), 42)

        # Check continuity
        self.assertAlmostEqual(result[0]['start'], 0)
        self.assertAlmostEqual(result[-1]['end'], 10)

    def test_long_chinese_sentence(self):
        text = "这是一个非常长的中文句子，应该被分割成多个部分，因为它超过了Netflix标准设定的每行最大字符数限制。我们需要确保它能够正确地被切分。"
        # Length ~70 chars. Max CPL 20.
        segments = [{"start": 0, "end": 10, "text": text}]
        result = self.service.check_netflix_compliance(segments, max_cpl=20)

        logger.info(f"Original text length: {len(text)}")
        logger.info(f"Result segments: {len(result)}")
        for i, seg in enumerate(result):
            logger.info(f"Seg {i}: {seg['text']} (len={len(seg['text'])})")
            self.assertLessEqual(len(seg['text']), 20)

    def test_mixed_punctuation(self):
        text = "First part. Second part is longer and needs check; Third part."
        segments = [{"start": 0, "end": 10, "text": text}]
        result = self.service.check_netflix_compliance(segments, max_cpl=30)

        for seg in result:
             self.assertLessEqual(len(seg['text']), 30)

if __name__ == '__main__':
    unittest.main()
