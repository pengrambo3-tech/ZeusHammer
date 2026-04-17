"""
Hermes Fusion Module - 核心系统

融合 Hermes Agent 核心功能:
- OSV 恶意软件检测
- MCP 完整协议栈
- 断路器模式
- 工具注册表
- 记忆系统
"""

import asyncio
import logging
import hashlib
import time
import re
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict

logger = logging.getLogger(__name__)


# ============================================================
# 断路器模式 (Circuit Breaker)
# Hermes 核心安全机制
# ============================================================

class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"      # 正常，熔丝闭合
    OPEN = "open"          # 断开，请求直接失败
    HALF_OPEN = "half_open"  # 半开，允许一个测试请求


@dataclass
class CircuitBreaker:
    """
    断路器
    
    Hermes 核心算法：当异常超过阈值时断开电路，防止雪崩
    """
    name: str
    failure_threshold: int = 5        # 失败次数阈值
    recovery_timeout: float = 60.0   # 恢复超时（秒）
    half_open_max_calls: int = 3      # 半开状态允许的调用数

    _state: CircuitState = field(default=CircuitState.CLOSED)
    _failure_count: int = field(default=0)
    _last_failure_time: float = field(default=0)
    _half_open_calls: int = field(default=0)

    def __post_init__(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            # 检查是否应该进入半开状态
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        current_state = self.state

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls

        return False  # OPEN 状态

    def record_success(self):
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                # 所有测试请求都成功，恢复正常
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"Circuit {self.name} recovered")
        else:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name} opened after {self._failure_count} failures")

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """使用断路器执行函数"""
        if not self.can_execute():
            raise Exception(f"Circuit {self.name} is open")

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self.record_success()
            return result

        except Exception as e:
            self.record_failure()
            raise


# ============================================================
# 工具注册表 (Tool Registry)
# Hermes 核心工具管理
# ============================================================

@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str
    parameters: Dict[str, Any]
    danger_level: int = 0  # 0-10, 越高越危险
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


