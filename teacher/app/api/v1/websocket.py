"""
WebSocket 路由：仪表板实时推送
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.notification import notification_hub

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/overview")
async def ws_overview(websocket: WebSocket):
    """
    WebSocket /ws/overview
    仪表板连接后持续接收 push 事件的实时更新消息。
    消息格式（JSON）：
    {
      "event": "push",
      "student": "张三",
      "image": "cat.json",
      "uploaded": 5,
      "total": 8
    }
    """
    await websocket.accept()
    queue = notification_hub.subscribe()
    logger.info("WebSocket 客户端已连接：%s", websocket.client)

    try:
        while True:
            # 等待消息，超时后发送心跳 ping
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
            except asyncio.TimeoutError:
                # 发送心跳保持连接
                await websocket.send_text(json.dumps({"event": "ping"}))
    except WebSocketDisconnect:
        logger.info("WebSocket 客户端断开连接：%s", websocket.client)
    except Exception as exc:
        logger.warning("WebSocket 异常：%s", exc)
    finally:
        notification_hub.unsubscribe(queue)
