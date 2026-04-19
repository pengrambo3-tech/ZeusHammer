"""
ZeusHammer WebSocket Communication

WebSocket通信模块，支持:
1. 实时消息推送
2. 服务器推送事件 (SSE)
3. 长连接管理
4. 心跳保活
5. 自动重连
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class WebSocketState(Enum):
    """WebSocket状态"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


@dataclass
class WebSocketMessage:
    """WebSocket消息"""
    type: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    id: str = ""


class WebSocketClient:
    """
    WebSocket客户端

    支持:
    - 自动重连
    - 心跳保活
    - 消息队列
    - TLS/mTLS
    """

    def __init__(
        self,
        url: str,
        headers: Dict = None,
        protocols: List[str] = None,
        ping_interval: float = 30.0,
        reconnect_delay: float = 1.0,
        max_reconnect_attempts: int = 10,
    ):
        self.url = url
        self.headers = headers or {}
        self.protocols = protocols
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self._ws = None
        self._state = WebSocketState.DISCONNECTED
        self._reconnect_attempts = 0
        self._last_pong = 0

        # 消息处理
        self._handlers: Dict[str, Callable] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

        # 任务
        self._reader_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> WebSocketState:
        """获取连接状态"""
        return self._state

    async def connect(self) -> bool:
        """连接到WebSocket服务器"""
        try:
            self._state = WebSocketState.CONNECTING
            logger.info(f"Connecting to {self.url}")

            import websockets

            self._ws = await websockets.connect(
                self.url,
                extra_headers=self.headers,
                subprotocols=self.protocols,
            )

            self._state = WebSocketState.CONNECTED
            self._reconnect_attempts = 0
            self._last_pong = time.time()

            logger.info(f"Connected to {self.url}")

            # 启动读取任务
            self._running = True
            self._reader_task = asyncio.create_task(self._read_loop())

            # 启动心跳任务
            self._ping_task = asyncio.create_task(self._ping_loop())

            return True

        except Exception as e:
            logger.error(f"WebSocket connect failed: {e}")
            self._state = WebSocketState.DISCONNECTED
            return False

    async def disconnect(self):
        """断开连接"""
        self._running = False

        # 取消任务
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        # 关闭连接
        if self._ws:
            await self._ws.close()
            self._ws = None

        self._state = WebSocketState.DISCONNECTED
        logger.info("WebSocket disconnected")

    async def reconnect(self):
        """重新连接"""
        if self._reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnect attempts reached")
            self._state = WebSocketState.CLOSED
            return False

        self._state = WebSocketState.RECONNECTING
        self._reconnect_attempts += 1

        delay = self.reconnect_delay * (2 ** min(self._reconnect_attempts - 1, 5))
        logger.info(f"Reconnecting in {delay}s (attempt {self._reconnect_attempts})")

        await asyncio.sleep(delay)

        return await self.connect()

    async def send(self, message: Dict) -> bool:
        """发送消息"""
        if self._state != WebSocketState.CONNECTED:
            logger.warning("Cannot send: not connected")
            return False

        try:
            data = json.dumps(message)
            await self._ws.send(data)
            return True
        except Exception as e:
            logger.error(f"WebSocket send failed: {e}")
            return False

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        return await self.send({"type": "text", "data": text})

    async def send_binary(self, data: bytes) -> bool:
        """发送二进制消息"""
        if self._state != WebSocketState.CONNECTED:
            return False

        try:
            await self._ws.send(data)
            return True
        except Exception as e:
            logger.error(f"WebSocket send binary failed: {e}")
            return False

    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        self._handlers[event] = handler

    def off(self, event: str):
        """移除事件处理器"""
        if event in self._handlers:
            del self._handlers[event]

    async def _read_loop(self):
        """读取循环"""
        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                await self._handle_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket read error: {e}")
                if self._running:
                    await self.reconnect()
                break

    async def _handle_message(self, message: Any):
        """处理消息"""
        try:
            # 解析消息
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            msg_type = data.get("type", "message")

            # 调用处理器
            if msg_type in self._handlers:
                handler = self._handlers[msg_type]
                result = handler(data)

                if asyncio.iscoroutine(result):
                    await result

            # 添加到队列
            await self._message_queue.put(data)

        except Exception as e:
            logger.error(f"Message handle error: {e}")

    async def _ping_loop(self):
        """心跳循环"""
        while self._running and self._ws:
            try:
                await asyncio.sleep(self.ping_interval)

                if self._ws:
                    await self._ws.ping()
                    self._last_pong = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ping error: {e}")
                break

    async def receive(self) -> Optional[Dict]:
        """接收消息（从队列）"""
        try:
            return await asyncio.wait_for(
                self._message_queue.get(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            return None

    async def get_queue_message(self) -> Optional[Dict]:
        """获取队列消息（非阻塞）"""
        try:
            return self._message_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


class WebSocketServer:
    """
    WebSocket服务器

    支持:
    - 多个客户端管理
    - 广播
    - 消息路由
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self._server = None
        self._clients: Dict[str, WebSocketClient] = {}
        self._running = False

        # 处理器
        self._route_handlers: Dict[str, Callable] = {}

    async def start(self):
        """启动服务器"""
        import websockets

        self._running = True

        async with websockets.serve(
            self._handle_client,
            self.host,
            self.port,
        ):
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            await asyncio.Future()  # 永远运行

    async def stop(self):
        """停止服务器"""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("WebSocket server stopped")

    async def _handle_client(self, ws, path: str):
        """处理客户端连接"""
        client_id = str(id(ws))
        self._clients[client_id] = ws

        logger.info(f"Client connected: {client_id}")

        try:
            async for message in ws:
                await self._handle_message(client_id, ws, message)

        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            del self._clients[client_id]
            logger.info(f"Client disconnected: {client_id}")

    async def _handle_message(self, client_id: str, ws, message: Any):
        """处理客户端消息"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            msg_type = data.get("type", "message")

            # 路由处理
            if msg_type in self._route_handlers:
                handler = self._route_handlers[msg_type]
                result = handler(client_id, data)

                if asyncio.iscoroutine(result):
                    result = await result

                if result is not None:
                    await ws.send(json.dumps(result))

        except Exception as e:
            logger.error(f"Message handle error: {e}")

    def route(self, event: str, handler: Callable):
        """注册路由处理器"""
        self._route_handlers[event] = handler

    async def broadcast(self, message: Dict, exclude: List[str] = None):
        """广播消息"""
        exclude = exclude or []

        for client_id, ws in self._clients.items():
            if client_id not in exclude:
                try:
                    await ws.send(json.dumps(message))
                except Exception:
                    pass

    def get_client_count(self) -> int:
        """获取客户端数量"""
        return len(self._clients)


# SSE服务器 (用于HTTP推送)

class SSEServer:
    """
    Server-Sent Events服务器

    用于HTTP长连接推送
    """

    def __init__(self):
        self._clients: List[asyncio.Queue] = []

    async def add_client(self) -> asyncio.Queue:
        """添加客户端"""
        queue = asyncio.Queue()
        self._clients.append(queue)
        return queue

    def remove_client(self, queue: asyncio.Queue):
        """移除客户端"""
        if queue in self._clients:
            self._clients.remove(queue)

    async def broadcast(self, event: str, data: Any):
        """广播事件"""
        message = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        bytes_message = message.encode()

        for queue in self._clients[:]:
            try:
                await queue.put(bytes_message)
            except Exception:
                pass

    async def send_to(self, queue: asyncio.Queue, event: str, data: Any):
        """发送消息到指定客户端"""
        message = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        await queue.put(message.encode())

    def get_client_count(self) -> int:
        """获取客户端数量"""
        return len(self._clients)
