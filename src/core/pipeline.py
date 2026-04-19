"""
ZeusHammer 处理管道

原创设计，处理用户输入的管道。

管道阶段:
1. Input  - 输入预处理
2. Parse  - 意图解析
3. Plan   - 行动计划
4. Execute - 执行
5. Output - 输出后处理
"""

import asyncio
import logging
import re
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Stage(Enum):
    """管道阶段"""
    INPUT = "input"
    PARSE = "parse"
    PLAN = "plan"
    EXECUTE = "execute"
    OUTPUT = "output"


@dataclass
class PipelineContext:
    """管道上下文"""
    user_input: str
    intent: str = ""
    entities: Dict[str, Any] = None
    plan: List[Dict] = None
    results: List[Any] = None
    response: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        self.entities = self.entities or {}
        self.plan = self.plan or []
        self.results = self.results or []
        self.metadata = self.metadata or {}


class Pipeline:
    """
    处理管道

    原创设计，统一处理流程。

    特点:
    - 阶段化处理
    - 可插拔处理器
    - 并行执行支持
    - 错误恢复
    """

    def __init__(self, core):
        self.core = core
        self._handlers: Dict[Stage, List[Callable]] = {
            stage: [] for stage in Stage
        }
        self._error_handlers: Dict[Stage, Callable] = {}

        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认处理器"""

        # Input阶段
        async def trim_input(ctx: PipelineContext):
            ctx.user_input = ctx.user_input.strip()
            # 移除多余空白
            ctx.user_input = re.sub(r'\s+', ' ', ctx.user_input)

        self.register(Stage.INPUT, trim_input)

        # Parse阶段 - 意图识别
        async def parse_intent(ctx: PipelineContext):
            text = ctx.user_input.lower()

            # 命令检测
            if text.startswith('/'):
                ctx.intent = "command"
                ctx.entities["command"] = text[1:].split()[0] if text[1:] else ""
                ctx.entities["args"] = text[1:].split()[1:]

            # 问句检测
            elif any(text.startswith(q) for q in ['what', 'how', 'why', 'when', 'where', 'who', 'which', '?']):
                ctx.intent = "question"

            # 代码检测
            elif '```' in ctx.user_input or 'function' in text or 'def ' in text:
                ctx.intent = "code"

            # 文件操作
            elif any(kw in text for kw in ['read', 'write', 'file', 'folder', 'directory']):
                ctx.intent = "file_operation"

            # 搜索
            elif any(kw in text for kw in ['search', 'find', 'look', 'google']):
                ctx.intent = "search"

            # 网络请求
            elif any(kw in text for kw in ['fetch', 'download', 'http', 'url', 'get', 'post']):
                ctx.intent = "web_request"

            # Git操作
            elif any(kw in text for kw in ['git', 'commit', 'push', 'pull', 'branch']):
                ctx.intent = "git"

            # 默认
            else:
                ctx.intent = "general"

        self.register(Stage.PARSE, parse_intent)

        # Plan阶段 - 行动计划
        async def create_plan(ctx: PipelineContext):
            intent = ctx.intent

            if intent == "command":
                # 命令直接执行
                ctx.plan = [{"type": "command", "action": ctx.entities.get("command")}]

            elif intent == "file_operation":
                ctx.plan = [
                    {"type": "tool", "tool": "file_tools", "action": "list"},
                    {"type": "think"}
                ]

            elif intent == "search":
                ctx.plan = [
                    {"type": "tool", "tool": "web_tools", "action": "search"},
                    {"type": "think"}
                ]

            elif intent == "web_request":
                ctx.plan = [
                    {"type": "tool", "tool": "web_tools", "action": "fetch"},
                    {"type": "think"}
                ]

            elif intent == "git":
                ctx.plan = [
                    {"type": "tool", "tool": "git_tools", "action": "status"},
                    {"type": "think"}
                ]

            elif intent == "code":
                ctx.plan = [
                    {"type": "think"}
                ]

            else:
                ctx.plan = [{"type": "think"}]

        self.register(Stage.PLAN, create_plan)

        # Execute阶段
        async def execute_plan(ctx: PipelineContext):
            for step in ctx.plan:
                step_type = step.get("type")

                if step_type == "think":
                    response = await self.core.think(
                        ctx.user_input,
                        context=self._build_context(ctx)
                    )
                    ctx.response = response

                elif step_type == "tool":
                    tool_name = step.get("tool")
                    if self.core.tools:
                        result = await self.core.tools.execute(
                            tool_name,
                            step.get("params", {})
                        )
                        ctx.results.append(result)

                elif step_type == "command":
                    cmd = step.get("action")
                    if cmd == "help":
                        ctx.response = self._get_help()
                    elif cmd == "status":
                        ctx.response = self._get_status()
                    elif cmd == "tools":
                        ctx.response = self._list_tools()
                    else:
                        ctx.response = f"未知命令: /{cmd}"

        self.register(Stage.EXECUTE, execute_plan)

        # Output阶段
        async def format_output(ctx: PipelineContext):
            if not ctx.response:
                # 如果还没有响应，从结果构建
                if ctx.results:
                    ctx.response = self._format_results(ctx.results)
                else:
                    ctx.response = "[ZeusHammer] 已处理您的请求"

        self.register(Stage.OUTPUT, format_output)

    def register(self, stage: Stage, handler: Callable):
        """注册处理器"""
        self._handlers[stage].append(handler)

    def unregister(self, stage: Stage, handler: Callable):
        """注销处理器"""
        if handler in self._handlers[stage]:
            self._handlers[stage].remove(handler)

    async def process(self, user_input: str, context: Any = None, **kwargs) -> str:
        """
        处理输入

        流程:
        INPUT -> PARSE -> PLAN -> EXECUTE -> OUTPUT
        """
        ctx = PipelineContext(user_input=user_input)

        # 按顺序执行各阶段
        for stage in Stage:
            if stage not in self._handlers:
                continue

            try:
                for handler in self._handlers[stage]:
                    await handler(ctx)
            except Exception as e:
                logger.error(f"阶段 {stage.value} 处理失败: {e}")

                # 尝试错误恢复
                if stage in self._error_handlers:
                    await self._error_handlers[stage](ctx, e)
                else:
                    ctx.response = f"处理失败: {str(e)}"
                    break

        return ctx.response

    def _build_context(self, ctx: PipelineContext) -> str:
        """构建上下文"""
        parts = [f"意图: {ctx.intent}"]

        if ctx.entities:
            parts.append(f"实体: {ctx.entities}")

        if ctx.results:
            parts.append(f"结果: {ctx.results[:3]}")

        return "\n".join(parts)

    def _get_help(self) -> str:
        return """
ZeusHammer 可用命令:
  /help     - 显示帮助
  /status   - 显示状态
  /tools    - 显示可用工具
  /exit     - 退出
"""

    def _get_status(self) -> str:
        return f"""
ZeusHammer 状态:
  版本: {self.core.version}
  状态: {self.core.state}
  记忆: {'已启用' if self.core.memory else '未启用'}
  工具: {'已启用' if self.core.tools else '未启用'}
"""

    def _list_tools(self) -> str:
        if not self.core.tools:
            return "工具系统未启用"
        tools = self.core.tools.list_tools()
        return f"可用工具: {', '.join(tools)}"

    def _format_results(self, results: List) -> str:
        """格式化结果"""
        if not results:
            return ""

        lines = []
        for i, result in enumerate(results):
            if isinstance(result, dict):
                lines.append(f"结果 {i+1}:")
                for key, value in result.items():
                    lines.append(f"  {key}: {value}")
            else:
                lines.append(str(result))

        return "\n".join(lines)[:1000]