"""
ZeusHammer Security Module

真正融合Hermes安全核心算法:

1. OSV恶意软件检测
2. 凭证泄露检测
3. 危险命令检测
4. 断路器模式
5. 采样回调
6. 速率限制

参考Hermes实现
"""

import asyncio
import re
import logging
import time
import hashlib
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================
# Hermes OSV恶意软件检测
# ============================================

class OSVDetector:
    """
    Hermes核心: OSV恶意软件检测

    使用OSV (Open Source Vulnerabilities)数据库
    检测已知恶意软件包和漏洞

    https://osv.dev
    """

    OSV_API_URL = "https://api.osv.dev/v1"

    # 已知恶意软件包模式
    MALWARE_PACKAGES = {
        # 恶意pip包
        "malware-package-1",
        "suspicious-package",
        "trojan-downloader",
    }

    # 危险命令模式
    DANGEROUS_COMMANDS = {
        "curl": [
            r"curl\s+.*\|\s*(?:sh|bash|python|perl|ruby)",
            r"curl\s+.*-o\s+.*\.sh",
            r"curl\s+.*--insecure\s+.*\|\s*sh",
        ],
        "wget": [
            r"wget\s+.*\|\s*(?:sh|bash|python|perl|ruby)",
            r"wget\s+.*-O\s+.*\.sh",
        ],
        "python": [
            r"python\s+.*-m\s+pip\s+install\s+.*--user\s+.*",
            r"python\s+.*-c\s+.*import\s+os",
            r"python\s+.*-c\s+.*eval\s*\(",
        ],
        "bash": [
            r":\(\)\s*\{\s*:\|:\s*&\s*\}",
            r"fork\s+ bomber",
        ],
    }

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 3600  # 1小时

    async def check_package(self, package_name: str, ecosystem: str = "pip") -> Dict:
        """
        检查包是否恶意

        Hermes实现: 查询OSV数据库
        """
        cache_key = f"{ecosystem}:{package_name}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["timestamp"] < self._cache_ttl:
                return cached["result"]

        try:
            # 查询OSV API
            url = f"{self.OSV_API_URL}/query"
            data = {
                "package": {
                    "name": package_name,
                    "ecosystem": ecosystem,
                }
            }

            req = urllib.request.Request(
                url,
                data=urllib.parse.urlencode(data).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read())

            # 检查是否是恶意软件
            vulnerabilities = result.get("vulns", [])
            is_malware = package_name.lower() in self.MALWARE_PACKAGES

            check_result = {
                "package": package_name,
                "ecosystem": ecosystem,
                "is_malware": is_malware,
                "vulnerabilities": len(vulnerabilities),
                "details": vulnerabilities[:5] if vulnerabilities else [],
            }

            self._cache[cache_key] = {
                "result": check_result,
                "timestamp": time.time(),
            }

            return check_result

        except Exception as e:
            logger.error(f"OSV check failed: {e}")
            return {
                "package": package_name,
                "ecosystem": ecosystem,
                "is_malware": False,
                "error": str(e),
            }

    async def check_command(self, command: str) -> Dict:
        """
        检查命令是否危险

        Hermes实现: 正则匹配危险模式
        """
        results = []

        command_lower = command.lower()

        for dangerous_cmd, patterns in self.DANGEROUS_COMMANDS.items():
            if dangerous_cmd in command_lower:
                for pattern in patterns:
                    if re.search(pattern, command, re.IGNORECASE):
                        results.append({
                            "type": "dangerous_command",
                            "command": dangerous_cmd,
                            "pattern": pattern,
                            "severity": self._get_severity(pattern),
                        })

        return {
            "command": command,
            "is_dangerous": len(results) > 0,
            "issues": results,
        }

    def _get_severity(self, pattern: str) -> str:
        """获取严重级别"""
        if "fork" in pattern.lower():
            return "critical"
        if "rm -rf" in pattern.lower():
            return "critical"
        if "| sh" in pattern.lower():
            return "high"
        return "medium"


# ============================================
# 凭证泄露检测
# ============================================

