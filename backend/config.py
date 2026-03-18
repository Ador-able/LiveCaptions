"""
统一配置管理模块

所有环境变量的加载和配置都在这里集中管理。
作为程序入口点，确保在任何其他模块导入之前加载环境变量。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 计算项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env 文件（只加载一次）
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=False)

# --- 数据库配置 ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'tasks.db'}")

# --- Redis 配置 ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TIMEZONE = os.getenv("CELERY_TIMEZONE", "Asia/Shanghai")

# --- LLM 配置 ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# --- 模型配置 ---
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_HOME = os.getenv("HF_HOME", str(BASE_DIR / "models" / "huggingface"))
HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE", "1")
TORCH_HOME = os.getenv("TORCH_HOME", str(BASE_DIR / "models" / "torch"))
WHISPER_MODEL_V2_PATH = os.getenv("WHISPER_MODEL_V2_PATH", str(BASE_DIR / "models" / "faster-whisper" / "large-v2"))
WHISPER_MODEL_V3_PATH = os.getenv("WHISPER_MODEL_V3_PATH", str(BASE_DIR / "models" / "faster-whisper" / "large-v3"))

# --- Demucs 配置 ---
DEMUCS_MODEL = os.getenv("DEMUCS_MODEL", "htdemucs_ft")
DEMUCS_DEVICE = os.getenv("DEMUCS_DEVICE", "cuda")
DEMUCS_SEGMENT = os.getenv("DEMUCS_SEGMENT", "14")

# --- 文件系统配置 ---
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads"))
RESULT_DIR = os.getenv("RESULT_DIR", str(BASE_DIR / "data" / "results"))

# --- 服务配置 ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
