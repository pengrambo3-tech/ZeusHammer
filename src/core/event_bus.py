"""
ZeusHammer 事件总线

原创设计，统一事件系统。

设计特点:
- 异步事件处理
- 通配符订阅
- 事件优先级
- 错误隔离
- 历史记录
"""

import asyncio
import logging
import time
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import fnmatch

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """事件"""
    type: str  # 事件类型，支持通配符: "tool.*"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    priority: int = 0


class EventBus:
    """
    事件总线

    原创设计，所有子系统通过事件总线通信。

    用法:
        event_bus = EventBus()

        # 订阅
        await event_bus.subscribe("tool.*", handler)
        await event_bus.on("tool.completed", handler)

        # 发布
        await event_bus.publish(Event(type="tool.completed", data={...}))

        # 通配符
        await event_bus.publish(Event(type="tool.started", ...))  # 匹配 "tool.*"
        await event_bus.publish(Event(type="memory.recalled", ...))  # 不匹配
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._history: List[Event] = []
        self._max_history = 1000
        self._lock = asyncio.Lock()

    async def subscribe(self, pattern: str, handler: Callable):
        """
        订阅事件 (通配符支持)

        Args:
            pattern: 事件类型模式，支持 * 和 ?
            handler: 异步处理函数
        """
        async with self._lock:
            self._subscribers[pattern].append(handler)
        logger.debug(f"订阅事件: {pattern}")

    def on(self, event_type: str):
        """装饰器订阅"""
        def decorator(handler: Callable):
            asyncio.create_task(self.subscribe(event_type, handler))
            return handler
        return decorator

    async def unsubscribe(self, pattern: str, handler: Callable = None):
        """取消订阅"""
        async with self._lock:
            if handler:
                if pattern in self._subscribers:
                    self._subscribers[pattern] = [
                        h for h in self._subscribers[pattern] if h != handler
                    ]
            else:
                self._subscribers.pop(pattern, None)

    async def publish(self, event: Event):
        """
        发布事件

        所有匹配的订阅者都会被异步调用。
        单个订阅者失败不会影响其他订阅者。
        """
        # 记录历史
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        # 找出匹配的订阅者
        matched_handlers = []
        async with self._lock:
            for pattern, handlers in self._subscribers.items():
                if fnmatch.fnmatch(event.type, pattern):
                    matched_handlers.extend(handlers)

        # 异步调用所有处理者
        if matched_handlers:
            logger.debug(f"发布事件: {event.type} -> {len(matched_handlers)} 处理器")

        for handler in matched_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(self._safe_handle(handler, event))
                else:
                    asyncio.create_task(self._safe_handle(handler, event))
            except Exception as e:
                logger.error(f"事件处理器启动失败: {e}")

    async def _safe_handle(self, handler: Callable, event: Event):
        """安全执行处理器"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"事件处理失败 ({event.type}): {e}")

    async def wait_for(self, event_type: str, timeout: float = 30) -> Optional[Event]:
        """
        等待特定事件

        Args:
            event_type: 事件类型
            timeout: 超时时间(秒)

        Returns:
            第一个匹配的事件，或None
        """
        future = asyncio.get_event_loop().create_future()

        async def handler(event: Event):
            if event.type == event_type:
                future.set_result(event)

        await self.subscribe(event_type, handler)

        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            await self.unsubscribe(event_type)

    def get_history(self, event_type: str = None, limit: int = 100) -> List[Event]:
        """获取历史事件"""
        history = self._history
        if event_type:
            history = [e for e in history if fnmatch.fnmatch(e.type, event_type)]
        return history[-limit:]

    def clear_history(self):
        """清空历史"""
        self._history.clear()

    @property
    def subscriber_count(self) -> int:
        """订阅者数量"""
        return sum(len(h) for h in self._subscribers.values())

    def list_patterns(self) -> List[str]:
        """列出所有订阅模式"""
        return list(self._subscribers.keys())