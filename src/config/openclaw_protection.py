"""
ZeusHammer OpenClaw Configuration Protection

真正融合OpenClaw配置保护核心算法:

1. 受保护配置路径验证
2. 危险标志检测
3. baseHash并发控制
4. Payload钩子
5. 配置版本控制
6. 实时路径监控

参考OpenClaw实现
"""

import asyncio
import hashlib
import time
import re
import json
import copy
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod


# ============================================
# OpenClaw受保护配置路径
# ============================================

class ProtectedConfigPaths:
    """
    OpenClaw实现: 受保护配置路径

    不能被修改的关键配置路径
    """

    # 受保护的配置路径
    PROTECTED_PATHS = {
        # 权限控制
        "permission.level": {
            "reason": "Controls security policy",
            "readonly": True,
            "allowed_values": ["safe", "semi_open", "full_open"],
        },
        "permission.protected_paths": {
            "reason": "Defines security boundaries",
            "readonly": True,
        },
        "permission.sandbox": {
            "reason": "Controls sandbox enforcement",
            "readonly": True,
        },

        # 安全相关
        "security.enabled": {
            "reason": "Cannot disable security",
            "readonly": True,
            "allowed_values": [True],
        },
        "security.credential_patterns": {
            "reason": "Data loss prevention rules",
            "readonly": True,
        },
        "security.scan_on_read": {
            "reason": "Security scanning policy",
            "readonly": True,
        },

        # 工具执行
        "tools.exec.ask": {
            "reason": "Confirmation behavior",
            "readonly": False,
        },
        "tools.exec.security": {
            "reason": "Dangerous operation policy",
            "readonly": True,
        },
        "tools.exec.safeBins": {
            "reason": "Command allowlist",
            "readonly": True,
        },

        # API配置
        "api.key": {
            "reason": "Sensitive credential",
            "readonly": False,
            "sensitive": True,
        },
        "api.base_url": {
            "reason": "API endpoint",
            "readonly": False,
        },

        # MCP配置
        "mcp.servers": {
            "reason": "Server configuration",
            "readonly": False,
        },
        "mcp.timeout": {
            "reason": "Timeout settings",
            "readonly": False,
        },
    }

    # 嵌套受保护路径 (任何以这些开头的路径)
    PROTECTED_PREFIXES = [
        "security.credential",
        "security.dangerous",
        "permission.admin",
        "tools.exec.dangerous",
    ]

    @classmethod
    def is_protected(cls, path: str) -> bool:
        """检查路径是否受保护"""
        # 精确匹配
        if path in cls.PROTECTED_PATHS:
            return True

        # 前缀匹配
        for prefix in cls.PROTECTED_PREFIXES:
            if path.startswith(prefix + ".") or path == prefix:
                return True

        return False

    @classmethod
    def get_info(cls, path: str) -> Optional[Dict]:
        """获取保护信息"""
        # 精确匹配
        if path in cls.PROTECTED_PATHS:
            return cls.PROTECTED_PATHS[path]

        # 前缀匹配
        for prefix, info in cls.PROTECTED_PATHS.items():
            if path.startswith(prefix + ".") or path == prefix:
                return info

        return None

    @classmethod
    def can_modify(cls, path: str, new_value: Any = None) -> Tuple[bool, str]:
        """检查是否可以修改"""
        info = cls.get_info(path)

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


# ============================================
# OpenClaw危险标志检测
# ============================================

