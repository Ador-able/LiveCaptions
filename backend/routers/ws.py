from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from loguru import logger
import json
import asyncio
from ..redis_client import async_redis

router = APIRouter()

# 简单的 WebSocket 连接管理器
class ConnectionManager:
    def __init__(self):
        # 存储所有活跃的全局连接
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Global WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Global WebSocket disconnected. Remaining connections: {len(self.active_connections)}")

manager = ConnectionManager()

@router.websocket("/ws/global")
async def global_websocket_endpoint(websocket: WebSocket):
    """
    全局 WebSocket 端点，用于实时推送系统内所有任务的进度和日志。
    """
    await manager.connect(websocket)
    
    ps = async_redis.pubsub()
    await ps.subscribe("task_updates")
    
    async def listen_redis():
        try:
            while True:
                message = await ps.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    try:
                        # 收到消息立即转发
                        await websocket.send_text(message["data"])
                    except Exception as e:
                        logger.error(f"WS error sending message: {e}")
                        break
                await asyncio.sleep(0.01) # 极其短暂的休眠以防过度占用 CPU
        except Exception as e:
            logger.error(f"Redis listener error: {e}")

    async def listen_client():
        try:
            while True:
                # 持续监听客户端，主要用于检测断开或心跳消息
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected normally by client")
        except Exception as e:
            logger.error(f"WS client listener exception: {e}")

    listen_redis_task = asyncio.create_task(listen_redis())
    listen_client_task = asyncio.create_task(listen_client())

    try:
        # 等待其中一个任务完成（如客户端断开或 Redis 出错）
        done, pending = await asyncio.wait(
            [listen_redis_task, listen_client_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        # 取消另一个正在运行的任务
        for task in pending:
            task.cancel()
    except Exception as e:
        logger.debug(f"WS tasks wait exited: {e}")
    finally:
        await ps.unsubscribe("task_updates")
        manager.disconnect(websocket)
