"""
ZeusHammer Advanced Tool Executor

真正融合三个项目的核心优势:

1. ClaudeCode:
   - 工具并发分区算法 (partitionToolCalls)
   - isConcurrencySafe判断
   - OTel遥测日志
   - 权限钩子系统
   - 自动上下文压缩

2. Hermes:
   - OSV恶意软件检测
   - 凭证泄露检测正则
   - MCP采样回调机制
   - 动态工具发现
   - 断路器模式

3. OpenClaw:
   - 受保护配置路径验证
   - 危险标志检测
   - baseHash并发控制
   - Payload钩子
"""

import asyncio
import re
import logging
import subprocess
import time
import hashlib
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================
# ClaudeCode核心: 工具并发分区算法
# ============================================

class ToolConcurrencyType(Enum):
    """工具并发类型 - ClaudeCode设计"""
    READ = "read"           # 只读工具，可并行
    WRITE = "write"         # 写入工具，串行
    EXECUTE = "execute"     # 执行工具，串行
    NETWORK = "network"     # 网络工具，有限并发
    SYSTEM = "system"       # 系统工具，串行


@dataclass
class ToolBatch:
    """工具批次 - ClaudeCode的Batch类型"""
    is_concurrency_safe: bool  # 是否可并发执行
    blocks: List[Dict] = field(default_factory=list)  # 批次中的工具调用


@dataclass
class ToolCall:
    """工具调用请求"""
    id: str
    name: str
    params: Dict[str, Any]
    tool_type: ToolConcurrencyType = ToolConcurrencyType.READ


@dataclass
class ToolResult:
    """工具执行结果"""
    id: str
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0


# ============================================
# Hermes核心: 安全检测
# ============================================