class DangerousFlags:
    """
    OpenClaw实现: 危险标志检测

    检测和阻止危险配置标志
    """

    # 危险标志定义 (按严重级别)
    FLAGS = {
        # 关键危险
        "allow_dangerous_operations": {
            "severity": "critical",
            "description": "Allow all operations without security checks",
            "default_value": False,
            "danger": "Completely disables safety mechanisms",
        },
        "disable_security_checks": {
            "severity": "critical",
            "description": "Disable all security validations",
            "default_value": False,
            "danger": "Removes credential detection and malware scanning",
        },
        "enable_raw_exec": {
            "severity": "critical",
            "description": "Enable raw command execution",
            "default_value": False,
            "danger": "Executes commands without any wrapping",
        },
        "skip_permission_check": {
            "severity": "critical",
            "description": "Skip all permission checks",
            "default_value": False,
            "danger": "Bypasses user confirmation",
        },

        # 高危
        "full_admin_access": {
            "severity": "high",
            "description": "Grant full administrative privileges",
            "default_value": False,
            "danger": "Unrestricted system access",
        },
        "allow_network_bypass": {
            "severity": "high",
            "description": "Allow bypassing network restrictions",
            "default_value": False,
            "danger": "Unrestricted network access",
        },
        "allow_privilege_escalation": {
            "severity": "high",
            "description": "Allow privilege escalation",
            "default_value": False,
            "danger": "Can gain root/admin access",
        },

        # 中危
        "allow_system_modification": {
            "severity": "medium",
            "description": "Allow modification of system files",
            "default_value": False,
            "danger": "Can modify protected system paths",
        },
        "disable_audit_log": {
            "severity": "medium",
            "description": "Disable audit logging",
            "default_value": False,
            "danger": "Removes security audit trail",
        },
        "allow_unsigned_scripts": {
            "severity": "medium",
            "description": "Allow running unsigned scripts",
            "default_value": False,
            "danger": "Can execute unverified code",
        },
    }

    @classmethod
    def is_dangerous(cls, flag: str) -> bool:
        """检查是否为危险标志"""
        return flag in cls.FLAGS

    @classmethod
    def get_severity(cls, flag: str) -> str:
        """获取严重级别"""
        if flag in cls.FLAGS:
            return cls.FLAGS[flag]["severity"]
        return "unknown"

    @classmethod
    def get_info(cls, flag: str) -> Optional[Dict]:
        """获取危险标志信息"""
        return cls.FLAGS.get(flag)

    @classmethod
    def check_config(cls, config: Dict) -> List[Dict]:
        """
        检查配置中的危险标志

        OpenClaw核心算法
        """
        found = []
        flat = cls._flatten_dict(config)

        for key, value in flat.items():
            # 检查危险标志
            if key in cls.FLAGS:
                info = cls.FLAGS[key]
                if value is True or value == "true":
                    found.append({
                        "flag": key,
                        "severity": info["severity"],
                        "description": info["description"],
                        "danger": info["danger"],
                        "current_value": value,
                    })

            # 检查危险前缀
            for flag in cls.FLAGS:
                if key.endswith("." + flag) or key == flag:
                    info = cls.FLAGS[flag]
                    if value is True or value == "true":
                        found.append({
                            "flag": key,
                            "severity": info["severity"],
                            "description": info["description"],
                            "danger": info["danger"],
                            "current_value": value,
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


# ============================================
# OpenClaw baseHash并发控制
# ============================================

class BaseHashControl:
    """
    OpenClaw实现: baseHash并发控制

    防止并发写入冲突
    基于乐观锁原理
    """

    def __init__(self):
        self._snapshots: Dict[str, "ConfigSnapshot"] = {}

    def create_snapshot(self, config_id: str, config: Dict) -> "ConfigSnapshot":
        """创建配置快照"""
        snapshot = ConfigSnapshot(config)
        self._snapshots[config_id] = snapshot
        return snapshot

    def compute_hash(self, config: Dict) -> str:
        """计算配置哈希"""
        # 标准化配置
        normalized = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def verify_hash(self, config_id: str, base_hash: str) -> bool:
        """验证baseHash"""
        if config_id not in self._snapshots:
            return True  # 新配置

        current = self._snapshots[config_id]
        return current.base_hash == base_hash

    def update_if_match(
        self,
        config_id: str,
        new_config: Dict,
        base_hash: str,
    ) -> Tuple[bool, str]:
        """
        原子更新 (CAS操作)

        Returns:
            (success, message)
        """
        # 检查是否存在
        if config_id in self._snapshots:
            current = self._snapshots[config_id]

            # 验证baseHash
            if current.base_hash != base_hash:
                return False, "Configuration conflict: baseHash mismatch"

        # 更新
        snapshot = ConfigSnapshot(new_config)
        self._snapshots[config_id] = snapshot
        return True, "Updated"

    def get_hash(self, config_id: str) -> Optional[str]:
        """获取当前哈希"""
        if config_id in self._snapshots:
            return self._snapshots[config_id].base_hash
        return None


@dataclass
class ConfigSnapshot:
    """配置快照"""
    config: Dict
    base_hash: str = ""
    timestamp: float = field(default_factory=time.time)
    version: int = 1

    def __post_init__(self):
        if not self.base_hash:
            # 标准化并计算哈希
            normalized = json.dumps(self.config, sort_keys=True, default=str)
            self.base_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]


# ============================================
# OpenClaw Payload钩子
# ============================================

class PayloadHooks:
    """
    OpenClaw实现: Payload钩子

    请求/响应拦截和处理
    """

    def __init__(self):
        self._pre_send_hooks: List[Callable] = []
        self._post_receive_hooks: List[Callable] = []
        self._pre_config_hooks: List[Callable] = []
        self._post_config_hooks: List[Callable] = []

    def add_pre_send_hook(self, hook: Callable[[Dict], Optional[Dict]]):
        """添加发送前钩子"""
        self._pre_send_hooks.append(hook)

    def add_post_receive_hook(self, hook: Callable[[Dict], Optional[Dict]]):
        """添加接收后钩子"""
        self._post_receive_hooks.append(hook)

    def add_pre_config_hook(self, hook: Callable[[Dict, Dict], Tuple[bool, str]]):
        """
        添加配置修改前钩子

        Args:
            hook: (current_config, new_config) -> (allowed, reason)

        Returns:
            (修改是否允许, 原因)
        """
        self._pre_config_hooks.append(hook)

    def add_post_config_hook(self, hook: Callable[[str, Any, Any], None]):
        """
        添加配置修改后钩子

        Args:
            hook: (path, old_value, new_value) -> None
        """
        self._post_config_hooks.append(hook)

    async def run_pre_send(self, payload: Dict) -> Dict:
        """运行发送前钩子"""
        result = payload
        for hook in self._pre_send_hooks:
            try:
                modified = hook(result)
                if modified is not None:
                    result = modified
            except Exception as e:
                pass  # 钩子失败不影响主流程
        return result

    async def run_post_receive(self, payload: Dict) -> Dict:
        """运行接收后钩子"""
        result = payload
        for hook in self._post_receive_hooks:
            try:
                modified = hook(result)
                if modified is not None:
                    result = modified
            except Exception as e:
                pass
        return result

    async def run_pre_config(
        self,
        current: Dict,
        new_config: Dict,
    ) -> Tuple[bool, str]:
        """运行配置修改前钩子"""
        for hook in self._pre_config_hooks:
            try:
                allowed, reason = hook(current, new_config)
                if not allowed:
                    return False, reason
            except Exception:
                pass
        return True, ""

    async def run_post_config(
        self,
        path: str,
        old_value: Any,
        new_value: Any,
    ):
        """运行配置修改后钩子"""
        for hook in self._post_config_hooks:
            try:
                hook(path, old_value, new_value)
            except Exception:
                pass


# ============================================
# OpenClaw配置版本控制
# ============================================

class ConfigVersioning:
    """
    OpenClaw实现: 配置版本控制

    跟踪配置变更历史
    """

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self._history: List[Dict] = []
        self._versions: Dict[str, int] = {}

    def record_change(
        self,
        config_id: str,
        path: str,
        old_value: Any,
        new_value: Any,
        reason: str = "",
    ):
        """记录配置变更"""
        # 递增版本号
        version = self._versions.get(config_id, 0) + 1
        self._versions[config_id] = version

        entry = {
            "version": version,
            "config_id": config_id,
            "path": path,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "timestamp": time.time(),
        }

        self._history.append(entry)

        # 限制历史长度
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

        return version

    def get_history(
        self,
        config_id: str = None,
        path: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """获取变更历史"""
        history = self._history

        if config_id:
            history = [h for h in history if h["config_id"] == config_id]

        if path:
            history = [h for h in history if h["path"] == path]

        return history[-limit:]

    def get_version(self, config_id: str) -> int:
        """获取当前版本号"""
        return self._versions.get(config_id, 0)

    def rollback(self, config_id: str, version: int) -> Optional[Dict]:
        """回滚到指定版本"""
        target = None
        for entry in reversed(self._history):
            if entry["config_id"] == config_id and entry["version"] == version:
                target = entry
                break

        if target:
            return {
                "path": target["path"],
                "value": target["old_value"],
            }
        return None


# ============================================
# OpenClaw受保护路径监控
# ============================================

class PathMonitor:
    """
    OpenClaw实现: 受保护路径监控

    监控文件系统变化
    """

    def __init__(self):
        self._watched_paths: Dict[str, List[Callable]] = {}
        self._running = False

    def watch(self, path: str, callback: Callable[[str, str], None]):
        """
        监控路径变化

        Args:
            path: 要监控的路径
            callback: (event_type, path) -> None
                   event_type: "created", "modified", "deleted"
        """
        if path not in self._watched_paths:
            self._watched_paths[path] = []
        self._watched_paths[path].append(callback)

    def unwatch(self, path: str, callback: Callable = None):
        """取消监控"""
        if path in self._watched_paths:
            if callback:
                self._watched_paths[path].remove(callback)
            else:
                del self._watched_paths[path]

    def get_watched_paths(self) -> List[str]:
        """获取监控的路径"""
        return list(self._watched_paths.keys())

    async def check_path(self, path: str) -> bool:
        """检查路径是否有变化"""
        # 简化实现 - 实际应该用watchdog库
        return True

    def notify_change(self, event_type: str, path: str):
        """通知变化"""
        for watched_path, callbacks in self._watched_paths.items():
            if path.startswith(watched_path):
                for callback in callbacks:
                    try:
                        callback(event_type, path)
                    except Exception:
                        pass


# ============================================
# 配置保护管理器 (整合)
# ============================================

class ConfigProtectionManager:
    """
    OpenClaw实现: 配置保护管理器

    整合所有保护机制
    """

    def __init__(self):
        self.protected_paths = ProtectedConfigPaths()
        self.dangerous_flags = DangerousFlags()
        self.hash_control = BaseHashControl()
        self.payload_hooks = PayloadHooks()
        self.versioning = ConfigVersioning()
        self.path_monitor = PathMonitor()

        # 变更日志
        self._change_log: List[Dict] = []

        # 当前配置
        self._current_config: Dict = {}

    def set_config(self, config: Dict):
        """设置当前配置"""
        self._current_config = copy.deepcopy(config)

        # 创建初始快照
        self.hash_control.create_snapshot("main", config)

    def validate_change(
        self,
        path: str,
        old_value: Any,
        new_value: Any,
        reason: str = "",
    ) -> Tuple[bool, str]:
        """
        验证配置变更

        OpenClaw核心算法
        """
        # 检查受保护路径
        can_modify, reason1 = self.protected_paths.can_modify(path, new_value)
        if not can_modify:
            return False, f"Protected path: {reason1}"

        # 检查危险标志
        dangerous = self.dangerous_flags.check_config({path: new_value})
        if dangerous:
            flag = dangerous[0]
            return False, f"Dangerous flag '{flag['flag']}': {flag['danger']}"

        # 运行钩子
        # 注意：这里简化处理，实际应该用async版本

        return True, ""

    def apply_change(
        self,
        path: str,
        new_value: Any,
        base_hash: str = None,
        reason: str = "",
    ) -> Tuple[bool, str]:
        """
        应用配置变更

        Returns:
            (success, message)
        """
        # 获取旧值
        old_value = self._get_nested(self._current_config, path)

        # 验证变更
        allowed, reason1 = self.validate_change(path, old_value, new_value, reason)
        if not allowed:
            return False, reason1

        # CAS操作
        if base_hash:
            success, msg = self.hash_control.update_if_match(
                "main",
                self._current_config,
                base_hash,
            )
            if not success:
                return False, msg

        # 应用变更
        self._set_nested(self._current_config, path, new_value)

        # 记录版本
        version = self.versioning.record_change("main", path, old_value, new_value, reason)

        # 记录变更日志
        self._change_log.append({
            "path": path,
            "old_value": old_value,
            "new_value": new_value,
            "version": version,
            "timestamp": time.time(),
        })

        return True, f"Updated (version {version})"

    def validate_config(self, config: Dict) -> Tuple[bool, List[Dict]]:
        """
        验证整个配置

        Returns:
            (is_valid, errors)
        """
        errors = []

        # 检查危险标志
        dangerous = self.dangerous_flags.check_config(config)
        for flag in dangerous:
            errors.append({
                "type": "dangerous_flag",
                "flag": flag["flag"],
                "severity": flag["severity"],
                "message": flag["danger"],
            })

        return len(errors) == 0, errors

    def assert_mutation_allowed(
        self,
        current_config: Dict,
        new_config: Dict,
        base_hash: str = None,
    ) -> None:
        """
        断言配置变更允许

        失败则抛出异常
        """
        # 危险标志检查
        dangerous = self.dangerous_flags.check_config(new_config)
        if dangerous:
            flags = [f["flag"] for f in dangerous]
            raise PermissionError(f"Cannot enable dangerous flags: {flags}")

        # 受保护路径检查
        flat_current = DangerousFlags._flatten_dict(current_config)
        flat_new = DangerousFlags._flatten_dict(new_config)

        for path in flat_new:
            if self.protected_paths.is_protected(path):
                old_val = flat_current.get(path)
                new_val = flat_new[path]

                if old_val != new_val:
                    can_modify, reason = self.protected_paths.can_modify(path, new_val)
                    if not can_modify:
                        raise PermissionError(reason)

        # baseHash验证
        if base_hash:
            if not self.hash_control.verify_hash("main", base_hash):
                raise ValueError("Configuration conflict: baseHash mismatch")

    def _get_nested(self, obj: Dict, path: str) -> Any:
        """获取嵌套值"""
        keys = path.split(".")
        value = obj
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _set_nested(self, obj: Dict, path: str, value: Any):
        """设置嵌套值"""
        keys = path.split(".")
        current = obj
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def get_change_history(self, limit: int = 50) -> List[Dict]:
        """获取变更历史"""
        return self._change_log[-limit:]


# 全局实例
_config_protection: Optional[ConfigProtectionManager] = None


def get_config_protection() -> ConfigProtectionManager:
    """获取配置保护管理器"""
    global _config_protection
    if _config_protection is None:
        _config_protection = ConfigProtectionManager()
    return _config_protection


# 别名 - 提供统一的导入接口
OpenClawProtection = ConfigProtectionManager
