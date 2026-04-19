"""
ZeusHammer Configuration Protection System

真正融合OpenClaw的配置保护机制:

1. 受保护配置路径 - 不能被修改
2. 危险标志检测 - 不能被启用
3. baseHash并发控制 - 防止并发覆盖
4. Payload钩子 - 请求可观测性
"""

import hashlib
import time
import re
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum


class ConfigChangeType(Enum):
    """配置变更类型"""
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class ConfigChange:
    """配置变更记录"""
    path: str
    change_type: ConfigChangeType
    old_value: Any
    new_value: Any
    timestamp: float = field(default_factory=time.time)
    user: str = "system"


@dataclass
class ConfigSnapshot:
    """配置快照"""
    config: Dict[str, Any]
    base_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.base_hash:
            self.base_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """计算配置哈希"""
        import json
        config_str = json.dumps(self.config, sort_keys=True, default=str)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]


class ProtectedConfigPaths:
    """
    OpenClaw实现: 受保护配置路径

    防止修改关键的配置路径
    """

    # OpenClaw的受保护路径
    PROTECTED_PATHS = {
        # 权限相关
        "permission.level": {
            "reason": "Permission level controls security",
            "allowed_values": ["safe", "semi_open", "full_open"],
        },
        "permission.protected_paths": {
            "reason": "Protected paths define security boundaries",
            "readonly": True,
        },
        "permission.dangerous_flags": {
            "reason": "Dangerous flags control safety",
            "readonly": True,
        },

        # 安全相关
        "security.enabled": {
            "reason": "Security cannot be disabled",
            "readonly": True,
        },
        "security.credential_patterns": {
            "reason": "Credential patterns define data loss prevention",
            "readonly": True,
        },

        # 工具执行相关
        "tools.exec.ask": {
            "reason": "Exec ask controls confirmation behavior",
            "readonly": False,
        },
        "tools.exec.security": {
            "reason": "Exec security controls dangerous operations",
            "readonly": True,
        },
        "tools.exec.safeBins": {
            "reason": "Safe bins limit command access",
            "readonly": True,
        },

        # API相关
        "api.key": {
            "reason": "API key is sensitive",
            "readonly": False,
            "sensitive": True,
        },
    }

    @classmethod
    def is_protected(cls, path: str) -> bool:
        """检查路径是否受保护"""
        # 精确匹配
        if path in cls.PROTECTED_PATHS:
            return True

        # 前缀匹配 (子路径也受保护)
        for protected in cls.PROTECTED_PATHS:
            if path.startswith(protected + "."):
                return True

        return False

    @classmethod
    def get_protection_info(cls, path: str) -> Optional[Dict]:
        """获取保护信息"""
        # 精确匹配
        if path in cls.PROTECTED_PATHS:
            return cls.PROTECTED_PATHS[path]

        # 前缀匹配
        for protected, info in cls.PROTECTED_PATHS.items():
            if path.startswith(protected + "."):
                return info

        return None

    @classmethod
    def can_modify(cls, path: str, new_value: Any = None) -> tuple[bool, str]:
        """
        检查是否可以修改

        Returns:
            (can_modify, reason)
        """
        info = cls.get_protection_info(path)

        if not info:
            return True, ""

        # 只读检查
        if info.get("readonly", False):
            return False, f"Path '{path}' is readonly: {info['reason']}"

        # 允许值检查
        if "allowed_values" in info:
            if new_value not in info["allowed_values"]:
                return False, f"Value must be one of: {info['allowed_values']}"

        return True, ""


