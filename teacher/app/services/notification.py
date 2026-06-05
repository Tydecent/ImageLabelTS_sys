"""
通知服务：内存 pub/sub，用于 WebSocket 推送
当学生成功 push 后，向所有已连接的仪表板广播更新消息
"""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class NotificationHub:
    """
    简单的内存 pub/sub 中心。
    仪表板 WebSocket 连接时订阅，push 成功后发布消息。
    """

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """注册一个新订阅者，返回其专属队列"""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.append(q)
        logger.debug("新 WebSocket 客户端订阅，当前订阅者数: %d", len(self._queues))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """移除订阅者"""
        try:
            self._queues.remove(q)
        except ValueError:
            pass
        logger.debug("WebSocket 客户端取消订阅，当前订阅者数: %d", len(self._queues))

    async def publish(self, message: dict[str, Any]) -> None:
        """向所有订阅者广播消息，队列满时丢弃（不阻塞）"""
        for q in list(self._queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("订阅者队列已满，丢弃消息")


# 全局单例，供路由层使用
notification_hub = NotificationHub()
