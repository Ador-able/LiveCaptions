# 系统架构文档 (System Architecture)

本文档描述了 Video Subtitle Master 的技术架构和组件交互。

## 1. 后端 (Backend)

- **框架:** FastAPI (Python 3.10+)
- **任务队列:** Celery (使用 Redis 作为 Broker 和 Backend)
- **数据库:** SQLAlchemy (SQLite/PostgreSQL) + Alembic (迁移)
- **进程管理:** Supervisord (Docker 容器内管理 FastAPI, Celery, Redis)

## 2. AI 处理流水线 (AI Pipeline)

字幕生成的核心流程如下：

1.  **音频提取 (Audio Extraction):**
    - 使用 `ffmpeg` 将视频转换为 16kHz 单声道 WAV 格式。
2.  **人声分离 (Vocal Isolation):**
    - 使用 `demucs` (默认模型: `htdemucs`) 分离人声和背景音。
    - 目的: 提高后续 ASR 的准确率，减少背景噪音干扰。
3.  **语音转写 (ASR):**
    - 使用 `faster-whisper` (基于 CTranslate2 的 Whisper 实现)。
    - 默认模型: `large-v3`。
    - 特性: 内置 VAD (Voice Activity Detection) 过滤静音片段，Beam Search 优化解码。
4.  **说话人分离 (Diarization):**
    - 使用 `pyannote.audio` (版本 3.1+)。
    - 功能: 区分不同说话人，生成说话人标签。
5.  **文本对齐与分割 (Alignment & Segmentation):**
    - 使用 `spacy` (`zh_core_web_sm`, `en_core_web_sm`) 进行句法分析。
    - 结合 Whisper 的字级时间戳 (Word-level timestamps) 进行精确对齐。
6.  **翻译 (Translation):**
    - 使用 LLM (OpenAI 接口兼容)。
    - 采用 "直译 -> 反思 -> 意译" 三步法 (Agentic Workflow)。
    - 支持术语表提取和应用。

## 3. 前端 (Frontend)

- **框架:** React + Vite
- **UI 库:** Tailwind CSS
- **交互:** 通过 RESTful API 与后端通信，WebSocket (可选) 用于实时进度更新。

## 4. 部署 (Deployment)

- **容器化:** Docker (单容器架构)。
- **GPU 支持:** 必须支持 CUDA 12.4+ (推荐 NVIDIA RTX 3090/4090/5090)。
