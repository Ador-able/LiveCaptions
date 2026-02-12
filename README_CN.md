# LiveCaptions - 影视级字幕生成服务

LiveCaptions 是一个强大的、AI 驱动的视频字幕生成与翻译服务。它利用深度学习模型（Whisper, Demucs, Pyannote）和 LLM（GPT-4, Claude 等）来实现高质量的字幕提取、人声分离、对齐和多步意译。

## 核心功能

*   **ASR 语音识别**: 使用 `faster-whisper` (Large-v3 模型) 进行高精度转写。
*   **高级音频处理**:
    *   **人声分离**: 集成 `Demucs` 分离背景音乐和人声，解决嘈杂背景下的识别问题。
    *   **说话人分离 (Diarization)**: 区分不同说话人。
    *   **VAD 静音检测**: 严格过滤静音，避免幻觉。
*   **LLM 翻译引擎**:
    *   **三步翻译法**: 直译 -> 反思/校对 -> 意译/润色。
    *   **术语提取**: 自动提取并统一专有名词翻译。
    *   **上下文感知**: 基于全片上下文进行翻译。
*   **Netflix 标准合规**:
    *   严格限制每行字符数 (CPL) 和阅读速度 (CPS)。
    *   强制单行字幕（可配置），智能分割长句。
*   **任务管理**:
    *   支持暂停、恢复和崩溃后断点续传。
    *   实时进度监控和详细日志。
*   **部署**:
    *   单容器 Docker 部署 (后端 + 前端 + Redis + Worker)。
    *   GPU 加速 (支持 NVIDIA 5090 等显卡)。

## 环境要求

*   **NVIDIA 显卡**: 推荐 24GB+ 显存 (如 RTX 3090/4090/5090) 以获得最佳性能。
*   **Docker**: 已安装 Docker 和 NVIDIA Container Toolkit。
*   **API Key**: OpenAI 格式的 API 密钥 (用于翻译功能)。

## 快速开始

### 1. 克隆代码库

```bash
git clone https://github.com/Ador-able/LiveCaptions.git
cd LiveCaptions
```

### 2. 配置环境

在项目根目录创建 `.env` 文件（可选），或直接在 `docker-compose.yml` 中配置环境变量。

```env
OPENAI_API_KEY=sk-your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
```

### 3. 启动服务

```bash
docker-compose up -d
```

服务启动后访问：
*   **Web 界面**: `http://localhost:8000`
*   **API 文档**: `http://localhost:8000/docs`

数据持久化：
*   所有数据库和上传文件存储在 `./data` 目录中。
*   Redis 数据存储在 `./data/dump.rdb`。

## 开发指南

### 后端 (Backend)

后端使用 **FastAPI** 构建，利用 **Celery** 处理后台耗时任务。

*   `backend/main.py`: 应用入口。
*   `backend/worker/`: Celery 任务定义。
*   `backend/services/`: 核心逻辑 (ASR, LLM, 音频处理)。

### 前端 (Frontend)

前端使用 **React** (Vite + Tailwind CSS) 构建。

*   `frontend/src/`: 源代码。
*   `frontend/dist/`: 构建产物 (由 Dockerfile 自动生成)。

## 许可证

[MIT](LICENSE)
