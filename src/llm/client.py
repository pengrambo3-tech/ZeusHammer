"""
ZeusHammer LLM调用层

真实集成ClaudeCode的Anthropic API能力。
"""

import os
import asyncio
import subprocess
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    tool_calls: List[Dict] = None
    usage: Dict = None
    model: str = ""


class LLMClient:
    """
    真实LLM客户端

    集成ClaudeCode的Anthropic API调用能力。
    支持两种模式:
    1. 直接API调用 (ANTHROPIC_API_KEY)
    2. Claude CLI调用 (claude command)
    """

    def __init__(
        self,
        api_key: str = None,
        api_base: str = "https://api.anthropic.com",
        model: str = "claude-opus-4-5"
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.api_base = api_base
        self.model = model

    async def think(self, prompt: str, system: str = "", tools: List[Dict] = None) -> LLMResponse:
        """
        调用LLM思考

        优先使用Claude CLI，失败则使用直接API调用。
        """
        # 方法1: Claude CLI
        result = await self._call_via_cli(prompt, system, tools)
        if result:
            return result

        # 方法2: 直接API
        result = await self._call_via_api(prompt, system, tools)
        if result:
            return result

        # 提供清晰的错误信息
        if not self.api_key and not self._check_claude_cli():
            return LLMResponse(
                content="Error: No API key configured. Please set ANTHROPIC_API_KEY or CHINAWHAPI_KEY in ~/.zueshammer/.env",
                model=self.model
            )
        
        raise RuntimeError("LLM调用失败，请检查API密钥是否有效")

    async def _call_via_cli(self, prompt: str, system: str, tools: List[Dict]) -> Optional[LLMResponse]:
        """通过Claude CLI调用"""
        try:
            # 构建prompt
            full_prompt = prompt
            if system:
                full_prompt = f"{system}\n\n{full_prompt}"

            # 使用claude命令
            cmd = [
                "claude",
                "-p",  # print prompt
                "--model", self.model,
                full_prompt
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return LLMResponse(
                    content=result.stdout.strip(),
                    model=self.model
                )

            logger.debug(f"Claude CLI失败: {result.stderr}")
            return None

        except FileNotFoundError:
            logger.debug("Claude CLI未安装")
            return None
        except Exception as e:
            logger.debug(f"Claude CLI错误: {e}")
            return None

    def _check_claude_cli(self) -> bool:
        """检查Claude CLI是否可用"""
        import shutil
        return shutil.which("claude") is not None

    async def _call_via_api(self, prompt: str, system: str, tools: List[Dict]) -> Optional[LLMResponse]:
        """通过直接API调用"""
        if not self.api_key:
            return None

        try:
            import urllib.request
            import urllib.error

            url = f"{self.api_base}/v1/messages"

            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-dangerous-direct-password-access": "true"
            }

            data = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            if system:
                data["system"] = system

            if tools:
                data["tools"] = tools

            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))

                content = ""
                tool_calls = []

                for block in result.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "name": block.get("name"),
                            "input": block.get("input", {})
                        })

                return LLMResponse(
                    content=content,
                    tool_calls=tool_calls if tool_calls else None,
                    usage=result.get("usage", {}),
                    model=result.get("model", self.model)
                )

        except Exception as e:
            logger.debug(f"API调用失败: {e}")
            return None


# 全局实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


async def llm_think(prompt: str, system: str = "", tools: List[Dict] = None) -> LLMResponse:
    """快速调用"""
    client = get_llm_client()
    return await client.think(prompt, system, tools)