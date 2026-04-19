"""
ZeusHammer 工具执行器

融合三大项目最佳实践的原创设计:

ClaudeCode贡献:
- 权限检查系统
- 工具验证
- 错误处理

Hermes贡献:
- 工具注册表
- 分类管理
- 工具发现

OpenClaw贡献:
- 命令别名
- 上下文传递
- 结果缓存

原创增强:
- 统一的工具接口
- 沙箱执行
- 权限策略
"""

import asyncio
import logging
import time
import inspect
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别"""
    NONE = 0      # 完全禁止
    READ = 1      # 只读
    WRITE = 2     # 读写
    EXECUTE = 3   # 可执行
    ADMIN = 4     # 管理


@dataclass
class ToolSchema:
    """工具Schema"""
    name: str
    description: str
    category: str = "general"
    parameters: Dict[str, Any] = field(default_factory=dict)
    returns: Dict[str, Any] = field(default_factory=dict)
    permission: PermissionLevel = PermissionLevel.WRITE
    timeout: int = 30
    cacheable: bool = False


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any = None
    error: str = None
    execution_time: float = 0
    cached: bool = False


class Tool:
    """
    工具基类

    所有工具都应该继承此类或实现相同的接口。
    """

    def __init__(self, name: str, description: str = "", category: str = "general"):
        self.name = name
        self.description = description
        self.category = category
        self._schema = ToolSchema(
            name=name,
            description=description,
            category=category
        )

    def get_schema(self) -> ToolSchema:
        """获取Schema"""
        return self._schema

    async def execute(self, **kwargs) -> Any:
        """执行工具 - 子类实现"""
        raise NotImplementedError

    async def validate(self, params: Dict[str, Any]) -> tuple[bool, str]:
        """验证参数 - 可选实现"""
        return True, ""

    async def before_execute(self, params: Dict[str, Any]):
        """执行前钩子 - 可选实现"""
        pass

    async def after_execute(self, params: Dict[str, Any], result: Any):
        """执行后钩子 - 可选实现"""
        pass


class ToolExecutor:
    """
    工具执行器

    融合三大项目最佳实践:

    1. 工具注册 (Hermes):
       - 统一的工具注册表
       - 分类管理
       - 别名支持

    2. 权限检查 (ClaudeCode):
       - 分层权限
       - 路径限制
       - 用户确认

    3. 执行管理 (OpenClaw):
       - 超时控制
       - 结果缓存
       - 错误恢复
    """

    def __init__(
        self,
        timeout: int = 30,
        sandbox: bool = True,
        event_bus=None,
        permission_mode: str = "smart"
    ):
        self.timeout = timeout
        self.sandbox = sandbox
        self.event_bus = event_bus
        self.permission_mode = permission_mode

        # 工具注册表
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, Set[str]] = {}
        self._aliases: Dict[str, str] = {}

        # 结果缓存
        self._cache: Dict[str, ToolResult] = {}
        self._cache_max = 100

        # 权限配置
        self._path_rules: Dict[str, PermissionLevel] = {}

    async def initialize(self):
        """初始化 - 注册内置工具"""
        logger.info("初始化工具执行器...")

        # 注册内置工具
        from .builtin import BuiltinTools
        builtin = BuiltinTools()

        for tool in builtin.get_all():
            self.register(tool)

        logger.info(f"已注册 {len(self._tools)} 个工具")

    def register(
        self,
        tool: Tool,
        category: str = None,
        alias: str = None,
        **kwargs
    ):
        """
        注册工具

        融合设计:
        - Hermes的注册机制
        - OpenClaw的别名系统
        - 分类管理
        """
        name = tool.name

        # 注册到主表
        self._tools[name] = tool

        # 分类管理
        cat = category or tool.category
        if cat not in self._categories:
            self._categories[cat] = set()
        self._categories[cat].add(name)

        # 别名
        if alias:
            self._aliases[alias] = name

        # 合并schema
        if kwargs:
            schema = tool.get_schema()
            for k, v in kwargs.items():
                if hasattr(schema, k):
                    setattr(schema, k, v)

        logger.debug(f"注册工具: {name} (分类: {cat})")

    def unregister(self, name: str):
        """注销工具"""
        if name not in self._tools:
            return

        tool = self._tools[name]

        # 从分类移除
        cat = tool.category
        if cat in self._categories:
            self._categories[cat].discard(name)

        # 从别名移除
        self._aliases = {k: v for k, v in self._aliases.items() if v != name}

        # 删除
        del self._tools[name]

        # 从缓存移除
        self._cache.pop(name, None)

        logger.debug(f"注销工具: {name}")

    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        # 检查别名
        if name in self._aliases:
            name = self._aliases[name]

        return self._tools.get(name)

    def list_tools(self, category: str = None) -> List[str]:
        """列出工具"""
        if category:
            return list(self._categories.get(category, set()))
        return list(self._tools.keys())

    def list_categories(self) -> List[str]:
        """列出分类"""
        return list(self._categories.keys())

    def get_by_category(self, category: str) -> List[Tool]:
        """按分类获取"""
        names = self._categories.get(category, set())
        return [self._tools[n] for n in names if n in self._tools]

    # =========================================================================
    # 权限检查 (ClaudeCode风格)
    # =========================================================================

    def _check_permission(self, tool: Tool, params: Dict) -> tuple[bool, str]:
        """
        检查权限

        融合设计:
        - ClaudeCode的权限级别
        - Hermes的路径规则
        - OpenClaw的模式匹配
        """
        # locked模式最严格
        if self.permission_mode == "locked":
            # 只允许白名单工具
            allowed = {"file.read", "file.list", "web.get", "search"}
            if tool.name not in allowed:
                return False, f"工具 {tool.name} 在locked模式下被禁用"

        # 检查参数中的路径权限
        if "path" in params:
            path = str(params["path"])
            level = self._get_path_permission(path)

            if tool.get_schema().permission.value > level.value:
                return False, f"路径 {path} 权限不足"

        # 检查沙箱
        if self.sandbox and tool.category in ("shell", "exec"):
            # 危险工具需要特殊权限
            if self.permission_mode != "open":
                return False, f"危险工具 {tool.name} 需要open权限模式"

        return True, ""

    def _get_path_permission(self, path: str) -> PermissionLevel:
        """获取路径权限"""
        path = str(Path(path).resolve())

        for pattern, level in sorted(
            self._path_rules.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if pattern in path:
                return level

        # 默认权限
        if self.permission_mode == "open":
            return PermissionLevel.ADMIN
        elif self.permission_mode == "smart":
            return PermissionLevel.WRITE
        else:
            return PermissionLevel.READ

    def set_path_rule(self, pattern: str, level: PermissionLevel):
        """设置路径规则"""
        self._path_rules[pattern] = level

    # =========================================================================
    # 执行 (融合设计)
    # =========================================================================

    async def execute(self, tool_name: str, params: Dict = None, **kwargs) -> ToolResult:
        """
        执行工具

        融合设计:
        - Hermes的执行流程
        - ClaudeCode的验证
        - OpenClaw的缓存
        """
        params = params or {}
        params.update(kwargs)

        start_time = time.time()
        cache_key = f"{tool_name}:{hash(frozenset(params.items()))}"

        # 检查缓存
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            cached.cached = True
            logger.debug(f"缓存命中: {tool_name}")
            return cached

        # 获取工具
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"工具不存在: {tool_name}",
                execution_time=time.time() - start_time
            )

        # 权限检查
        allowed, reason = self._check_permission(tool, params)
        if not allowed:
            await self._publish_event("tool.denied", tool_name, reason)
            return ToolResult(
                success=False,
                error=reason,
                execution_time=time.time() - start_time
            )

        # 发布开始事件
        await self._publish_event("tool.started", tool_name, params)

        try:
            # 执行前钩子
            await tool.before_execute(params)

            # 参数验证
            valid, msg = await tool.validate(params)
            if not valid:
                return ToolResult(
                    success=False,
                    error=f"参数验证失败: {msg}",
                    execution_time=time.time() - start_time
                )

            # 执行
            timeout = tool.get_schema().timeout or self.timeout
            result = await asyncio.wait_for(
                tool.execute(**params),
                timeout=timeout
            )

            # 执行后钩子
            await tool.after_execute(params, result)

            # 构建结果
            tool_result = ToolResult(
                success=True,
                data=result,
                execution_time=time.time() - start_time
            )

            # 缓存
            if tool.get_schema().cacheable:
                self._cache[cache_key] = tool_result
                self._enforce_cache_limit()

            await self._publish_event("tool.completed", tool_name, result)
            return tool_result

        except asyncio.TimeoutError:
            await self._publish_event("tool.timeout", tool_name, timeout)
            return ToolResult(
                success=False,
                error=f"执行超时: {timeout}秒",
                execution_time=time.time() - start_time
            )

        except Exception as e:
            logger.exception(f"工具执行失败: {tool_name}")
            await self._publish_event("tool.error", tool_name, str(e))
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time
            )

    async def execute_chain(self, chain: List[Dict]) -> List[ToolResult]:
        """执行工具链"""
        results = []

        for step in chain:
            tool_name = step.get("tool")
            params = step.get("params", {})

            result = await self.execute(tool_name, params)

            # 如果失败，可选择停止或继续
            if not result.success and step.get("stop_on_error"):
                results.append(result)
                break

            results.append(result)

            # 如果有输出，可传递给下一步
            if result.success and result.data:
                step["_result"] = result.data

        return results

    async def _publish_event(self, event_type: str, tool_name: str, data: Any):
        """发布事件"""
        if self.event_bus:
            await self.event_bus.publish(type=event_type, data={
                "tool_name": tool_name,
                "data": data
            })

    def _enforce_cache_limit(self):
        """强制缓存限制"""
        while len(self._cache) > self._cache_max:
            # 删除最早的
            oldest = next(iter(self._cache))
            del self._cache[oldest]

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "total_tools": len(self._tools),
            "categories": len(self._categories),
            "aliases": len(self._aliases),
            "cache_size": len(self._cache),
            "permission_mode": self.permission_mode
        }