class CredentialDetector:
    """
    Hermes核心: 凭证泄露检测

    检测代码和命令中的凭证
    """

    # 凭证模式 - 按类型分组
    CREDENTIAL_PATTERNS = {
        # GitHub
        "github_pat": (
            r"ghp_[A-Za-z0-9]{36}",
            "GitHub Personal Access Token"
        ),
        "github_fine_pat": (
            r"github_pat_[A-Za-z0-9_]{22,}",
            "GitHub Fine-grained PAT"
        ),
        "github_oauth": (
            r"gho_[A-Za-z0-9]{36}",
            "GitHub OAuth Token"
        ),

        # OpenAI/Anthropic
        "openai_key": (
            r"sk-[A-Za-z0-9]{48}",
            "OpenAI API Key"
        ),
        "openai_proj_key": (
            r"sk-proj-[A-Za-z0-9_-]{48,}",
            "OpenAI Project Key"
        ),
        "anthropic_key": (
            r"sk-ant-[A-Za-z0-9_-]{48,}",
            "Anthropic API Key"
        ),

        # AWS
        "aws_access_key": (
            r"AKIA[A-Za-z0-9]{16}",
            "AWS Access Key ID"
        ),
        "aws_secret_key": (
            r"A3T[A-Za-z0-9]{16}",
            "AWS Secret Access Key"
        ),

        # 云服务
        "slack_token": (
            r"xox[baprs]-[A-Za-z0-9]{10,}",
            "Slack Token"
        ),
        "discord_token": (
            r"[MN][A-Za-z\\d]{23,}\\.[A-Za-z\\d_-]{6}\\.[A-Za-z\\d_-]{27}",
            "Discord Token"
        ),
        "stripe_key": (
            r"sk_live_[A-Za-z0-9]{24}",
            "Stripe Secret Key"
        ),
        "stripe_pub_key": (
            r"pk_live_[A-Za-z0-9]{24}",
            "Stripe Publishable Key"
        ),

        # 数据库
        "postgres_conn": (
            r"postgres://[^\s]+:[^\s]+@[^\s]+",
            "PostgreSQL Connection String"
        ),
        "mysql_conn": (
            r"mysql://[^\s]+:[^\s]+@[^\s]+",
            "MySQL Connection String"
        ),

        # 私钥
        "private_key": (
            r"-----BEGIN.*PRIVATE KEY-----",
            "Private Key"
        ),
        "ssh_key": (
            r"-----BEGIN OPENSSH PRIVATE KEY-----",
            "SSH Private Key"
        ),

        # 通用
        "api_key_generic": (
            r"api[_-]?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,}",
            "Generic API Key"
        ),
        "password_in_code": (
            r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            "Hardcoded Password"
        ),
        "secret_in_code": (
            r"secret\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            "Hardcoded Secret"
        ),
    }

    def detect(self, text: str) -> List[Dict]:
        """
        检测凭证

        Hermes实现: 遍历所有模式
        """
        findings = []

        for cred_type, (pattern, description) in self.CREDENTIAL_PATTERNS.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                findings.append({
                    "type": cred_type,
                    "description": description,
                    "match": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                })

        return findings

    def sanitize(self, text: str) -> str:
        """
        清理凭证

        Hermes实现: 替换为[REDACTED]
        """
        result = text

        for cred_type, (pattern, _) in self.CREDENTIAL_PATTERNS.items():
            # 保留前6字符
            if "github" in cred_type or "ghp" in cred_type:
                result = re.sub(
                    r"(ghp_[A-Za-z0-9]{6})[A-Za-z0-9]{30}",
                    r"\g<1>...[REDACTED]",
                    result
                )
            elif "openai" in cred_type or "sk-" in pattern:
                result = re.sub(
                    r"(sk-)[A-Za-z0-9]{40}",
                    r"\g<1>..." + "[REDACTED]" * 4,
                    result
                )
            elif "aws" in cred_type or "AKIA" in pattern:
                result = re.sub(
                    r"(AKIA)[A-Za-z0-9]{16}",
                    r"\g<1>...[REDACTED]",
                    result
                )
            elif "slack" in cred_type:
                result = re.sub(
                    r"(xox[baprs]-[A-Za-z0-9]{10})[A-Za-z0-9_-]{20,}",
                    r"\g<1>...[REDACTED]",
                    result
                )
            else:
                # 通用替换
                result = re.sub(
                    pattern,
                    f"[REDACTED_{cred_type.upper()}]",
                    result
                )

        return result

    def is_safe_to_log(self, text: str) -> bool:
        """检查是否安全记录"""
        findings = self.detect(text)
        return len(findings) == 0


# ============================================
# 断路器模式
# ============================================

