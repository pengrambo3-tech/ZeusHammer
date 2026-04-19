"""
ZeusHammer Permission Manager

权限管理系统 - 完整实现

支持:
1. 安装时配置权限级别
2. 运行时动态切换
3. Web UI权限控制
4. 命令行权限切换
5. 按操作细粒度控制
"""

import os
import re
import logging
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """权限级别"""
    SAFE = "safe"           # 全确认模式
    SEMI_OPEN = "semi_open" # 半开放模式 (默认)
    FULL_OPEN = "full_open" # 野兽模式

    def __str__(self):
        return self.value

    @property
    def description(self):
        descriptions = {
            "safe": "全确认模式 - 所有操作需要确认",
            "semi_open": "半开放模式 - 安全操作自动执行，危险操作需确认",
            "full_open": "野兽模式 - 无任何限制",
        }
        return descriptions.get(self.value, "")


class OperationCategory(Enum):
    """操作类别"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_EXECUTE = "file_execute"
    NETWORK_REQUEST = "network_request"
    SHELL_COMMAND = "shell_command"
    SYSTEM_CONFIG = "system_config"
    API_CALL = "api_call"
    DANGEROUS = "dangerous"


@dataclass
class OperationRule:
    """操作规则"""
    category: OperationCategory
    patterns: List[str]  # 匹配模式
    requires_confirmation: bool = True
    auto_allow: bool = False
    risk_level: str = "low"  # low, medium, high, critical
    description: str = ""


@dataclass
class PermissionRequest:
    """权限请求"""
    category: OperationCategory
    operation: str
    details: Dict[str, Any]
    risk_level: str = "low"
    warning: str = ""
    timestamp: float = 0


@dataclass
class PermissionResult:
    """权限结果"""
    allowed: bool
    reason: str = ""
    rule: str = ""


class SecurityDetector:
    """
    安全检测 - Hermes核心

    检测凭证、恶意软件、危险命令
    """

    # 凭证模式
    CREDENTIAL_PATTERNS = [
        (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT"),
        (r"github_pat_[A-Za-z0-9_]{22,}", "GitHub Fine-grained PAT"),
        (r"sk-[A-Za-z0-9]{48}", "OpenAI API Key"),
        (r"sk-proj-[A-Za-z0-9_-]{48,}", "OpenAI Project Key"),
        (r"sk-ant-[A-Za-z0-9_-]{48,}", "Anthropic API Key"),
        (r"AKIA[A-Za-z0-9]{16}", "AWS Access Key"),
        (r"A3T[A-Za-z0-9]{16}", "AWS Secret Key"),
        (r"xox[baprs]-[A-Za-z0-9]{10,}", "Slack Token"),
        (r"glpat-[A-Za-z0-9-_]{20}", "GitLab PAT"),
        (r"-----BEGIN.*PRIVATE KEY-----", "Private Key"),
        (r"-----BEGIN OPENSSH PRIVATE KEY-----", "SSH Key"),
    ]

    # 恶意软件模式
    MALWARE_PATTERNS = [
        (r":\(\)\{\s*:\|:\s*\}", "Fork Bomb"),
        (r"fork\s+bomb", "Fork Bomb"),
        (r"curl\s+.*\|\s*(?:sh|bash|python)", "Pipe to Shell"),
        (r"wget\s+.*\|\s*(?:sh|bash|python)", "Pipe to Shell"),
        (r"base64\s+-d\s+.*\|\s*(?:sh|bash)", "Encoded Shell"),
    ]

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        (r"rm\s+-rf\s+/(?:home|root|etc|var|usr)", "Delete System Dirs"),
        (r"rm\s+-rf\s+/", "Recursive Root Delete"),
        (r"chmod\s+777\s+/(?:etc|root|var|usr)", "777 Sensitive Dirs"),
        (r">\s*/etc/passwd", "Overwrite Passwd"),
        (r">\s*/etc/shadow", "Overwrite Shadow"),
        (r"dd\s+if=.*of=/dev/(?:sd|hd|nvme)", "Direct Disk Write"),
        (r"mkfs\.", "Format Filesystem"),
        (r"eval\s*\(\s*\$", "Eval Injection"),
        (r";\s*rm\s+-rf", "Command Injection"),
        (r"&&\s*rm\s+-rf", "Command Injection"),
    ]

    # 受保护路径
    PROTECTED_PATHS_MACOS = [
        "/System",
        "/Applications/Carbon",
        "/Applications/Finder.app",
        "/Library/Application Support/com.apple.TCC",
        "/usr/bin/chmod",
        "/usr/bin/chown",
        "/usr/sbin/systemsetup",
        "/etc/sudoers",
    ]

    PROTECTED_PATHS_LINUX = [
        "/etc/sudoers",
        "/etc/passwd",
        "/etc/shadow",
        "/etc/group",
        "/root",
        "/boot",
    ]

    PROTECTED_PATHS_WINDOWS = [
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
        "C:\\Program Files",
    ]

    @classmethod
    def check_credentials(cls, text: str) -> List[tuple]:
        """检测凭证"""
        found = []
        for pattern, desc in cls.CREDENTIAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append((pattern, desc))
        return found

    @classmethod
    def check_malware(cls, text: str) -> List[tuple]:
        """检测恶意软件"""
        found = []
        for pattern, desc in cls.MALWARE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append((pattern, desc))
        return found

    @classmethod
    def check_dangerous(cls, text: str) -> List[tuple]:
        """检测危险命令"""
        found = []
        for pattern, desc in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                found.append((pattern, desc))
        return found

    @classmethod
    def check_protected_path(cls, path: str) -> Optional[str]:
        """检查受保护路径"""
        import platform
        system = platform.system()

        if system == "Darwin":
            protected = cls.PROTECTED_PATHS_MACOS
        elif system == "Linux":
            protected = cls.PROTECTED_PATHS_LINUX
        else:
            protected = cls.PROTECTED_PATHS_WINDOWS

        resolved = str(Path(path).resolve())
        for p in protected:
            if resolved.startswith(p):
                return p
        return None

    @classmethod
    def detect_risk(cls, operation: str, details: Dict = None) -> tuple:
        """
        检测风险

        Returns:
            (risk_level, warning_message)
        """
        text = operation + " " + str(details or {})

        # 检查凭证
        cred = cls.check_credentials(text)
        if cred:
            return ("high", f"凭证泄露风险: {cred[0][1]}")

        # 检查恶意软件
        malware = cls.check_malware(text)
        if malware:
            return ("critical", f"恶意软件检测: {malware[0][1]}")

        # 检查危险命令
        dangerous = cls.check_dangerous(text)
        if dangerous:
            return ("critical", f"危险命令: {dangerous[0][1]}")

        # 检查受保护路径
        if details and "path" in details:
            protected = cls.check_protected_path(details["path"])
            if protected:
                return ("high", f"受保护路径: {protected}")

        return ("low", "")

    @classmethod
    def sanitize(cls, text: str) -> str:
        """清理凭证"""
        result = text
        for pattern, _ in cls.CREDENTIAL_PATTERNS:
            if "ghp_" in pattern:
                result = re.sub(r"(ghp_[A-Za-z0-9]{6})[A-Za-z0-9]{30}", r"\g<1>...[REDACTED]", result)
            elif "sk-" in pattern:
                result = re.sub(r"(sk-)[A-Za-z0-9]{40}", r"\g<1>..." + "[REDACTED]" * 4, result)
            elif "AKIA" in pattern:
                result = re.sub(r"(AKIA)[A-Za-z0-9]{16}", r"\g<1>...[REDACTED]", result)
        return result


class PermissionManager:
    """
    权限管理器 - 完整实现

    支持:
    - 三种权限级别
    - 运行时动态切换
    - 操作规则配置
    - 历史记录
    - Web UI集成
    """

    def __init__(self, level: PermissionLevel = PermissionLevel.SEMI_OPEN):
        self.level = level
        self._security = SecurityDetector()

        # 操作规则
        self._rules: Dict[OperationCategory, OperationRule] = {}
        self._init_default_rules()

        # 历史记录
        self._history: List[PermissionRequest] = []

        # 回调
        self._on_require_confirmation: Optional[Callable] = None
        self._on_permission_change: Optional[Callable] = None

        # 从环境变量加载
        self._load_from_env()

    def _init_default_rules(self):
        """初始化默认规则"""
        self._rules = {
            OperationCategory.FILE_READ: OperationRule(
                category=OperationCategory.FILE_READ,
                patterns=["read", "cat", "open", "view"],
                auto_allow=True,
                risk_level="low",
                description="文件读取"
            ),
            OperationCategory.FILE_WRITE: OperationRule(
                category=OperationCategory.FILE_WRITE,
                patterns=["write", "create", "edit"],
                auto_allow=False,
                risk_level="medium",
                description="文件写入"
            ),
            OperationCategory.FILE_DELETE: OperationRule(
                category=OperationCategory.FILE_DELETE,
                patterns=["delete", "remove", "rm"],
                auto_allow=False,
                risk_level="high",
                description="文件删除"
            ),
            OperationCategory.SHELL_COMMAND: OperationRule(
                category=OperationCategory.SHELL_COMMAND,
                patterns=["exec", "run", "bash", "shell", "command"],
                auto_allow=False,
                risk_level="medium",
                description="Shell命令执行"
            ),
            OperationCategory.NETWORK_REQUEST: OperationRule(
                category=OperationCategory.NETWORK_REQUEST,
                patterns=["http", "fetch", "request", "curl", "wget"],
                auto_allow=True,
                risk_level="low",
                description="网络请求"
            ),
            OperationCategory.DANGEROUS: OperationRule(
                category=OperationCategory.DANGEROUS,
                patterns=["dangerous", "critical"],
                requires_confirmation=True,
                risk_level="critical",
                description="危险操作"
            ),
        }

    def _load_from_env(self):
        """从环境变量加载"""
        level_str = os.environ.get("ZUESHAMMER_PERMISSION", "")
        if level_str:
            try:
                self.level = PermissionLevel(level_str)
                logger.info(f"权限级别从环境变量加载: {self.level.value}")
            except ValueError:
                pass

    def set_level(self, level: PermissionLevel):
        """设置权限级别"""
        old_level = self.level
        self.level = level

        logger.info(f"权限级别切换: {old_level.value} -> {level.value}")

        # 调用回调
        if self._on_permission_change:
            self._on_permission_change(old_level, level)

    def is_full_open(self) -> bool:
        """是否为野兽模式"""
        return self.level == PermissionLevel.FULL_OPEN

    def is_safe(self) -> bool:
        """是否为安全模式"""
        return self.level == PermissionLevel.SAFE

    def check(
        self,
        operation: str,
        details: Dict[str, Any] = None
    ) -> PermissionResult:
        """
        检查操作权限

        Returns:
            PermissionResult
        """
        details = details or {}

        # 野兽模式: 无限制
        if self.is_full_open():
            return PermissionResult(
                allowed=True,
                reason="野兽模式 - 无限制",
                rule="full_open"
            )

        # 分析操作
        category = self._categorize(operation)
        risk_level, warning = SecurityDetector.detect_risk(operation, details)

        # 创建请求记录
        request = PermissionRequest(
            category=category,
            operation=operation,
            details=details,
            risk_level=risk_level,
            warning=warning,
        )
        self._history.append(request)

        # 安全模式: 所有操作都需要确认
        if self.is_safe():
            return PermissionResult(
                allowed=False,
                reason=f"安全模式: 需要确认 - {warning or category.value}",
                rule="safe_mode"
            )

        # 半开放模式
        # 关键/高风险: 拒绝
        if risk_level in ("critical", "high"):
            return PermissionResult(
                allowed=False,
                reason=f"安全风险: {warning}",
                rule="security_block"
            )

        # 检查规则
        rule = self._rules.get(category)
        if rule and rule.auto_allow:
            return PermissionResult(
                allowed=True,
                reason=f"自动允许: {category.value}",
                rule=f"auto_allow_{category.value}"
            )

        # 中等风险或需要确认的操作
        return PermissionResult(
            allowed=False,
            reason=f"需要确认: {category.value} - {warning}",
            rule="requires_confirmation"
        )

    def _categorize(self, operation: str) -> OperationCategory:
        """分类操作"""
        op = operation.lower()

        if any(p in op for p in ["read", "cat", "open", "view", "get"]):
            return OperationCategory.FILE_READ
        if any(p in op for p in ["write", "create", "edit", "save"]):
            return OperationCategory.FILE_WRITE
        if any(p in op for p in ["delete", "remove", "rm", "unlink"]):
            return OperationCategory.FILE_DELETE
        if any(p in op for p in ["exec", "run", "bash", "shell", "command"]):
            return OperationCategory.SHELL_COMMAND
        if any(p in op for p in ["http", "fetch", "request", "curl", "wget"]):
            return OperationCategory.NETWORK_REQUEST
        if any(p in op for p in ["config", "setting", "system"]):
            return OperationCategory.SYSTEM_CONFIG

        return OperationCategory.DANGEROUS

    def confirm(self, request: PermissionRequest) -> bool:
        """
        用户确认操作

        由UI或CLI调用
        """
        # 从历史中移除最后一个请求
        if self._history and self._history[-1] == request:
            self._history.pop()

        # 这里简化处理，实际应该由调用方处理
        return True

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "level": self.level.value,
            "level_description": self.level.description,
            "is_full_open": self.is_full_open(),
            "is_safe": self.is_safe(),
            "history_count": len(self._history),
            "rules_count": len(self._rules),
        }

    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取历史"""
        return [
            {
                "category": r.category.value,
                "operation": r.operation,
                "risk_level": r.risk_level,
                "warning": r.warning,
                "timestamp": r.timestamp,
            }
            for r in self._history[-limit:]
        ]

    def set_confirmation_callback(self, callback: Callable):
        """设置确认回调"""
        self._on_require_confirmation = callback

    def set_permission_change_callback(self, callback: Callable):
        """设置权限变更回调"""
        self._on_permission_change = callback

    # ============ 运行时切换接口 ============

    def switch_to_safe(self):
        """切换到安全模式"""
        self.set_level(PermissionLevel.SAFE)

    def switch_to_semi_open(self):
        """切换到半开放模式"""
        self.set_level(PermissionLevel.SEMI_OPEN)

    def switch_to_full_open(self):
        """切换到野兽模式"""
        logger.warning("⚠️ 切换到野兽模式 - 所有操作无限制！")
        self.set_level(PermissionLevel.FULL_OPEN)

    def switch_level(self, level: str) -> bool:
        """
        切换权限级别

        Args:
            level: safe, semi_open, full_open

        Returns:
            是否成功
        """
        try:
            self.set_level(PermissionLevel(level))
            return True
        except ValueError:
            return False


# 全局实例
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager(level: PermissionLevel = None) -> PermissionManager:
    """获取权限管理器"""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(level or PermissionLevel.SEMI_OPEN)
    return _permission_manager


def is_beast_mode() -> bool:
    """是否为野兽模式"""
    return get_permission_manager().is_full_open()


def disable_sandbox():
    """禁用沙盒 - 野兽模式快捷方式"""
    get_permission_manager().switch_to_full_open()
