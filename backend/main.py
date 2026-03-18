"""
FastAPI 主应用入口

配置加载由 config 模块统一管理，这里只需导入即可。
"""
import traceback
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .config import BASE_DIR
from .database import engine, SessionLocal
from .routers import tasks, download, ws, system
from . import models, crud
from .worker.tasks import process_video_task
from loguru import logger

# Create database tables
models.Base.metadata.create_all(bind=engine)

# 清理启动时可能卡住的任务
db = SessionLocal()
try:
    reset_ids = crud.cleanup_stuck_tasks(db)
    if reset_ids:
        logger.info(f"Re-triggering {len(reset_ids)} tasks...")
        for task_id in reset_ids:
            process_video_task.delay(task_id)
finally:
    db.close()

app = FastAPI(title="LiveCaptions API", description="Video Captioning and Translation System", version="1.0.0")

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常并返回详细错误信息"""
    error_detail = {
        "error": str(exc),
        "type": type(exc).__name__,
        "traceback": traceback.format_exc(),
        "path": str(request.url),
        "method": request.method
    }
    logger.error(f"全局异常捕获: {error_detail}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_detail
    )

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(download.router, prefix="/api/download", tags=["download"])
app.include_router(ws.router, prefix="/api", tags=["websocket"])
app.include_router(system.router, prefix="/api/system", tags=["system"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}

# 回退托管前端静态文件
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
else:
    logger.warning("Frontend dist directory not found. Static files will not be served.")