class DangerousFlags:
    """
    OpenClaw实现: 危险标志检测

    检测和阻止启用危险配置标志
    """

    # 危险标志定义
    DANGEROUS_FLAGS = {
        "allow_dangerous_operations": {
            "severity": "critical",
            "description": "Allow all operations without security checks",
            "danger": "Disables all safety mechanisms",
        },
        "disable_security_checks": {
            "severity": "critical",
            "description": "Disable all security validations",
            "danger": "Removes credential detection and malware scanning",
        },
        "skip_permission_check": {
            "severity": "high",
            "description": "Skip permission checks for all operations",
            "danger": "Bypasses user confirmation for dangerous actions",
        },
        "full_admin_access": {
            "severity": "high",
            "description": "Grant full administrative privileges",
            "danger": "Allows unrestricted system access",
        },
        "allow_system_modification": {
            "severity": "medium",
            "description": "Allow modification of system files",
            "danger": "Can modify protected system paths",
        },
        "disable_audit_log": {
            "severity": "medium",
            "description": "Disable audit logging",
            "danger": "Removes security audit trail",
        },
        "allow_network_bypass": {
            "severity": "high",
            "description": "Allow bypassing network restrictions",
            "danger": "Can make unrestricted network requests",
        },
        "enable_raw_exec": {
            "severity": "critical",
            "description": "Enable raw command execution",
            "danger": "Executes commands without any wrapping",
        },
    }

    @classmethod
    def is_dangerous(cls, flag: str) -> bool:
        """检查是否为危险标志"""
        return flag in cls.DANGEROUS_FLAGS

    @classmethod
    def get_info(cls, flag: str) -> Optional[Dict]:
        """获取危险标志信息"""
        return cls.DANGEROUS_FLAGS.get(flag)

    @classmethod
    def check_flags(cls, config: Dict) -> List[Dict]:
        """
        检查配置中的危险标志

        Returns:
            List of dangerous flags found
        """
        found = []

        for key, value in cls._flatten_dict(config).items():
            # 直接匹配
            if key in cls.DANGEROUS_FLAGS:
                if value is True or value == "true":
                    found.append({
                        "flag": key,
                        **cls.DANGEROUS_FLAGS[key],
                        "value": value
                    })

            # 嵌套匹配
            for dangerous_flag in cls.DANGEROUS_FLAGS:
                if key.endswith(f".{dangerous_flag}") or key == dangerous_flag:
                    if value is True or value == "true":
                        found.append({
                            "flag": key,
                            **cls.DANGEROUS_FLAGS[dangerous_flag],
                            "value": value
                        })

        return found

    @classmethod
    def _flatten_dict(cls, d: Dict, parent_key: str = "") -> Dict:
        """展平嵌套字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(cls._flatten_dict(v, new_key).items())
            else:
                items.append((new_key, v))
        return dict(items)


class BaseHashConcurrencyControl:
    """
    OpenClaw实现: baseHash并发控制

    防止并发写入冲突
    """

    def __init__(self):
        self._snapshots: Dict[str, ConfigSnapshot] = {}

    def create_snapshot(self, config_id: str, config: Dict) -> ConfigSnapshot:
        """创建配置快照"""
        snapshot = ConfigSnapshot(config=config)
        self._snapshots[config_id] = snapshot
        return snapshot

    def verify_hash(self, config_id: str, base_hash: str) -> bool:
        """验证baseHash"""
        if config_id not in self._snapshots:
            return True  # 新配置，无冲突

        current_hash = self._snapshots[config_id].base_hash
        return current_hash == base_hash

    def update_snapshot(self, config_id: str, config: Dict) -> bool:
        """更新配置快照"""
        if config_id in self._snapshots:
            current_hash = self._snapshots[config_id].base_hash
            new_config_hash = ConfigSnapshot(config=config).base_hash

            if current_hash != new_config_hash:
                # 配置已变更，检测到并发冲突
                return False

        self._snapshots[config_id] = ConfigSnapshot(config=config)
        return True

    def get_hash(self, config_id: str) -> Optional[str]:
        """获取当前哈希"""
        if config_id in self._snapshots:
            return self._snapshots[config_id].base_hash
        return None


class PayloadHooks:
    """
    OpenClaw实现: Payload钩子

    允许在请求/响应前后执行自定义逻辑
    """

    def __init__(self):
        self._pre_hooks: List[Callable] = []
        self._post_hooks: List[Callable] = []

    def add_pre_hook(self, hook: Callable[[Dict], Optional[Dict]]):
        """添加预处理钩子"""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable[[Dict], Optional[Dict]]):
        """添加后处理钩子"""
        self._post_hooks.append(hook)

    async def run_pre_hooks(self, payload: Dict) -> Optional[Dict]:
        """运行预处理钩子"""
        result = payload
        for hook in self._pre_hooks:
            try:
                modified = hook(result)
                if modified is not None:
                    result = modified
            except Exception:
                pass
        return result

    async def run_post_hooks(self, payload: Dict) -> Optional[Dict]:
        """运行后处理钩子"""
        result = payload
        for hook in self._post_hooks:
            try:
                modified = hook(result)
                if modified is not None:
                    result = modified
            except Exception:
                pass
        return result


class ConfigProtectionManager:
    """
    配置保护管理器 - 融合OpenClaw所有安全机制

    整合:
    1. 受保护路径验证
    2. 危险标志检测
    3. baseHash并发控制
    4. Payload钩子
    """

    def __init__(self):
        self.protected_paths = ProtectedConfigPaths()
        self.dangerous_flags = DangerousFlags()
        self.hash_control = BaseHashConcurrencyControl()
        self.payload_hooks = PayloadHooks()

        self._change_log: List[ConfigChange] = []

    def validate_change(
        self,
        path: str,
        old_value: Any,
        new_value: Any
    ) -> tuple[bool, str]:
        """
        验证配置变更是否允许

        Returns:
            (is_allowed, reason)
        """
        # 检查受保护路径
        is_protected, reason = self.protected_paths.can_modify(path, new_value)
        if not is_protected:
            return False, f"Protected path: {reason}"

        # 记录变更
        change_type = ConfigChangeType.UPDATE
        if old_value is None:
            change_type = ConfigChangeType.ADD
        elif new_value is None:
            change_type = ConfigChangeType.DELETE

        self._change_log.append(ConfigChange(
            path=path,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value
        ))

        return True, ""

    def validate_config(self, config: Dict) -> tuple[bool, List[Dict]]:
        """
        验证整个配置

        Returns:
            (is_valid, errors)
        """
        errors = []

        # 检查危险标志
        dangerous = self.dangerous_flags.check_flags(config)
        for flag_info in dangerous:
            errors.append({
                "type": "dangerous_flag",
                "message": f"Dangerous flag '{flag_info['flag']}': {flag_info['danger']}",
                "severity": flag_info["severity"]
            })

        # 检查受保护路径变更
        for change in self._change_log[-100:]:  # 最近100条
            is_protected, reason = self.protected_paths.can_modify(change.path, change.new_value)
            if not is_protected:
                errors.append({
                    "type": "protected_path",
                    "path": change.path,
                    "message": reason,
                    "severity": "critical"
                })

        return len(errors) == 0, errors

    def assert_mutation_allowed(
        self,
        current_config: Dict,
        new_config: Dict,
        base_hash: str = None
    ) -> None:
        """
        断言配置变更允许 - 失败则抛出异常

        OpenClaw核心算法实现
        """
        # baseHash验证
        if base_hash:
            if not self.hash_control.verify_hash("main", base_hash):
                raise ValueError("Configuration conflict: baseHash mismatch")

        # 危险标志检测
        dangerous = self.dangerous_flags.check_flags(new_config)
        if dangerous:
            flag_names = [f["flag"] for f in dangerous]
            raise ValueError(f"Cannot enable dangerous flags: {flag_names}")

        # 受保护路径验证
        flat_current = self._flatten_dict(current_config)
        flat_new = self._flatten_dict(new_config)

        for path in flat_new:
            if self.protected_paths.is_protected(path):
                old_val = flat_current.get(path)
                new_val = flat_new[path]

                if old_val != new_val:
                    can_modify, reason = self.protected_paths.can_modify(path, new_val)
                    if not can_modify:
                        raise PermissionError(reason)

    def _flatten_dict(self, d: Dict, parent_key: str = "") -> Dict:
        """展平字典"""
        return DangerousFlags._flatten_dict(d, parent_key)


# 全局实例
_config_protection: Optional[ConfigProtectionManager] = None


def get_config_protection() -> ConfigProtectionManager:
    """获取配置保护管理器"""
    global _config_protection
    if _config_protection is None:
        _config_protection = ConfigProtectionManager()
    return _config_protection


# 别名 - 提供统一的导入接口
ConfigProtection = ConfigProtectionManager
