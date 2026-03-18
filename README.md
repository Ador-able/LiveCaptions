# LiveCaptions

AI 驱动的视频字幕生成与翻译服务，支持高精度语音识别、智能翻译和 Netflix 标准字幕输出。

## 功能特性

- **高精度 ASR**: 使用 Faster Whisper 进行语音识别
- **人声分离**: 集成 Demucs 分离背景音乐和人声
- **智能翻译**: LLM 三步翻译法（直译 → 反思 → 意译）
- **术语提取**: 自动提取并统一专有名词翻译
- **视频背景**: 支持提供视频简介作为翻译上下文
- **Netflix 标准**: 严格的字幕合规性检查
- **断点续传**: 支持任务暂停和恢复
- **实时进度**: WebSocket 实时推送任务状态

## 项目结构

```
LiveCaptions/
├── backend/              # 后端服务 (FastAPI + Celery)
│   ├── routers/         # API 路由
│   ├── services/        # 核心业务逻辑
│   ├── worker/          # Celery 任务
│   ├── utils/           # 工具函数
│   └── tests/           # 测试代码
├── frontend/            # 前端应用 (React + Vite)
│   └── src/
│       ├── components/  # UI 组件
│       ├── pages/       # 页面组件
│       ├── contexts/    # React Context
│       └── lib/         # 工具库
└── data/                # 数据目录 (gitignore)
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- NVIDIA GPU (推荐 24GB+ 显存)
- Redis (用于 Celery 队列)

### 后端启动

```bash
cd backend
pip install -r requirements.txt

# 启动 API 服务
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 启动 Celery Worker (另一个终端)
celery -A backend.worker.celery_app worker --loglevel=info -P solo --concurrency=1
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

### 环境变量

在项目根目录创建 `.env` 文件：

```env
OPENAI_API_KEY=sk-your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
RESULT_DIR=./data/results
```

## 开发规范

### 后端 (Python)

- 使用 **Black** 格式化代码
- 使用 **Ruff** 进行代码检查
- 使用 **isort** 排序导入

```bash
cd backend
pip install black ruff isort

# 格式化代码
black .
isort .
ruff check . --fix
```

### 前端 (TypeScript)

- 使用 **Prettier** 格式化代码
- 使用 **ESLint** 进行代码检查

```bash
cd frontend
npm run format
npm run lint
```

## API 文档

启动后端服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 许可证

MIT