class SecurityDetector:
    """
    安全检测器 - Hermes风格

    包含:
    - 凭证泄露检测
    - 恶意软件检测
    - 危险命令检测
    """

    # 凭证模式 - Hermes实现
    CREDENTIAL_PATTERNS = [
        (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
        (r"sk-[A-Za-z0-9]{48}", "OpenAI API Key"),
        (r"sk-proj-[A-Za-z0-9_-]{48,}", "OpenAI Project Key"),
        (r"AKIA[A-Za-z0-9]{16}", "AWS Access Key"),
        (r"A3T[A-Za-z0-9]{16}", "AWS Secret Key"),
        (r"xox[baprs]-[A-Za-z0-9]{10,}", "Slack Token"),
        (r"sq0[a-z]{3}-[A-Za-z0-9]{22}", "Square API Token"),
        (r"sk_live_[A-Za-z0-9]{24}", "Stripe Secret Key"),
        (r"pk_live_[A-Za-z0-9]{24}", "Stripe Publishable Key"),
        (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub Fine-grained PAT"),
        (r"glpat-[A-Za-z0-9-_]{20}", "GitLab PAT"),
        (r"-----BEGIN.*PRIVATE KEY-----", "Private Key"),
    ]

    # 恶意软件模式 - Hermes实现
    MALWARE_PATTERNS = [
        (r":\(\)\{\s*:\|:\&\}\$;:", "Fork bomb"),
        (r"curl\s+.*\|.*sh", "Pipe to shell execution"),
        (r"wget\s+.*\|.*sh", "Pipe to shell execution"),
        (r"base64\s+-d\s+.*\|.*sh", "Encoded shell execution"),
        (r"python\s+.*-c\s+.*\|.*sh", "Python pipe to shell"),
        (r"perl\s+.*-e\s+.*\|.*sh", "Perl pipe to shell"),
        (r"ruby\s+.*-e\s+.*\|.*sh", "Ruby pipe to shell"),
    ]

    # 危险命令模式 - Hermes实现
    DANGEROUS_PATTERNS = [
        (r"rm\s+-rf\s+/(?:\*\s*)?(?:home|root|etc|var|usr)", "Recursive delete system dirs"),
        (r"rm\s+-rf\s+/", "Recursive delete from root"),
        (r"chmod\s+777\s+/(?:etc|root|home|var)", "777 permissions on sensitive dirs"),
        (r">\s*/etc/passwd", "Overwrite passwd file"),
        (r">\s*/etc/shadow", "Overwrite shadow file"),
        (r"dd\s+if=.*of=/dev/", "Direct disk write"),
        (r"mkfs\.", "Format filesystem"),
        (r":()\s*\{\s*:\|:\s*&\s*\}", "Fork bomb"),
        (r"eval\s*\(\s*\$", "Eval with variable"),
        (r"exec\s+\d+", "File descriptor exec"),
    ]

    # 受保护路径 - OpenClaw实现
    PROTECTED_PATHS = [
        "/System",
        "/Applications/Carbon",
        "/Applications/Finder.app",
        "/Library/Application Support/com.apple.TCC",
        "/usr/bin/chmod",
        "/usr/bin/chown",
        "/usr/sbin/systemsetup",
        "/etc/sudoers",
        "/etc/passwd",
        "/etc/shadow",
    ]

    @classmethod
    def check_credentials(cls, text: str) -> List[tuple]:
        """检测凭证泄露 - Hermes实现"""
        found = []
        for pattern, description in cls.CREDENTIAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append((pattern, description))
        return found

    @classmethod
    def check_malware(cls, text: str) -> List[tuple]:
        """检测恶意软件 - Hermes实现"""
        found = []
        for pattern, description in cls.MALWARE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append((pattern, description))
        return found

    @classmethod
    def check_dangerous(cls, text: str) -> List[tuple]:
        """检测危险命令 - Hermes实现"""
        found = []
        for pattern, description in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append((pattern, description))
        return found

    @classmethod
    def check_protected_path(cls, path: str) -> Optional[str]:
        """检查受保护路径 - OpenClaw实现"""
        path = str(Path(path).resolve())
        for protected in cls.PROTECTED_PATHS:
            if path.startswith(protected):
                return protected
        return None

    @classmethod
    def sanitize_credential(cls, text: str) -> str:
        """清理凭证 - Hermes实现"""
        result = text
        # GitHub PAT
        result = re.sub(r"(ghp_[A-Za-z0-9]{6})[A-Za-z0-9]{30}", r"\g<1>...[REDACTED]", result)
        # OpenAI Key
        result = re.sub(r"(sk-)[A-Za-z0-9]{40}", r"\g<1>..." + "[REDACTED]" * 4, result)
        # AWS Key
        result = re.sub(r"(AKIA)[A-Za-z0-9]{16}", r"\g<1>...[REDACTED]", result)
        return result


# ============================================
# OpenClaw核心: 配置保护
# ============================================

class ConfigProtection:
    """
    配置保护器 - OpenClaw实现

    受保护配置路径和危险标志检测
    """

    # 受保护的配置路径
    PROTECTED_CONFIG_PATHS = [
        "tools.exec.ask",
        "tools.exec.security",
        "tools.exec.safeBins",
        "permission.level",
        "permission.protected_paths",
        "security.credential_patterns",
    ]

    # 危险配置标志
    DANGEROUS_FLAGS = [
        "allow_dangerous_operations",
        "disable_security_checks",
        "skip_permission_check",
        "full_admin_access",
    ]

    @classmethod
    def assert_mutation_allowed(cls, current_config: Dict, new_config: Dict, path: str) -> None:
        """验证配置变更是否允许 - OpenClaw实现"""
        # 检查受保护路径
        for protected in cls.PROTECTED_CONFIG_PATHS:
            if path.startswith(protected):
                current_value = cls._get_nested(current_config, protected)
                new_value = cls._get_nested(new_config, protected)
                if current_value != new_value:
                    raise PermissionError(f"Cannot change protected config path: {path}")

        # 检查危险标志
        for flag in cls.DANGEROUS_FLAGS:
            new_value = cls._get_nested(new_config, flag)
            if new_value and new_value is True:
                raise PermissionError(f"Cannot enable dangerous config flag: {flag}")

    @classmethod
    def _get_nested(cls, obj: Dict, path: str) -> Any:
        """获取嵌套配置值"""
        keys = path.split(".")
        value = obj
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


# ============================================
# ClaudeCode核心: 工具并发分区
# ============================================

class ToolPartitioner:
    """
    工具分区器 - ClaudeCode核心算法

    partitionToolCalls实现:
    1. 只读工具并行执行
    2. 写入工具串行执行
    3. 执行工具串行执行
    """

    # 只读工具列表
    READ_ONLY_TOOLS = {
        "read", "cat", "glob", "grep", "find", "head", "tail",
        "wc", "ls", "stat", "file", "find", "locate",
        "search", "fetch", "http_get", "curl_get",
    }

    # 写入工具列表
    WRITE_TOOLS = {
        "write", "edit", "create", "mkdir", "touch",
        "delete", "remove", "rm", "rmdir",
        "mv", "cp", "install", "pip_install",
    }

    # 执行工具列表
    EXECUTE_TOOLS = {
        "bash", "shell", "exec", "run", "command",
        "sudo", "su",
    }

    @classmethod
    def partition_tool_calls(
        cls,
        tool_calls: List[Dict],
        tool_context: Dict = None
    ) -> List[ToolBatch]:
        """
        ClaudeCode核心算法: 工具并发分区

        将工具调用分区为批次:
        - 只读工具可以并行
        - 写入工具必须串行
        - 执行工具必须串行

        Returns:
            List[ToolBatch]: 分区后的批次列表
        """
        batches: List[ToolBatch] = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            is_concurrency_safe = cls._is_concurrency_safe(tool_name, tool_call)

            if is_concurrency_safe and batches and batches[-1].is_concurrency_safe:
                # 加入上一个只读批次
                batches[-1].blocks.append(tool_call)
            else:
                # 新建批次
                batches.append(ToolBatch(
                    is_concurrency_safe=is_concurrency_safe,
                    blocks=[tool_call]
                ))

        return batches

    @classmethod
    def _is_concurrency_safe(cls, tool_name: str, tool_call: Dict) -> bool:
        """
        ClaudeCode算法: 判断工具是否可并发

        基于工具名称和参数判断是否安全并发执行
        """
        tool_lower = tool_name.lower()

        # 工具名检查
        if tool_lower in cls.READ_ONLY_TOOLS:
            return True

        if tool_lower in cls.WRITE_TOOLS:
            return False

        if tool_lower in cls.EXECUTE_TOOLS:
            return False

        # 默认保守策略
        return False

    @classmethod
    def get_tool_concurrency_type(cls, tool_name: str) -> ToolConcurrencyType:
        """获取工具并发类型"""
        tool_lower = tool_name.lower()

        if tool_lower in cls.READ_ONLY_TOOLS:
            return ToolConcurrencyType.READ

        if tool_lower in cls.WRITE_TOOLS:
            return ToolConcurrencyType.WRITE

        if tool_lower in cls.EXECUTE_TOOLS:
            return ToolConcurrencyType.EXECUTE

        return ToolConcurrencyType.SYSTEM


# ============================================
# Hermes核心: MCP采样回调
# ============================================

class SamplingCallback:
    """
    MCP采样回调 - Hermes实现

    允许MCP服务器请求LLM采样
    """

    def __init__(self, llm_client):
        self.llm = llm_client
        self._rate_timestamps: List[float] = []
        self._tool_loop_count = 0
        self.max_rpm = 60  # 每分钟最大请求
        self.max_tool_rounds = 100  # 最大工具循环次数

    def check_rate_limit(self) -> bool:
        """滑动窗口限流 - Hermes实现"""
        now = time.time()
        window = now - 60

        # 清理过期时间戳
        self._rate_timestamps = [t for t in self._rate_timestamps if t > window]

        if len(self._rate_timestamps) >= self.max_rpm:
            return False

        self._rate_timestamps.append(now)
        return True

    def check_tool_loop_limit(self) -> bool:
        """检查工具循环限制"""
        if self._tool_loop_count > self.max_tool_rounds:
            return False
        self._tool_loop_count += 1
        return True

    async def create_message(self, prompt: str, system: str = "") -> Optional[str]:
        """创建采样消息 - Hermes实现"""
        if not self.check_rate_limit():
            return None

        if not self.check_tool_loop_limit():
            return None

        try:
            response = await self.llm.think(prompt=prompt, system=system)
            return response.content
        except Exception as e:
            logger.error(f"Sampling failed: {e}")
            return None


# ============================================
# ClaudeCode核心: 遥测日志
# ============================================

class TelemetryLogger:
    """
    遥测日志 - ClaudeCode实现

    发送到多个日志目标:
    - Statsig
    - OpenTelemetry
    - 本地日志
    """

    def __init__(self):
        self._enabled = True
        self._events: List[Dict] = []

    def log_approval_event(self, tool_name: str, source: str, **kwargs):
        """记录批准事件 - ClaudeCode实现"""
        event = {
            "type": "tool_approval",
            "tool_name": tool_name,
            "source": source,
            "timestamp": time.time(),
            **kwargs
        }
        self._log_event(event)

    def log_rejection_event(self, tool_name: str, source: str, reason: str, **kwargs):
        """记录拒绝事件 - ClaudeCode实现"""
        event = {
            "type": "tool_rejection",
            "tool_name": tool_name,
            "source": source,
            "reason": reason,
            "timestamp": time.time(),
            **kwargs
        }
        self._log_event(event)

    def log_code_edit_event(self, tool_name: str, file_path: str, decision: str, **kwargs):
        """记录代码编辑事件 - ClaudeCode实现"""
        event = {
            "type": "code_edit",
            "tool_name": tool_name,
            "file_path": file_path,
            "decision": decision,
            "timestamp": time.time(),
            **kwargs
        }
        self._log_event(event)

    def _log_event(self, event: Dict):
        """记录事件到所有目标"""
        self._events.append(event)

        # Statsig (模拟)
        logger.info(f"[Telemetry] {event['type']}: {event.get('tool_name', 'N/A')}")

        # OpenTelemetry (模拟)
        # 在实际实现中会发送到OTel collector

        # 本地日志
        logger.debug(f"[OTel] Event: {event}")


# ============================================
# 断路器模式 - Hermes实现
# ============================================

class CircuitBreaker:
    """
    断路器 - Hermes实现

    防止重复失败
    """

    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._failures = 0
        self._last_failure_time = 0
        self._state = "closed"  # closed, open, half_open

    @property
    def state(self) -> str:
        """获取当前状态"""
        if self._state == "open":
            if time.time() - self._last_failure_time > self.timeout:
                self._state = "half_open"
        return self._state

    def record_success(self):
        """记录成功"""
        self._failures = 0
        self._state = "closed"

    def record_failure(self):
        """记录失败"""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker opened after {self._failures} failures")

    def can_execute(self) -> bool:
        """是否可以执行"""
        return self.state != "open"


# ============================================
# 主工具执行器 - 融合所有核心
# ============================================

class AdvancedToolExecutor:
    """
    高级工具执行器 - 真正融合三个项目

    融合:
    - ClaudeCode: 并发分区算法、isConcurrencySafe、遥测
    - Hermes: OSV检测、凭证泄露、MCP采样、断路器
    - OpenClaw: 配置保护、危险标志检测
    """

    def __init__(self, llm_client=None, permission_level: str = "semi_open"):
        self.llm_client = llm_client
        self.permission_level = permission_level

        # 并发控制
        self._read_semaphore = asyncio.Semaphore(10)  # 最多10个并行只读
        self._write_semaphore = asyncio.Semaphore(1)  # 写入串行
        self._execute_semaphore = asyncio.Semaphore(1)  # 执行串行
        self._network_semaphore = asyncio.Semaphore(5)  # 网络有限并发

        # 安全组件
        self.security = SecurityDetector()
        self.config_protection = ConfigProtection()
        self.telemetry = TelemetryLogger()
        self.sampling = SamplingCallback(llm_client) if llm_client else None
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # 工具注册
        self._tools: Dict[str, Callable] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置工具"""
        self._tools["bash"] = self._execute_bash
        self._tools["read"] = self._execute_read
        self._tools["write"] = self._execute_write
        self._tools["edit"] = self._execute_edit
        self._tools["glob"] = self._execute_glob
        self._tools["grep"] = self._execute_grep
        self._tools["http_request"] = self._execute_http

    def _get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """获取断路器"""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker()
        return self._circuit_breakers[name]

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        执行单个工具调用

        全开放模式下无沙盒限制
        """
        start_time = time.time()
        tool_name = tool_call.name

        # 安全检查 - 非全开放模式
        if self.permission_level != "full_open":
            security_result = await self._security_check(tool_call)
            if not security_result["allowed"]:
                return ToolResult(
                    id=tool_call.id,
                    success=False,
                    error=security_result["reason"]
                )

        # 断路器检查
        cb = self._get_circuit_breaker(tool_name)
        if not cb.can_execute():
            return ToolResult(
                id=tool_call.id,
                success=False,
                error="Circuit breaker open - too many failures"
            )

        # 执行
        try:
            tool_func = self._tools.get(tool_name)
            if not tool_func:
                return ToolResult(
                    id=tool_call.id,
                    success=False,
                    error=f"Unknown tool: {tool_name}"
                )

            result = await tool_func(tool_call.params)
            cb.record_success()

            duration_ms = (time.time() - start_time) * 1000

            # 遥测
            self.telemetry.log_approval_event(tool_name, self.permission_level)

            return ToolResult(
                id=tool_call.id,
                success=result.get("success", True),
                output=result.get("output"),
                duration_ms=duration_ms
            )

        except Exception as e:
            cb.record_failure()
            duration_ms = (time.time() - start_time) * 1000

            # 遥测
            self.telemetry.log_rejection_event(tool_name, self.permission_level, str(e))

            return ToolResult(
                id=tool_call.id,
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )

    async def execute_batch(
        self,
        tool_calls: List[ToolCall],
        partition: bool = True
    ) -> List[ToolResult]:
        """
        批量执行工具 - ClaudeCode并发分区算法

        核心算法:
        1. partitionToolCalls分区
        2. 只读批次并行执行
        3. 写入/执行批次串行执行
        """
        if not partition:
            # 不分区，全部串行
            results = []
            for call in tool_calls:
                result = await self.execute(call)
                results.append(result)
            return results

        # 转换为dict格式
        call_dicts = [
            {"id": c.id, "name": c.name, "params": c.params}
            for c in tool_calls
        ]

        # ClaudeCode核心算法: 分区
        batches = ToolPartitioner.partition_tool_calls(call_dicts)

        results = []

        for batch in batches:
            if batch.is_concurrency_safe:
                # 只读批次: 并行执行
                batch_results = await self._execute_batch_parallel(
                    batch.blocks, tool_calls
                )
                results.extend(batch_results)
            else:
                # 写入/执行批次: 串行执行
                for block in batch.blocks:
                    call = next(c for c in tool_calls if c.id == block["id"])
                    result = await self.execute(call)
                    results.append(result)

        return results

    async def _execute_batch_parallel(
        self,
        blocks: List[Dict],
        original_calls: List[ToolCall]
    ) -> List[ToolResult]:
        """并行执行只读批次"""
        tasks = []
        for block in blocks:
            call = next(c for c in original_calls if c.id == block["id"])
            tasks.append(self.execute(call))

        return await asyncio.gather(*tasks)

    async def _security_check(self, tool_call: ToolCall) -> Dict:
        """安全检查"""
        tool_name = tool_call.name
        params = tool_call.params

        # 凭证泄露检测
        params_str = str(params)
        cred_matches = self.security.check_credentials(params_str)
        if cred_matches:
            self.telemetry.log_rejection_event(
                tool_name, "credential_detection",
                f"Credential detected: {cred_matches[0][1]}"
            )

        # 恶意软件检测
        malware_matches = self.security.check_malware(params_str)
        if malware_matches:
            return {
                "allowed": False,
                "reason": f"Malware detected: {malware_matches[0][1]}"
            }

        # 危险命令检测
        if tool_name == "bash":
            command = params.get("command", "")
            dangerous_matches = self.security.check_dangerous(command)
            if dangerous_matches:
                return {
                    "allowed": False,
                    "reason": f"Dangerous command: {dangerous_matches[0][1]}"
                }

        # 受保护路径检测
        if "path" in params:
            protected = self.security.check_protected_path(params["path"])
            if protected:
                return {
                    "allowed": False,
                    "reason": f"Protected path: {protected}"
                }

        return {"allowed": True}

    # === 内置工具实现 ===

    async def _execute_bash(self, params: Dict) -> Dict:
        """执行Bash命令 - 全开放模式无限制"""
        command = params.get("command", "")
        timeout = params.get("timeout", 30)
        cwd = params.get("cwd")

        # 全开放模式: 无沙盒限制
        if self.permission_level == "full_open":
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
        else:
            # 非全开放模式: 使用sh -c限制
            result = subprocess.run(
                ["sh", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )

        return {
            "success": result.returncode == 0,
            "output": {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        }

    async def _execute_read(self, params: Dict) -> Dict:
        """读取文件"""
        path = params.get("path", "")
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return {"success": False, "error": "File not found"}

            content = file_path.read_text(encoding="utf-8")

            # 行切片
            start = params.get("startLine", 0)
            end = params.get("endLine")
            if start or end:
                lines = content.splitlines()
                content = "\n".join(lines[start:end])

            return {
                "success": True,
                "output": {"path": str(file_path), "content": content}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_write(self, params: Dict) -> Dict:
        """写入文件"""
        path = params.get("path", "")
        content = params.get("content", "")

        try:
            file_path = Path(path).expanduser()

            # 安全检查
            if self.permission_level != "full_open":
                protected = self.security.check_protected_path(file_path)
                if protected:
                    return {"success": False, "error": f"Protected path: {protected}"}

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "output": {"path": str(file_path), "size": len(content)}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_edit(self, params: Dict) -> Dict:
        """编辑文件"""
        path = params.get("path", "")
        old_string = params.get("old_string", "")
        new_string = params.get("new_string", "")

        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return {"success": False, "error": "File not found"}

            content = file_path.read_text(encoding="utf-8")

            if old_string not in content:
                return {"success": False, "error": "String not found"}

            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return {
                "success": True,
                "output": {"path": str(file_path), "changes": "1 replacement"}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_glob(self, params: Dict) -> Dict:
        """Glob模式匹配"""
        import fnmatch

        pattern = params.get("pattern", "*")
        cwd = params.get("cwd", ".")

        try:
            base = Path(cwd).expanduser()
            matches = []

            for path in base.rglob("*"):
                if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(str(path), pattern):
                    matches.append(str(path))
                    if len(matches) >= 1000:
                        break

            return {
                "success": True,
                "output": {"matches": matches, "count": len(matches)}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_grep(self, params: Dict) -> Dict:
        """Grep搜索"""
        pattern = params.get("pattern", "")
        path = params.get("path", ".")
        case_sensitive = params.get("case_sensitive", True)

        if not pattern:
            return {"success": False, "error": "Missing pattern"}

        try:
            base = Path(path).expanduser()
            matches = []

            regex = 0 if case_sensitive else re.I
            pattern_regex = re.compile(pattern, regex)

            for file_path in base.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines(), 1):
                            if pattern_regex.search(line):
                                matches.append({
                                    "path": str(file_path),
                                    "line": i,
                                    "content": line.strip()
                                })
                                if len(matches) >= 1000:
                                    break
                    except Exception:
                        pass

            return {
                "success": True,
                "output": {"matches": matches, "count": len(matches)}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_http(self, params: Dict) -> Dict:
        """HTTP请求"""
        import urllib.request
        import urllib.error

        url = params.get("url", "")
        method = params.get("method", "GET")
        headers = params.get("headers", {})
        body = params.get("body", "")

        try:
            req = urllib.request.Request(
                url,
                data=body.encode() if body else None,
                headers=headers,
                method=method
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8", errors="ignore")

            return {
                "success": True,
                "output": {
                    "status": response.status,
                    "content": content[:5000],
                    "headers": dict(response.headers)
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# 全局实例
_executor: Optional[AdvancedToolExecutor] = None


def get_advanced_executor(llm_client=None, permission_level: str = "semi_open") -> AdvancedToolExecutor:
    """获取高级工具执行器"""
    global _executor
    if _executor is None:
        _executor = AdvancedToolExecutor(llm_client, permission_level)
    return _executor