class ToolRegistry:
    """
    工具注册表
    
    Hermes 核心：统一管理所有可用工具
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._tools: Dict[str, Callable] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._dangerous_patterns: List[str] = [
            r"rm\s+-rf",
            r"drop\s+database",
            r"format\s+disk",
            r"del\s+/f\s+/s",
        ]

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        danger_level: int = 0,
        category: str = "general",
        **kwargs
    ):
        """注册工具"""
        self._tools[name] = handler
        self._metadata[name] = ToolMetadata(
            name=name,
            description=description,
            parameters=kwargs.get("parameters", {}),
            danger_level=danger_level,
            category=category,
            tags=kwargs.get("tags", []),
            examples=kwargs.get("examples", [])
        )
        logger.info(f"Registered tool: {name} (danger={danger_level})")

    def get(self, name: str) -> Optional[Callable]:
        """获取工具"""
        return self._tools.get(name)

    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._metadata.get(name)

    def list_tools(self, category: str = None) -> List[str]:
        """列出工具"""
        if category:
            return [
                name for name, meta in self._metadata.items()
                if meta.category == category
            ]
        return list(self._tools.keys())

    def is_dangerous(self, name: str) -> bool:
        """检查工具是否危险"""
        meta = self._metadata.get(name)
        if meta:
            return meta.danger_level >= 7
        return False

    def check_command_safety(self, command: str) -> tuple:
        """
        检查命令安全性
        
        Hermes 安全机制：检测危险命令
        """
        for pattern in self._dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"

        return True, "safe"


# ============================================================
# OSV 恶意软件检测 (OSV Scanner)
# Hermes 安全机制
# ============================================================

class OSVScanner:
    """
    OSV 恶意软件检测器
    
    Hermes 核心：检测已知的恶意软件模式和漏洞
    """

    # 已知恶意模式
    MALWARE_PATTERNS = {
        "reverse_shell": [
            r"bash\s+-i",
            r"/dev/tcp/",
            r"nc\s+-e",
            r"rm\s+/tmp/f",
            r"python.*-c.*socket",
        ],
        "data_exfiltration": [
            r"curl.*--data",
            r"wget.*-O-.*\|.*bash",
            r"base64.*\|.*nc",
        ],
        "privilege_escalation": [
            r"sudo\s+su",
            r"chmod\s+4777",
            r"chmod\s+666",
        ],
        "cryptominer": [
            r"xmrig",
            r"minerd",
            r"stratum\+tcp://",
        ]
    }

    # 危险文件路径
    DANGEROUS_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "/root/.ssh",
        "~/.ssh/id_rsa",
        "/System",
        "/Applications/Carbon",
    ]

    def scan_command(self, command: str) -> Dict[str, Any]:
        """
        扫描命令安全性
        
        Returns:
            {"safe": bool, "reason": str, "category": str}
        """
        command_lower = command.lower()

        for category, patterns in self.MALWARE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return {
                        "safe": False,
                        "reason": f"Malware pattern detected: {category}",
                        "category": category,
                        "pattern": pattern
                    }

        return {"safe": True, "reason": "clean", "category": "none"}

    def scan_path(self, path: str) -> Dict[str, Any]:
        """扫描路径安全性"""
        for dangerous in self.DANGEROUS_PATHS:
            if dangerous in path:
                return {
                    "safe": False,
                    "reason": f"Protected path: {dangerous}",
                    "path": path
                }

        return {"safe": True, "reason": "path safe"}

    def scan_file_content(self, content: str) -> Dict[str, Any]:
        """扫描文件内容"""
        suspicious_patterns = []

        # 检查 base64 混淆
        if len(content) > 1000:
            b64_count = len(re.findall(r'[A-Za-z0-9+/]{50,}={0,2}', content))
            if b64_count > 5:
                suspicious_patterns.append("Excessive base64 encoded content")

        # 检查可疑的 exec/eval
        if re.search(r'(eval|exec|compile)\s*\(', content):
            suspicious_patterns.append("Dynamic code execution detected")

        if suspicious_patterns:
            return {
                "safe": False,
                "patterns": suspicious_patterns
            }

        return {"safe": True}


# ============================================================
# 凭证泄露检测 (Credential Guard)
# Hermes 安全机制
# ============================================================

class CredentialGuard:
    """
    凭证泄露检测器
    
    Hermes 核心：检测代码中的敏感凭证
    """

    CREDENTIAL_PATTERNS = {
        "api_key": [
            (r'api[_-]?key["\']?\s*[:=]\s*["\'][A-Za-z0-9_-]{20,}', "API Key"),
            (r'OPENAI_API_KEY\s*=\s*["\'][A-Za-z0-9_-]{20,}', "OpenAI Key"),
            (r'ANTHROPIC_API_KEY\s*=\s*["\'][A-Za-z0-9_-]{20,}', "Anthropic Key"),
            (r'GITHUB_TOKEN\s*=\s*["\'][A-Za-z0-9_-]{20,}', "GitHub Token"),
        ],
        "private_key": [
            (r'-----BEGIN\s+(RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----', "Private Key"),
        ],
        "password": [
            (r'password["\']?\s*[:=]\s*["\'][^"\']{8,}', "Password"),
            (r'passwd["\']?\s*[:=]\s*["\'][^"\']{8,}', "Password"),
        ],
        "connection_string": [
            (r'mongodb://[^@]+@', "MongoDB Connection"),
            (r'mysql://[^@]+@', "MySQL Connection"),
            (r'postgres://[^@]+@', "PostgreSQL Connection"),
        ]
    }

    def scan(self, content: str) -> List[Dict[str, str]]:
        """
        扫描凭证泄露
        
        Returns:
            发现的凭证列表
        """
        findings = []

        for category, patterns in self.CREDENTIAL_PATTERNS.items():
            for pattern, label in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # 遮蔽敏感部分
                    matched = match.group()
                    if len(matched) > 15:
                        masked = matched[:8] + "..." + matched[-4:]
                    else:
                        masked = "***"

                    findings.append({
                        "category": category,
                        "label": label,
                        "line": content[:match.start()].count('\n') + 1,
                        "matched": masked,
                        "recommendation": f"Remove or use environment variable for {label}"
                    })

        return findings

    def mask_credentials(self, content: str) -> str:
        """遮蔽凭证"""
        result = content

        for category, patterns in self.CREDENTIAL_PATTERNS.items():
            for pattern, label in patterns:
                result = re.sub(pattern, f'[{label} MASKED]', result, flags=re.IGNORECASE)

        return result


# ============================================================
# 工具权限控制 (Tool Permissions)
# Hermes 安全机制
# ============================================================

class ToolPermissions:
    """
    工具权限控制
    
    Hermes 核心：基于权限级别控制工具访问
    """

    SAFE_LEVEL = "safe"         # 所有操作需确认
    SEMI_OPEN = "semi_open"     # 安全操作自动执行
    FULL_OPEN = "full_open"     # 无限制

    # 危险工具列表（按风险等级）
    DANGEROUS_TOOLS = {
        10: ["format_disk", "drop_database", "delete_system"],
        9: ["write_ssh_key", "modify_passwd", "add_sudo"],
        8: ["delete_file", "rm_recursive", "kill_process"],
        7: ["execute_shell", "run_command", "bash"],
        6: ["write_file", "edit_config", "modify_hosts"],
    }

    def __init__(self, level: str = SAFE_LEVEL):
        self.level = level

    def can_execute(self, tool_name: str) -> tuple:
        """
        检查是否可以执行工具
        
        Returns:
            (allowed: bool, reason: str)
        """
        if self.level == self.FULL_OPEN:
            return True, "full_open mode"

        danger_level = self._get_tool_danger_level(tool_name)

        if self.level == self.SAFE_LEVEL:
            if danger_level >= 5:
                return False, f"Tool {tool_name} requires explicit confirmation (danger={danger_level})"
            return True, "safe"

        elif self.level == self.SEMI_OPEN:
            if danger_level >= 7:
                return False, f"Tool {tool_name} is too dangerous for semi_open mode"
            return True, "semi_open allowed"

        return False, "Unknown permission level"

    def _get_tool_danger_level(self, tool_name: str) -> int:
        """获取工具危险等级"""
        tool_lower = tool_name.lower()

        for level, tools in self.DANGEROUS_TOOLS.items():
            for tool in tools:
                if tool in tool_lower:
                    return level

        return 0  # 默认安全


# ============================================================
# MCP 协议客户端 (MCP Client)
# Hermes 核心功能
# ============================================================

@dataclass
class MCPMessage:
    """MCP 消息"""
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict] = None
    result: Optional[Any] = None
    error: Optional[Dict] = None


class MCPClient:
    """
    MCP (Model Context Protocol) 客户端
    
    Hermes 核心：与 MCP 服务器通信
    """

    def __init__(self, server_url: str, timeout: int = 30):
        self.server_url = server_url
        self.timeout = timeout
        self._tools: Dict[str, Dict] = {}
        self._connected = False

    async def connect(self) -> bool:
        """连接到 MCP 服务器"""
        try:
            # 初始化连接
            init_result = await self._send_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    },
                    "clientInfo": {
                        "name": "ZuesHammer",
                        "version": "2.0.0"
                    }
                }
            )

            if init_result:
                self._connected = True
                await self._discover_tools()
                return True

        except Exception as e:
            logger.error(f"MCP connection failed: {e}")

        return False

    async def _discover_tools(self):
        """发现可用工具"""
        try:
            result = await self._send_request("tools/list")
            if result and "tools" in result:
                for tool in result["tools"]:
                    self._tools[tool["name"]] = tool
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")

    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用 MCP 工具"""
        if not self._connected:
            return {"error": "Not connected"}

        try:
            result = await self._send_request(
                "tools/call",
                {
                    "name": name,
                    "arguments": arguments
                }
            )
            return result

        except Exception as e:
            return {"error": str(e)}

    async def _send_request(
        self,
        method: str,
        params: Dict = None
    ) -> Optional[Dict]:
        """发送请求"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.server_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": method,
                        "params": params or {},
                        "id": hashlib.md5(f"{method}{time.time()}".encode()).hexdigest()[:8]
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if "result" in result:
                        return result["result"]
                    elif "error" in result:
                        raise Exception(result["error"])

        except Exception as e:
            logger.error(f"MCP request failed: {e}")
            raise

        return None

    def list_tools(self) -> List[Dict]:
        """列出可用工具"""
        return list(self._tools.values())

    async def disconnect(self):
        """断开连接"""
        self._connected = False
        self._tools.clear()


# 全局实例
_tool_registry: Optional[ToolRegistry] = None
_osv_scanner: Optional[OSVScanner] = None
_credential_guard: Optional[CredentialGuard] = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def get_osv_scanner() -> OSVScanner:
    """获取 OSV 扫描器"""
    global _osv_scanner
    if _osv_scanner is None:
        _osv_scanner = OSVScanner()
    return _osv_scanner


def get_credential_guard() -> CredentialGuard:
    """获取凭证保护器"""
    global _credential_guard
    if _credential_guard is None:
        _credential_guard = CredentialGuard()
    return _credential_guard
