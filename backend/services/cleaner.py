import os
import time
from loguru import logger

from ..config import UPLOAD_DIR, RESULT_DIR


class CleanerService:
    def __init__(self, upload_dir: str = None, result_dir: str = None):
        self.upload_dir = upload_dir or UPLOAD_DIR
        self.result_dir = result_dir or RESULT_DIR

    def clean_orphaned_files(self, max_age_hours: int = 24):
        """清理超过 max_age_hours 的临时文件和结果文件"""
        logger.info(f"开始清理文件 (最大保留时间: {max_age_hours} 小时)...")
        count = 0
        total_size = 0

        cutoff_time = time.time() - (max_age_hours * 3600)

        for directory in [self.upload_dir, self.result_dir]:
            if not os.path.exists(directory):
                continue

            for root, dirs, files in os.walk(directory):
                for name in files:
                    file_path = os.path.join(root, name)
                    try:
                        stat = os.stat(file_path)
                        if stat.st_mtime < cutoff_time:
                            size = stat.st_size
                            os.remove(file_path)
                            count += 1
                            total_size += size
                            logger.debug(f"已删除过期文件: {file_path}")
                    except Exception as e:
                        logger.error(f"删除文件失败 {file_path}: {e}")

        logger.info(f"清理完成: 删除 {count} 个文件, 释放 {total_size / 1024 / 1024:.2f} MB。")
        return {"deleted_count": count, "freed_mb": round(total_size / 1024 / 1024, 2)}


_cleaner = None


def get_cleaner_service():
    global _cleaner
    if _cleaner is None:
        _cleaner = CleanerService()
    return _cleaner
