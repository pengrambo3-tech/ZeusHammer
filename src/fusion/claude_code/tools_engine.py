"""
ClaudeCode Fusion Module - 工具执行引擎

融合 ClaudeCode 核心功能:
- partitionToolCalls 并发分区算法
- isConcurrencySafe 并发安全判断
- ToolResult 统一工具结果格式
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ToolConcurrencyType(Enum):
    """工具并发类型"""
    SAFE = "safe"           # 可并发执行
    DEPENDS_ON_RESULT = "depends_on_result"  # 依赖前一个结果
    BLOCKING = "blocking"   # 阻塞执行


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    input: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """工具执行结果"""
    id: str
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolPartition:
    """工具分区"""
    stage: int
    tool_calls: List[ToolCall]
    can_parallel: bool


class ToolDependencyAnalyzer:
    """
    工具依赖分析器
    
    ClaudeCode 核心算法：分析工具调用之间的依赖关系
    """

    # 需要结果的工具
    RESULT_DEPENDENT_TOOLS = {
        "read", "glob", "grep", "grep_directory",
        "bash_read", "file_operations_read",
        "web_tools", "browser_tools",
    }

    # 阻塞工具（必须串行执行）
    BLOCKING_TOOLS = {
        "write", "edit", "delete", "create",
        "bash_write", "file_operations_write",
        "terminal_execute",
    }

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)

    def analyze(self, tool_calls: List[ToolCall]) -> List[ToolPartition]:
        """
        分析工具调用依赖关系并分区
        
        Returns:
            分区列表，每个分区可以并行执行
        """
        partitions = []
        remaining = tool_calls.copy()
        stage = 0

        while remaining:
            partition, remaining = self._extract_next_partition(remaining, stage)
            if partition.tool_calls:
                partitions.append(partition)
            stage += 1

        return partitions

    def _extract_next_partition(
        self, 
        tool_calls: List[ToolCall],
        stage: int
    ) -> tuple:
        """提取下一个可执行的分区"""
        ready = []
        blocked = []

        # 已完成工具的ID
        completed_ids = set()

        for tc in tool_calls:
            if self._is_ready(tc, completed_ids):
                ready.append(tc)
            else:
                blocked.append(tc)

        can_parallel = self._can_parallel_execute(ready)

        partition = ToolPartition(
            stage=stage,
            tool_calls=ready,
            can_parallel=can_parallel
        )

        # 更新已完成ID
        for tc in ready:
            completed_ids.add(tc.id)

        return partition, blocked

    def _is_ready(self, tool_call: ToolCall, completed_ids: Set[str]) -> bool:
        """检查工具调用是否准备好执行"""
        for dep_id in tool_call.depends_on:
            if dep_id not in completed_ids:
                return False
        return True

    def _can_parallel_execute(self, tool_calls: List[ToolCall]) -> bool:
        """判断一组工具是否可以并行执行"""
        if not tool_calls:
            return False

        # 检查是否有阻塞工具
        for tc in tool_calls:
            if tc.name in self.BLOCKING_TOOLS:
                return False

        # 检查是否有互相依赖
        ids = {tc.id for tc in tool_calls}
        for tc in tool_calls:
            for dep in tc.depends_on:
                if dep in ids:
                    return False

        return True

    def get_concurrency_type(self, tool_name: str) -> ToolConcurrencyType:
        """获取工具的并发类型"""
        if tool_name in self.BLOCKING_TOOLS:
            return ToolConcurrencyType.BLOCKING
        elif tool_name in self.RESULT_DEPENDENT_TOOLS:
            return ToolConcurrencyType.DEPENDS_ON_RESULT
        return ToolConcurrencyType.SAFE


class ToolExecutor:
    """
    工具执行器
    
    ClaudeCode 核心算法：并发执行工具调用
    """

    def __init__(self, permission_level: str = "safe"):
        self.analyzer = ToolDependencyAnalyzer()
        self.permission_level = permission_level
        self.executor = ThreadPoolExecutor(max_workers=8)
        self._tool_registry: Dict[str, callable] = {}
        self._results: Dict[str, ToolResult] = {}

    def register_tool(self, name: str, handler: callable):
        """注册工具处理器"""
        self._tool_registry[name] = handler
        logger.info(f"Registered tool: {name}")

    async def run_tools(self, tool_calls: List[Dict]) -> List[ToolResult]:
        """
        执行工具调用列表
        
        使用 ClaudeCode 分区算法优化并发
        """
        # 转换为 ToolCall 对象
        calls = [
            ToolCall(
                id=tc.get("id", f"tool_{i}"),
                name=tc.get("name", tc.get("function", {}).get("name", "")),
                input=tc.get("input", tc.get("function", {}).get("arguments", {})),
                depends_on=tc.get("depends_on", [])
            )
            for i, tc in enumerate(tool_calls)
        ]

        # 分析依赖并分区
        partitions = self.analyzer.analyze(calls)

        # 执行分区
        all_results = []
        self._results.clear()

        for partition in partitions:
            if partition.can_parallel:
                # 并行执行
                results = await self._run_partition_parallel(partition)
            else:
                # 串行执行
                results = await self._run_partition_sequential(partition)

            all_results.extend(results)

            # 存储结果供后续使用
            for result in results:
                self._results[result.id] = result

        return all_results

    async def _run_partition_parallel(
        self, 
        partition: ToolPartition
    ) -> List[ToolResult]:
        """并行执行分区"""
        tasks = []
        for tc in partition.tool_calls:
            task = self._execute_tool(tc)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ToolResult(
                    id=partition.tool_calls[i].id,
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def _run_partition_sequential(
        self, 
        partition: ToolPartition
    ) -> List[ToolResult]:
        """串行执行分区"""
        results = []
        for tc in partition.tool_calls:
            result = await self._execute_tool(tc)
            results.append(result)
        return results

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行单个工具"""
        tool_name = tool_call.name

        # 检查权限
        if not self._check_permission(tool_name):
            return ToolResult(
                id=tool_call.id,
                success=False,
                error=f"Tool '{tool_name}' not permitted in {self.permission_level} mode"
            )

        # 获取工具处理器
        handler = self._tool_registry.get(tool_name)
        if not handler:
            return ToolResult(
                id=tool_call.id,
                success=False,
                error=f"Tool '{tool_name}' not found"
            )

        try:
            # 执行工具
            if asyncio.iscoroutinefunction(handler):
                output = await handler(**tool_call.input)
            else:
                output = handler(**tool_call.input)

            return ToolResult(
                id=tool_call.id,
                success=True,
                output=output
            )

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {e}")
            return ToolResult(
                id=tool_call.id,
                success=False,
                error=str(e)
            )

    def _check_permission(self, tool_name: str) -> bool:
        """检查工具权限"""
        if self.permission_level == "full_open":
            return True

        # 危险工具需要确认
        dangerous_tools = {
            "write", "edit", "delete", "create",
            "bash", "shell", "terminal",
        }

        if self.permission_level == "safe":
            return tool_name not in dangerous_tools

        return True

    def get_result(self, tool_id: str) -> Optional[ToolResult]:
        """获取工具执行结果"""
        return self._results.get(tool_id)