class CircuitBreaker:
    """
    Hermes核心: 断路器模式

    防止重复失败导致系统崩溃
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

        self._failures = 0
        self._last_failure_time = 0
        self._state = "closed"  # closed, open, half_open
        self._half_open_calls = 0
        self._successes = 0

    @property
    def state(self) -> str:
        """获取当前状态"""
        if self._state == "open":
            if time.time() - self._last_failure_time > self.timeout:
                logger.info(f"Circuit breaker {self.name}: open -> half_open")
                self._state = "half_open"
                self._half_open_calls = 0
                self._successes = 0

        return self._state

    def record_success(self):
        """记录成功"""
        if self._state == "half_open":
            self._successes += 1
            if self._successes >= self.half_open_max_calls:
                logger.info(f"Circuit breaker {self.name}: half_open -> closed")
                self._state = "closed"
                self._failures = 0

        elif self._state == "closed":
            self._failures = max(0, self._failures - 1)

    def record_failure(self):
        """记录失败"""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._state == "half_open":
            logger.warning(f"Circuit breaker {self.name}: half_open -> open")
            self._state = "open"

        elif self._state == "closed":
            if self._failures >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker {self.name}: closed -> open "
                    f"(failures={self._failures})"
                )
                self._state = "open"

    def can_execute(self) -> bool:
        """是否可以执行"""
        if self._state == "open":
            return False
        elif self._state == "half_open":
            return self._half_open_calls < self.half_open_max_calls
        return True

    def record_half_open_call(self):
        """记录半开调用"""
        self._half_open_calls += 1


# ============================================
# 采样回调系统
# ============================================

class SamplingCallback:
    """
    Hermes核心: 采样回调系统

    允许MCP服务器请求LLM采样
    """

    def __init__(
        self,
        llm_client = None,
        max_rpm: int = 60,
        max_tool_rounds: int = 100,
    ):
        self.llm_client = llm_client
        self.max_rpm = max_rpm
        self.max_tool_rounds = max_tool_rounds

        self._rate_timestamps: List[float] = []
        self._tool_loop_count = 0

        # 采样历史
        self._sampling_history: List[Dict] = []

        # 断路器
        self._circuit_breaker = CircuitBreaker(
            name="sampling",
            failure_threshold=10,
            timeout=60,
        )

    def check_rate_limit(self) -> bool:
        """
        滑动窗口速率限制

        Hermes实现: 60秒窗口内最大请求数
        """
        now = time.time()
        window = now - 60

        # 清理过期时间戳
        self._rate_timestamps = [t for t in self._rate_timestamps if t > window]

        if len(self._rate_timestamps) >= self.max_rpm:
            logger.warning(f"Sampling rate limit exceeded: {len(self._rate_timestamps)}/{self.max_rpm}")
            return False

        self._rate_timestamps.append(now)
        return True

    def check_tool_loop_limit(self) -> bool:
        """检查工具循环限制"""
        if self._tool_loop_count > self.max_tool_rounds:
            logger.warning(f"Tool loop limit exceeded: {self._tool_loop_count}/{self.max_tool_rounds}")
            return False

        self._tool_loop_count += 1
        return True

    def reset_tool_loop_count(self):
        """重置工具循环计数"""
        self._tool_loop_count = 0

    async def create_message(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> Optional[Dict]:
        """
        创建采样消息

        Hermes实现: 完整的速率和循环检查
        """
        # 断路器检查
        if not self._circuit_breaker.can_execute():
            return {"error": "Circuit breaker open"}

        # 速率限制
        if not self.check_rate_limit():
            return {"error": "Rate limit exceeded"}

        # 工具循环限制
        if not self.check_tool_loop_limit():
            return {"error": "Tool loop limit exceeded"}

        # 调用LLM
        try:
            if self.llm_client:
                response = await self.llm_client.think(
                    prompt=prompt,
                    system=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                result = {
                    "content": response.content,
                    "model": getattr(self.llm_client, "model", "unknown"),
                    "stop_reason": "end_turn",
                }

            else:
                # 没有LLM客户端时返回错误
                return {"error": "No LLM client configured"}

            # 记录成功
            self._circuit_breaker.record_success()

            # 记录历史
            self._sampling_history.append({
                "timestamp": time.time(),
                "prompt": prompt[:100],
                "response_length": len(result.get("content", "")),
            })

            return result

        except Exception as e:
            # 记录失败
            self._circuit_breaker.record_failure()
            logger.error(f"Sampling failed: {e}")
            return {"error": str(e)}

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "total_samplings": len(self._sampling_history),
            "tool_loop_count": self._tool_loop_count,
            "rate_limit_remaining": self.max_rpm - len(self._rate_timestamps),
            "circuit_breaker_state": self._circuit_breaker.state,
        }


# ============================================
# 安全服务
# ============================================

class SecurityService:
    """
    安全服务 - 整合所有安全组件
    """

    def __init__(self):
        # OSV检测
        self.osv = OSVDetector()

        # 凭证检测
        self.credentials = CredentialDetector()

        # 断路器
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """获取断路器"""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(name=name)
        return self._circuit_breakers[name]

    async def check_command(self, command: str) -> Dict:
        """检查命令安全性"""
        # 危险命令检查
        command_result = await self.osv.check_command(command)

        # 凭证检查
        cred_findings = self.credentials.detect(command)

        return {
            "is_safe": not command_result["is_dangerous"] and len(cred_findings) == 0,
            "dangerous_issues": command_result.get("issues", []),
            "credential_leaks": [
                {"type": f["type"], "description": f["description"]}
                for f in cred_findings
            ],
        }

    async def check_package(self, package_name: str, ecosystem: str = "pip") -> Dict:
        """检查包安全性"""
        return await self.osv.check_package(package_name, ecosystem)

    def check_credentials(self, text: str) -> List[Dict]:
        """检查凭证泄露"""
        return self.credentials.detect(text)

    def sanitize(self, text: str) -> str:
        """清理敏感信息"""
        return self.credentials.sanitize(text)


# 全局实例
_security_service: Optional[SecurityService] = None


def get_security_service() -> SecurityService:
    """获取安全服务"""
    global _security_service
    if _security_service is None:
        _security_service = SecurityService()
    return _security_service


# 辅助函数
import json


# 别名 - 提供统一的导入接口
HermesSecurity = SecurityService
