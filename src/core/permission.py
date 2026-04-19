"""
ZeusHammer Permission System

Three permission levels:
1. SAFE - Full confirmation required (beginner friendly)
2. SEMI_OPEN - Warning for security issues, approval needed (intermediate)
3. FULL_OPEN - No restrictions, beast mode (expert)

真正融合:
- ClaudeCode: Permission hooks, confirmation prompts, telemetry
- Hermes: Security detection, credential exposure, OSV checking
- OpenClaw: Protected paths, security flags, dangerous patterns
"""

import os
import re
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Permission levels for ZeusHammer"""
    SAFE = "safe"           # Full confirmation required
    SEMI_OPEN = "semi_open" # Warning + approval for security
    FULL_OPEN = "full_open" # No restrictions, beast mode


class PermissionCategory(Enum):
    """Categories of operations requiring permission"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_EXECUTE = "file_execute"
    NETWORK_REQUEST = "network_request"
    WEB_ACCESS = "web_access"
    SHELL_COMMAND = "shell_command"
    SYSTEM_CONFIG = "system_config"
    ENV_MODIFY = "env_modify"
    API_CALL = "api_call"
    WEBHOOK = "webhook"
    DANGEROUS = "dangerous"


@dataclass
class PermissionRequest:
    """Permission request details"""
    category: PermissionCategory
    operation: str
    details: Dict[str, Any]
    risk_level: str = "low"
    warning_message: str = ""


@dataclass
class PermissionResult:
    """Permission decision"""
    granted: bool
    reason: str = ""
    skip_future: bool = False


# ============================================
# Hermes核心: 安全检测模式
# ============================================