class OTelLogger:
    """
    OpenTelemetry 遥测日志
    
    ClaudeCode 核心功能：结构化日志记录和追踪
    """

    def __init__(self, service_name: str = "ZuesHammer"):
        self.service_name = service_name
        self._spans: Dict[str, Dict] = {}
        self._logs: List[Dict] = []

    def start_span(self, name: str, attributes: Dict = None) -> str:
        """开始追踪跨度"""
        import uuid
        span_id = str(uuid.uuid4())[:16]

        self._spans[span_id] = {
            "name": name,
            "attributes": attributes or {},
            "start_time": None,
            "end_time": None,
            "events": []
        }

        return span_id

    def end_span(self, span_id: str, status: str = "ok"):
        """结束追踪跨度"""
        if span_id in self._spans:
            self._spans[span_id]["status"] = status

    def log(
        self,
        level: str,
        message: str,
        attributes: Dict = None,
        span_id: str = None
    ):
        """记录日志"""
        import time

        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "attributes": attributes or {},
            "service": self.service_name,
            "span_id": span_id
        }

        self._logs.append(log_entry)

        # 根据级别打印
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def log_tool_call(self, tool_name: str, input_data: Dict, result: Any):
        """记录工具调用"""
        self.log(
            "info",
            f"Tool call: {tool_name}",
            attributes={
                "tool.name": tool_name,
                "tool.input": str(input_data)[:200],
                "tool.success": result.get("success", False) if isinstance(result, dict) else True
            }
        )

    def get_trace(self, span_id: str) -> Optional[Dict]:
        """获取追踪信息"""
        return self._spans.get(span_id)


# 全局遥测实例
_telemetry: Optional[OTelLogger] = None


def get_telemetry() -> OTelLogger:
    """获取遥测实例"""
    global _telemetry
    if _telemetry is None:
        _telemetry = OTelLogger()
    return _telemetry
