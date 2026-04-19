"""
ZeusHammer 核心引擎

原创设计，统一管理所有子系统。

架构设计:
                    ┌─────────────┐
                    │   用户输入   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  事件总线   │ ← 统一事件系统
                    └──┬─────┬───┘
                       │     │
         ┌─────────────┼─────┼─────────────┐
         │             │     │             │
    ┌────▼────┐  ┌────▼─┐ ┌▼────────┐ ┌──▼────┐
    │ 记忆系统 │  │ 管道  │ │ 工具系统 │ │ 技能  │
    └────┬────┘  └──┬───┘ └────┬────┘ └──┬────┘
         │           │          │          │
         └───────────┴──────────┴──────────┘
                           │
                    ┌──────▼──────┐
                    │   LLM 调用   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │   响应输出   │
                    └─────────────┘
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from .config import Config
from .event_bus import EventBus, Event
from .pipeline import Pipeline
from ..memory.unified import UnifiedMemory
from ..tools.executor import ToolExecutor
from ..mcp.protocol import MCPProtocol
from ..skills.engine import SkillEngine
from ..browser.orchestrator import BrowserOrchestrator
from ..gateway.websocket import WebSocketGateway

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """智能体状态"""
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    RESPONDING = "responding"
    ERROR = "error"


@dataclass
class TurnContext:
    """对话轮次上下文"""
    turn_id: str
    user_input: str
    timestamp: float = field(default_factory=time.time)
    state: AgentState = AgentState.IDLE
    tools_used: List[str] = field(default_factory=list)
    memory_used: List[str] = field(default_factory=list)
    skills_activated: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ZeusHammerCore:
    """
    ZeusHammer 核心引擎

    原创设计，统一协调所有子系统。

    设计原则:
    1. 事件驱动: 所有子系统通过事件总线通信
    2. 管道处理: 用户输入经过Pipeline处理
    3. 记忆优先: 每次处理前先检索记忆
    4. 工具编排: 统一管理工具执行
    5. 可观测性: 全链路追踪
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_default_locations()
        self.name = self.config.name
        self.version = self.config.version

        # 状态
        self._state = AgentState.IDLE
        self._running = False
        self._turn_counter = 0

        # 核心组件
        self._event_bus = EventBus()
        self._pipeline = Pipeline(self)
        self._memory: Optional[UnifiedMemory] = None
        self._tools: Optional[ToolExecutor] = None
        self._mcp: Optional[MCPProtocol] = None
        self._skills: Optional[SkillEngine] = None
        self._browser: Optional[BrowserOrchestrator] = None
        self._gateway: Optional[WebSocketGateway] = None

        # 当前上下文
        self._current_turn: Optional[TurnContext] = None

        # 钩子
        self._pre_process_hooks: List[Callable] = []
        self._post_process_hooks: List[Callable] = []

    async def start(self):
        """启动智能体"""
        logger.info(f"启动 {self.name} v{self.version}...")

        self._running = True

        # 初始化各子系统
        await self._init_memory()
        await self._init_tools()
        await self._init_mcp()
        await self._init_skills()
        await self._init_browser()
        await self._init_gateway()

        # 注册事件处理
        self._register_event_handlers()

        # 发布启动事件
        await self._event_bus.publish(Event(
            type="agent.started",
            data={"name": self.name, "version": self.version}
        ))

        logger.info(f"{self.name} 启动完成")

    async def _init_memory(self):
        """初始化记忆系统"""
        if not self.config.memory_enabled:
            return

        self._memory = UnifiedMemory(
            short_max=self.config.memory_short_max,
            short_ttl=self.config.memory_short_ttl,
            long_db=self.config.memory_long_db,
            long_enabled=self.config.memory_long_enabled
        )
        await self._memory.initialize()
        logger.info("记忆系统初始化完成")

    async def _init_tools(self):
        """初始化工具系统"""
        if not self.config.tools_enabled:
            return

        self._tools = ToolExecutor(
            timeout=self.config.tool_timeout,
            sandbox=self.config.tool_sandbox,
            event_bus=self._event_bus
        )
        await self._tools.initialize()
        logger.info("工具系统初始化完成")

    async def _init_mcp(self):
        """初始化MCP协议"""
        if not self.config.mcp_enabled:
            return

        self._mcp = MCPProtocol(
            timeout=self.config.mcp_timeout,
            event_bus=self._event_bus
        )
        await self._mcp.initialize()
        logger.info("MCP协议初始化完成")

    async def _init_skills(self):
        """初始化技能引擎"""
        if not self.config.skills_enabled:
            return

        self._skills = SkillEngine(
            skills_dir=self.config.skills_dir,
            auto_load=self.config.skills_auto_load,
            event_bus=self._event_bus
        )
        await self._skills.load_all()
        logger.info("技能引擎初始化完成")

    async def _init_browser(self):
        """初始化浏览器编排器"""
        if not self.config.browser_enabled:
            return

        self._browser = BrowserOrchestrator(
            provider=self.config.browser_provider,
            headless=self.config.browser_headless,
            viewport=self.config.browser_viewport
        )
        await self._browser.initialize()
        logger.info("浏览器编排器初始化完成")

    async def _init_gateway(self):
        """初始化网关"""
        if not self.config.gateway_enabled:
            return

        self._gateway = WebSocketGateway(
            url=self.config.gateway_url,
            token=self.config.gateway_token,
            event_bus=self._event_bus
        )
        await self._gateway.connect()
        logger.info("网关初始化完成")

    def _register_event_handlers(self):
        """注册事件处理器"""

        @self._event_bus.on("tool.started")
        async def on_tool_started(event: Event):
            logger.info(f"工具执行: {event.data.get('tool_name')}")
            self._state = AgentState.TOOL_CALL

        @self._event_bus.on("tool.completed")
        async def on_tool_completed(event: Event):
            logger.info(f"工具完成: {event.data.get('tool_name')}")
            self._state = AgentState.THINKING

        @self._event_bus.on("memory.recalled")
        async def on_memory_recalled(event: Event):
            logger.debug(f"记忆召回: {len(event.data.get('items', []))} 条")

        @self._event_bus.on("error")
        async def on_error(event: Event):
            logger.error(f"错误: {event.data.get('message')}")
            self._state = AgentState.ERROR

    async def process(self, user_input: str) -> str:
        """
        处理用户输入

        流程:
        1. 创建轮次上下文
        2. 预处理钩子
        3. 记忆检索
        4. Pipeline处理
        5. 后处理钩子
        6. 记忆存储
        """
        self._turn_counter += 1
        turn_id = f"turn_{self._turn_counter}_{int(time.time())}"

        # 创建上下文
        self._current_turn = TurnContext(
            turn_id=turn_id,
            user_input=user_input
        )
        self._state = AgentState.THINKING

        logger.info(f"[{turn_id}] 处理输入: {user_input[:50]}...")

        try:
            # 1. 预处理
            for hook in self._pre_process_hooks:
                user_input = await hook(self, user_input) or user_input

            # 2. 记忆检索
            memory_context = ""
            if self._memory:
                memory_context = await self._memory.recall(user_input)
                if memory_context:
                    self._current_turn.memory_used.append("recall")
                    await self._event_bus.publish(Event(
                        type="memory.recalled",
                        data={"query": user_input, "context": memory_context}
                    ))

            # 3. Pipeline处理
            response = await self._pipeline.process(
                user_input,
                context=self._current_turn,
                memory_context=memory_context
            )

            # 4. 后处理
            for hook in self._post_process_hooks:
                response = await hook(self, response) or response

            # 5. 记忆存储
            if self._memory:
                await self._memory.store(
                    user_input,
                    response,
                    importance=self._evaluate_importance(user_input, response)
                )

            self._state = AgentState.IDLE
            return response

        except Exception as e:
            logger.exception(f"处理失败: {e}")
            self._state = AgentState.ERROR
            await self._event_bus.publish(Event(
                type="error",
                data={"message": str(e), "turn_id": turn_id}
            ))
            return f"处理失败: {str(e)}"

    def _evaluate_importance(self, user_input: str, response: str) -> int:
        """评估对话重要性 (1-5)"""
        # 简单启发式评估
        score = 1

        # 有工具调用
        if self._current_turn.tools_used:
            score += 1

        # 有记忆召回
        if self._current_turn.memory_used:
            score += 1

        # 有技能激活
        if self._current_turn.skills_activated:
            score += 1

        # 响应较长
        if len(response) > 500:
            score += 1

        return min(score, 5)

    async def think(self, prompt: str, context: str = "") -> str:
        """
        调用LLM思考

        这是一个简化的实现。
        实际项目中应该调用真实的LLM API。
        """
        logger.debug(f"LLM调用: {prompt[:50]}...")

        # 这里是模拟响应
        # 实际应该调用: await self._llm.call(prompt, system_context)

        return f"[ZeusHammer思考中...] {prompt}"

    def register_pre_hook(self, hook: Callable):
        """注册预处理钩子"""
        self._pre_process_hooks.append(hook)

    def register_post_hook(self, hook: Callable):
        """注册后处理钩子"""
        self._post_process_hooks.append(hook)

    async def stop(self):
        """停止智能体"""
        logger.info("停止智能体...")

        await self._event_bus.publish(Event(
            type="agent.stopping",
            data={"name": self.name}
        ))

        # 关闭各子系统
        if self._gateway:
            await self._gateway.disconnect()
        if self._browser:
            await self._browser.close()
        if self._mcp:
            await self._mcp.shutdown()
        if self._memory:
            await self._memory.close()

        self._running = False
        self._state = AgentState.IDLE

        logger.info("智能体已停止")

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def memory(self) -> Optional[UnifiedMemory]:
        return self._memory

    @property
    def tools(self) -> Optional[ToolExecutor]:
        return self._tools

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus