# Backend

LiveCaptions 后端服务，使用 FastAPI + Celery 构建。

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt

# 代码格式化
pip install black ruff isort
black .
isort .
ruff check . --fix

# 启动服务
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 启动 Celery Worker
celery -A backend.worker.celery_app worker --loglevel=info -P solo --concurrency=1
```

## 目录结构

- `routers/` - API 路由定义
- `services/` - 核心业务逻辑（ASR, LLM, 音频处理）
- `worker/` - Celery 后台任务
- `utils/` - 工具函数
- `tests/` - 测试代码
