"""
ZeusHammer WebSocket网关 - 完整实现

真正实现WebSocket连接管理。
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets not installed. Run: pip install websockets")


class MessageType(Enum):
    """消息类型"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


@dataclass
class WSMessage:
    """WebSocket消息"""
    type: MessageType
    id: str
    action: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "type": self.type.value,
            "id": self.id,
            "action": self.action,
            "data": self.data,
            "timestamp": self.timestamp,
            "session_id": self.session_id
        })

    @classmethod
    def from_json(cls, text: str) -> "WSMessage":
        data = json.loads(text)
        return cls(
            type=MessageType(data.get("type", "event")),
            id=data.get("id", ""),
            action=data.get("action", ""),
            data=data.get("data"),
            timestamp=data.get("timestamp", time.time()),
            session_id=data.get("session_id", "")
        )


class WebSocketGateway:
    """
    WebSocket网关客户端 - 完整实现

    真正的WebSocket连接管理。
    """

    def __init__(
        self,
        url: str = "",
        token: str = "",
        event_bus=None,
        headers: Dict[str, str] = None,
    ):
        self.url = url
        self.token = token
        self.event_bus = event_bus
        self.headers = headers or {}

        # 连接
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._reconnecting = False

        # 会话
        self._session_id = str(uuid.uuid4())
        self._user_id = None

        # 消息
        self._pending: Dict[str, asyncio.Future] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._handlers: Dict[str, Callable] = {}

        # 配置
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._ping_interval = 30.0
        self._ping_timeout = 10.0
        self._max_retries = 10

        # 任务
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

        # 统计
        self._stats = {
            "sent": 0,
            "received": 0,
            "errors": 0,
            "reconnects": 0
        }

    async def connect(self) -> bool:
        """连接到网关"""
        if not self.url:
            logger.info("网关未配置，跳过连接")
            return False

        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets库不可用")
            return False

        logger.info(f"连接到网关: {self.url}")

        try:
            # 构建请求头
            headers = {**self.headers}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            # 连接
            self._ws = await websockets.connect(
                self.url,
                extra_headers=headers,
            )

            self._connected = True
            self._session_id = str(uuid.uuid4())

            # 启动接收循环
            self._receive_task = asyncio.create_task(self._receive_loop())

            # 启动心跳
            self._ping_task = asyncio.create_task(self._ping_loop())

            logger.info(f"网关连接成功 (session: {self._session_id})")
            return True

        except Exception as e:
            logger.error(f"网关连接失败: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """断开连接"""
        logger.info("断开网关连接")
        self._connected = False

        # 取消任务
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
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
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        # 取消待处理请求
        for future in self._pending.values():
            if not future.done():
                future.set_result(None)

        self._pending.clear()

    async def _receive_loop(self):
        """接收消息循环"""
        while self._connected and self._ws:
            try:
                async for text in self._ws:
                    if not self._connected:
                        break

                    await self._handle_message(text)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"连接关闭: {e}")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"接收错误: {e}")
                self._stats["errors"] += 1

        # 重连
        if self._connected and not self._reconnecting:
            await self._reconnect()

    async def _ping_loop(self):
        """心跳循环"""
        while self._connected and self._ws:
            try:
                await asyncio.sleep(self._ping_interval)

                if self._connected and self._ws:
                    await self._ws.ping()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"心跳错误: {e}")

    async def _reconnect(self):
        """重连"""
        if self._stats["reconnects"] >= self._max_retries:
            logger.error("最大重连次数达到，放弃重连")
            self._connected = False
            return

        self._reconnecting = True
        delay = self._reconnect_delay

        logger.info(f"尝试重连 ({delay}s后)...")

        while self._connected and self._stats["reconnects"] < self._max_retries:
            await asyncio.sleep(delay)

            try:
                if await self.connect():
                    self._stats["reconnects"] += 1
                    self._reconnecting = False
                    logger.info("重连成功")
                    return

            except Exception:
                delay = min(delay * 2, self._max_reconnect_delay)

        self._reconnecting = False
        logger.error("重连失败")

    async def send(
        self,
        action: str,
        data: Any = None,
        wait_response: bool = True,
        timeout: float = 30
    ) -> Any:
        """发送消息"""
        if not self._connected or not self._ws:
            raise RuntimeError("未连接到网关")

        message = WSMessage(
            type=MessageType.REQUEST,
            id=str(uuid.uuid4()),
            action=action,
            data=data,
            session_id=self._session_id
        )

        try:
            await self._ws.send(message.to_json())
            self._stats["sent"] += 1

        except Exception as e:
            logger.error(f"发送失败: {e}")
            self._stats["errors"] += 1
            raise

        # 等待响应
        if wait_response:
            future = asyncio.get_event_loop().create_future()
            self._pending[message.id] = future

            try:
                result = await asyncio.wait_for(future, timeout)
                return result
            except asyncio.TimeoutError:
                del self._pending[message.id]
                raise TimeoutError(f"请求超时: {action}")

        return None

    async def send_text(self, text: str):
        """发送原始文本"""
        if not self._connected or not self._ws:
            raise RuntimeError("未连接到网关")

        await self._ws.send(text)
        self._stats["sent"] += 1

    async def send_binary(self, data: bytes):
        """发送二进制数据"""
        if not self._connected or not self._ws:
            raise RuntimeError("未连接到网关")

        await self._ws.send(data)
        self._stats["sent"] += 1

    async def _handle_message(self, text: str):
        """处理接收到的消息"""
        try:
            message = WSMessage.from_json(text)
            self._stats["received"] += 1

            logger.debug(f"收到: {message.action} ({message.type.value})")

            if message.type == MessageType.RESPONSE:
                if message.id in self._pending:
                    future = self._pending[message.id]
                    if not future.done():
                        future.set_result(message.data)

            elif message.type == MessageType.EVENT:
                await self._handle_event(message)

            elif message.type == MessageType.PING:
                pong = WSMessage(
                    type=MessageType.PONG,
                    id=message.id,
                    action="pong"
                )
                await self._ws.send(pong.to_json())

            elif message.type == MessageType.ERROR:
                logger.error(f"网关错误: {message.data}")

        except Exception as e:
            logger.error(f"消息处理失败: {e}")
            self._stats["errors"] += 1

    async def _handle_event(self, message: WSMessage):
        """处理事件"""
        action = message.action

        if action in self._handlers:
            handler = self._handlers[action]
            result = handler(message.data)
            if asyncio.iscoroutine(result):
                await result

        if self.event_bus:
            await self.event_bus.publish(type=f"gateway.{action}", data=message.data)

    def on(self, action: str, handler: Callable):
        """注册事件处理器"""
        self._handlers[action] = handler
        logger.debug(f"注册网关事件处理器: {action}")

    def off(self, action: str):
        """移除事件处理器"""
        if action in self._handlers:
            del self._handlers[action]

    async def create_session(self, user_id: str = None) -> str:
        """创建会话"""
        result = await self.send("session.create", {"user_id": user_id})
        self._session_id = result.get("session_id", self._session_id)
        self._user_id = user_id
        return self._session_id

    async def end_session(self):
        """结束会话"""
        await self.send("session.end", {"session_id": self._session_id})
        self._session_id = str(uuid.uuid4())

    async def list_agents(self) -> List[Dict]:
        """列出可用代理"""
        result = await self.send("agent.list")
        return result.get("agents", [])

    async def create_agent(self, name: str, config: Dict = None) -> str:
        """创建代理"""
        result = await self.send("agent.create", {
            "name": name,
            "config": config or {}
        })
        return result.get("agent_id", "")

    async def send_message(self, recipient: str, message: str):
        """发送消息"""
        return await self.send("message.send", {
            "recipient": recipient,
            "message": message
        })

    async def broadcast(self, message: str):
        """广播消息"""
        return await self.send("message.broadcast", {"message": message})

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def session_id(self) -> str:
        return self._session_id

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "connected": self._connected,
            "session_id": self._session_id,
            "pending_requests": len(self._pending)
        }


class WebSocketServer:
    """
    WebSocket服务器

    用于接收客户端连接。
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8766):
        self.host = host
        self.port = port
        self._server = None
        self._clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    async def start(self):
        """启动服务器"""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets库不可用")

        self._running = True

        async with websockets.serve(
            self._handle_client,
            self.host,
            self.port
        ):
            logger.info(f"WebSocket服务器启动: {self.host}:{self.port}")
            await asyncio.Future()  # 永远运行

    async def stop(self):
        """停止服务器"""
        self._running = False
        for client in list(self._clients.values()):
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()

    async def _handle_client(self, ws: websockets.WebSocketServerProtocol, path: str):
        """处理客户端连接"""
        client_id = str(id(ws))
        self._clients[client_id] = ws

        logger.info(f"客户端连接: {client_id}")

        try:
            async for text in ws:
                if not self._running:
                    break

                message = WSMessage.from_json(text)

                # 处理消息
                if message.action in self._handlers:
                    handler = self._handlers[message.action]
                    result = handler(message.data, client_id)

                    if asyncio.iscoroutine(result):
                        result = await result

                    # 发送响应
                    if result is not None:
                        response = WSMessage(
                            type=MessageType.RESPONSE,
                            id=message.id,
                            action=message.action,
                            data=result
                        )
                        await ws.send(response.to_json())

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"客户端处理错误: {e}")
        finally:
            del self._clients[client_id]
            logger.info(f"客户端断开: {client_id}")

    def route(self, action: str, handler: Callable):
        """注册路由处理器"""
        self._handlers[action] = handler

    async def broadcast(self, message: WSMessage):
        """广播消息"""
        for client_id, ws in self._clients.items():
            try:
                await ws.send(message.to_json())
            except Exception:
                pass

    def get_client_count(self) -> int:
        """获取客户端数量"""
        return len(self._clients)