class SecurityPatterns:
    """
    Hermes实现: 安全检测模式

    凭证泄露、恶意软件、危险命令检测
    """

    # 凭证模式
    CREDENTIAL_PATTERNS = [
        (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT"),
        (r"sk-[A-Za-z0-9]{48}", "OpenAI Key"),
        (r"sk-proj-[A-Za-z0-9_-]{48,}", "OpenAI Project Key"),
        (r"AKIA[A-Za-z0-9]{16}", "AWS Access Key"),
        (r"A3T[A-Za-z0-9]{16}", "AWS Secret Key"),
        (r"xox[baprs]-[A-Za-z0-9]{10,}", "Slack Token"),
        (r"glpat-[A-Za-z0-9-_]{20}", "GitLab PAT"),
        (r"-----BEGIN.*PRIVATE KEY-----", "Private Key"),
    ]

    # 恶意软件模式
    MALWARE_PATTERNS = [
        (r":\(\)\{\s*:\|:\&\}\$;:", "Fork bomb"),
        (r"curl\s+.*\|.*sh", "Pipe to shell"),
        (r"wget\s+.*\|.*sh", "Pipe to shell"),
        (r"base64\s+-d.*\|.*sh", "Encoded shell"),
    ]

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        (r"rm\s+-rf\s+/(?:home|root|etc|var|usr)", "Delete system dirs"),
        (r"rm\s+-rf\s+/", "Recursive root delete"),
        (r"chmod\s+777\s+/(?:etc|root|var)", "777 sensitive dirs"),
        (r">\s*/etc/passwd", "Overwrite passwd"),
        (r">\s*/etc/shadow", "Overwrite shadow"),
        (r"dd\s+if=.*of=/dev/", "Direct disk write"),
        (r"mkfs\.", "Format filesystem"),
        (r":\(\)\s*\{\s*:\|:\s*&\s*\}", "Fork bomb"),
        (r"eval\s*\(\s*\$", "Eval injection"),
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
        from pathlib import Path
        resolved = str(Path(path).resolve())
        for protected in cls.PROTECTED_PATHS:
            if resolved.startswith(protected):
                return protected
        return None

    @classmethod
    def sanitize(cls, text: str) -> str:
        """清理凭证"""
        result = text
        result = re.sub(r"(ghp_[A-Za-z0-9]{6})[A-Za-z0-9]{30}", r"\g<1>...[REDACTED]", result)
        result = re.sub(r"(sk-)[A-Za-z0-9]{40}", r"\g<1>..." + "[REDACTED]" * 4, result)
        result = re.sub(r"(AKIA)[A-Za-z0-9]{16}", r"\g<1>...[REDACTED]", result)
        return result


# ============================================
# 权限检查器
# ============================================

class PermissionChecker:
    """
    权限检查器 - 全开放模式无沙盒限制
    """

    def __init__(self, level: PermissionLevel = PermissionLevel.SEMI_OPEN):
        self.level = level
        self._security = SecurityPatterns()

    def set_level(self, level: PermissionLevel):
        """设置权限级别"""
        self.level = level
        logger.info(f"Permission level: {level.value}")

    def is_full_open(self) -> bool:
        """是否为全开放模式"""
        return self.level == PermissionLevel.FULL_OPEN

    def check_operation(
        self,
        operation: str,
        details: Dict[str, Any] = None
    ) -> PermissionResult:
        """
        检查操作权限

        全开放模式: 完全无限制
        其他模式: 安全检查
        """
        # 全开放模式: 无沙盒限制
        if self.is_full_open():
            return PermissionResult(
                granted=True,
                reason="FULL_OPEN - No restrictions (beast mode)"
            )

        details = details or {}

        # 分析风险
        request = self._analyze_operation(operation, details)

        # SAFE模式: 始终需要确认
        if self.level == PermissionLevel.SAFE:
            return PermissionResult(
                granted=False,
                reason=f"SAFE mode: {request.warning_message or 'Confirmation required'}"
            )

        # SEMI_OPEN: 检查安全问题
        if request.risk_level in ("high", "critical"):
            return PermissionResult(
                granted=False,
                reason=f"Security warning: {request.warning_message}"
            )

        # 中等风险: 警告但允许
        if request.risk_level == "medium":
            logger.warning(f"Security: {request.warning_message}")

        return PermissionResult(granted=True, reason="Allowed")

    def _analyze_operation(self, operation: str, details: Dict[str, Any]) -> PermissionRequest:
        """分析操作风险"""
        category = self._get_category(operation)
        risk_level = "low"
        warning = ""

        # 凭证泄露检测
        operation_str = str(operation) + str(details)
        cred_matches = self._security.check_credentials(operation_str)
        if cred_matches:
            risk_level = "high"
            warning = f"Credential detected: {cred_matches[0][1]}"

        # 恶意软件检测
        malware_matches = self._security.check_malware(operation_str)
        if malware_matches:
            risk_level = "critical"
            warning = f"Malware detected: {malware_matches[0][1]}"

        # 危险命令检测
        dangerous_matches = self._security.check_dangerous(operation_str)
        if dangerous_matches:
            risk_level = max(risk_level, "critical")
            warning = f"Dangerous command: {dangerous_matches[0][1]}"

        # 受保护路径检测
        path = details.get("path", "")
        if path:
            protected = self._security.check_protected_path(path)
            if protected:
                risk_level = max(risk_level, "high")
                warning = f"Protected path: {protected}"

        # 写入操作
        if category == PermissionCategory.FILE_WRITE:
            if any(ext in path.lower() for ext in [".sh", ".bash", ".zsh"]):
                risk_level = max(risk_level, "medium")

        # Shell命令
        if category == PermissionCategory.SHELL_COMMAND:
            risk_level = max(risk_level, "medium")

        return PermissionRequest(
            category=category,
            operation=operation,
            details=details,
            risk_level=risk_level,
            warning_message=warning or self._default_warning(category)
        )

    def _get_category(self, operation: str) -> PermissionCategory:
        """分类操作"""
        op_lower = operation.lower()

        if "read" in op_lower or "cat" in op_lower or "open" in op_lower:
            return PermissionCategory.FILE_READ
        if "write" in op_lower or "edit" in op_lower or "create" in op_lower:
            return PermissionCategory.FILE_WRITE
        if "delete" in op_lower or "remove" in op_lower or "rm" in op_lower:
            return PermissionCategory.FILE_DELETE
        if "exec" in op_lower or "run" in op_lower or "bash" in op_lower or "shell" in op_lower:
            return PermissionCategory.SHELL_COMMAND
        if "http" in op_lower or "fetch" in op_lower or "request" in op_lower:
            return PermissionCategory.NETWORK_REQUEST
        if "config" in op_lower or "setting" in op_lower:
            return PermissionCategory.SYSTEM_CONFIG

        return PermissionCategory.DANGEROUS

    def _default_warning(self, category: PermissionCategory) -> str:
        """类别默认警告"""
        warnings = {
            PermissionCategory.FILE_READ: "File read operation",
            PermissionCategory.FILE_WRITE: "File write operation",
            PermissionCategory.FILE_DELETE: "File delete operation",
            PermissionCategory.SHELL_COMMAND: "Shell command execution",
            PermissionCategory.NETWORK_REQUEST: "Network request",
            PermissionCategory.SYSTEM_CONFIG: "System configuration change",
            PermissionCategory.DANGEROUS: "Potentially dangerous operation",
        }
        return warnings.get(category, "Unknown operation")


# ============================================
# 权限管理器
# ============================================

class PermissionManager:
    """
    全局权限管理器
    """

    def __init__(self, level: PermissionLevel = PermissionLevel.SEMI_OPEN):
        self.checker = PermissionChecker(level)
        self._history: List[PermissionRequest] = []

    def set_level(self, level: PermissionLevel):
        """设置权限级别"""
        self.checker.set_level(level)

    def is_full_open(self) -> bool:
        """是否为全开放模式"""
        return self.checker.is_full_open()

    def check(
        self,
        operation: str,
        details: Dict[str, Any] = None
    ) -> PermissionResult:
        """检查操作权限"""
        result = self.checker.check_operation(operation, details)

        if result.granted:
            request = self.checker._analyze_operation(operation, details or {})
            self._history.append(request)

        return result

    def ask_confirmation(self, message: str) -> bool:
        """请求用户确认"""
        print(f"\n⚠️  {message}")
        print("Allow? [y/N]: ", end="", flush=True)

        try:
            response = input().strip().lower()
            return response in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False

    def get_history(self, category: PermissionCategory = None) -> List[PermissionRequest]:
        """获取历史"""
        if category:
            return [r for r in self._history if r.category == category]
        return self._history


# 全局实例
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    """获取权限管理器"""
    global _permission_manager
    if _permission_manager is None:
        level_str = os.environ.get("ZUESHAMMER_PERMISSION", "semi_open")
        try:
            level = PermissionLevel(level_str)
        except ValueError:
            level = PermissionLevel.SEMI_OPEN

        _permission_manager = PermissionManager(level)

    return _permission_manager


# ============================================
# 工具执行器装饰器
# ============================================

def require_permission(category: PermissionCategory):
    """需要权限的装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            pm = get_permission_manager()

            # 全开放模式: 直接执行
            if pm.is_full_open():
                return func(*args, **kwargs)

            operation = f"{func.__module__}.{func.__name__}"
            result = pm.check(operation, {"category": category.value})

            if not result.granted:
                raise PermissionError(f"Permission denied: {result.reason}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================
# 权限级别辅助函数
# ============================================

def is_beast_mode() -> bool:
    """检查是否为野兽模式"""
    return get_permission_manager().is_full_open()


def disable_sandbox():
    """禁用沙盒 - 全开放模式快捷方式"""
    pm = get_permission_manager()
    pm.set_level(PermissionLevel.FULL_OPEN)
    logger.warning("Sandbox DISABLED - FULL_OPEN BEAST MODE")
