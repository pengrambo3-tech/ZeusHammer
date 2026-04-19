#!/usr/bin/env python3
"""
ZeusHammer LLM 大模型接入模块
支持多API提供商：OpenAI、Claude、ChinaWhAPI、Ollama等
"""

import asyncio
import os
import json
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """LLM提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CHINA_WHAPI = "china_whapi"
    OLLAMA = "ollama"
    GROQ = "groq"
    GEMINI = "gemini"


@dataclass
class Message:
    """对话消息"""
    role: str  # system/user/assistant
    content: str
    name: Optional[str] = None


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: str = "china_whapi"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    api_base: str = ""  # API基础URL
    api_version: str = ""  # API版本
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 60.0
    
    # 中国特供配置
    use_china_endpoint: bool = True  # 使用国内节点


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    provider: str = ""


class BaseLLM:
    """LLM基类"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """发送对话请求"""
        raise NotImplementedError()
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """发送补全请求"""
        raise NotImplementedError()


class OpenAIClient(BaseLLM):
    """OpenAI兼容API客户端"""
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        start = time.time()
        
        # 构建请求
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY", "")
        base_url = self.config.api_base or "https://api.openai.com/v1"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"API错误: {resp.status} - {error}")
                    
                    result = await resp.json()
                    
                    return LLMResponse(
                        content=result["choices"][0]["message"]["content"],
                        model=result.get("model", self.config.model),
                        usage=result.get("usage", {}),
                        latency_ms=(time.time() - start) * 1000,
                        provider="openai"
                    )
                    
        except ImportError:
            # 降级到urllib
            import urllib.request
            import urllib.parse
            
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(data).encode(),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                result = json.loads(response.read())
                
                return LLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    model=result.get("model", self.config.model),
                    usage=result.get("usage", {}),
                    latency_ms=(time.time() - start) * 1000,
                    provider="openai"
                )


class AnthropicClient(BaseLLM):
    """Anthropic Claude API客户端"""
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        start = time.time()
        
        # 分离system消息
        system_msg = ""
        chat_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                chat_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # API配置
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        
        # ChinaWhAPI的特殊处理
        if self.config.provider == "china_whapi":
            base_url = "https://api.chinawhapi.com/v1"
            if not api_key:
                api_key = os.environ.get("CHINA_WHAPI_KEY", "")
        else:
            base_url = self.config.api_base or "https://api.anthropic.com/v1"
        
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true"  # 允许直接访问
        }
        
        # 构建消息内容
        if self.config.provider == "china_whapi":
            # ChinaWhAPI兼容OpenAI格式
            data = {
                "model": self.config.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
            }
            url = f"{base_url}/messages"
            # 移除不支持的头部
            headers.pop("anthropic-dangerous-direct-browser-access", None)
        else:
            # Anthropic原生格式
            data = {
                "model": self.config.model,
                "messages": chat_messages,
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
            }
            if system_msg:
                data["system"] = system_msg
            url = f"{base_url}/messages"
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"API错误: {resp.status} - {error}")
                    
                    result = await resp.json()
                    
                    # ChinaWhAPI返回OpenAI格式
                    if self.config.provider == "china_whapi":
                        content = result["choices"][0]["message"]["content"]
                    else:
                        content = result["content"][0]["text"]
                    
                    return LLMResponse(
                        content=content,
                        model=result.get("model", self.config.model),
                        usage=result.get("usage", {}),
                        latency_ms=(time.time() - start) * 1000,
                        provider="anthropic"
                    )
                    
        except ImportError:
            raise Exception("需要安装aiohttp: pip install aiohttp")


class OllamaClient(BaseLLM):
    """Ollama本地模型客户端"""
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        start = time.time()
        
        base_url = self.config.api_base or "http://localhost:11434"
        
        # 构建Ollama格式的messages
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        data = {
            "model": self.config.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
            }
        }
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/api/chat",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"Ollama错误: {resp.status} - {error}")
                    
                    result = await resp.json()
                    
                    return LLMResponse(
                        content=result["message"]["content"],
                        model=result.get("model", self.config.model),
                        usage={},  # Ollama不返回usage
                        latency_ms=(time.time() - start) * 1000,
                        provider="ollama"
                    )
                    
        except ImportError:
            raise Exception("需要安装aiohttp: pip install aiohttp")


class GroqClient(BaseLLM):
    """Groq API客户端 (免费高速)"""
    
    async def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        start = time.time()
        
        api_key = self.config.api_key or os.environ.get("GROQ_API_KEY", "")
        base_url = "https://api.groq.com/openai/v1"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"Groq API错误: {resp.status} - {error}")
                    
                    result = await resp.json()
                    
                    return LLMResponse(
                        content=result["choices"][0]["message"]["content"],
                        model=result.get("model", self.config.model),
                        usage=result.get("usage", {}),
                        latency_ms=(time.time() - start) * 1000,
                        provider="groq"
                    )
                    
        except ImportError:
            raise Exception("需要安装aiohttp: pip install aiohttp")


class LLMManager:
    """
    LLM管理器
    
    统一管理多个LLM提供商，自动选择和切换
    """
    
    # 模型列表
    MODELS = {
        # OpenAI
        "gpt-4o": {"provider": "openai", "context": 128000, "cost": "high"},
        "gpt-4o-mini": {"provider": "openai", "context": 128000, "cost": "low"},
        "gpt-4-turbo": {"provider": "openai", "context": 128000, "cost": "high"},
        "gpt-3.5-turbo": {"provider": "openai", "context": 16385, "cost": "low"},
        
        # Anthropic
        "claude-opus-4-5": {"provider": "anthropic", "context": 200000, "cost": "high"},
        "claude-sonnet-4-20250514": {"provider": "anthropic", "context": 200000, "cost": "medium"},
        "claude-3-5-sonnet-latest": {"provider": "anthropic", "context": 200000, "cost": "medium"},
        "claude-3-opus": {"provider": "anthropic", "context": 200000, "cost": "high"},
        "claude-3-sonnet": {"provider": "anthropic", "context": 200000, "cost": "medium"},
        "claude-3-haiku": {"provider": "anthropic", "context": 200000, "cost": "low"},
        
        # ChinaWhAPI (兼容OpenAI格式)
        "claude-sonnet-4-20250514": {"provider": "china_whapi", "context": 200000, "cost": "low"},
        "gpt-4o": {"provider": "china_whapi", "context": 128000, "cost": "low"},
        
        # Ollama (本地)
        "llama3.2:3b": {"provider": "ollama", "context": 128000, "cost": "free"},
        "llama3.1:8b": {"provider": "ollama", "context": 128000, "cost": "free"},
        "mistral": {"provider": "ollama", "context": 8192, "cost": "free"},
        "qwen2.5:7b": {"provider": "ollama", "context": 32768, "cost": "free"},
        "deepseek-r1:7b": {"provider": "ollama", "context": 32768, "cost": "free"},
        
        # Groq
        "llama-3.3-70b": {"provider": "groq", "context": 8192, "cost": "free"},
        "mixtral-8x7b": {"provider": "groq", "context": 32768, "cost": "free"},
        "gemma2-9b": {"provider": "groq", "context": 8192, "cost": "free"},
    }
    
    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig()
        self.client: Optional[BaseLLM] = None
        self._initialized = False
    
    async def initialize(self, provider: str = None, model: str = None):
        """初始化LLM客户端"""
        provider = provider or self.config.provider
        model = model or self.config.model
        
        logger.info(f"初始化LLM: {provider}/{model}")
        
        # 创建对应的客户端
        if provider in ["openai", "china_whapi"]:
            self.client = OpenAIClient(self.config)
        elif provider == "anthropic":
            self.client = AnthropicClient(self.config)
        elif provider == "ollama":
            self.client = OllamaClient(self.config)
        elif provider == "groq":
            self.client = GroqClient(self.config)
        else:
            raise ValueError(f"不支持的提供商: {provider}")
        
        self._initialized = True
        logger.info(f"LLM初始化完成: {provider}/{model}")
    
    async def chat(
        self,
        messages: List[Message],
        model: str = None,
        **kwargs
    ) -> LLMResponse:
        """
        发送对话请求
        
        Args:
            messages: 对话消息列表
            model: 可选，指定模型
            **kwargs: 其他参数 (temperature, max_tokens等)
            
        Returns:
            LLMResponse: 模型响应
        """
        if not self._initialized:
            await self.initialize()
        
        # 如果指定了模型
        if model and model != self.config.model:
            self.config.model = model
            await self.initialize(model=model)
        
        return await self.client.chat(messages, **kwargs)
    
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """补全请求"""
        messages = [Message(role="user", content=prompt)]
        return await self.chat(messages, **kwargs)
    
    async def simple_chat(self, user_input: str, system: str = None) -> str:
        """
        简单的对话
        
        Args:
            user_input: 用户输入
            system: 系统提示
            
        Returns:
            str: 模型回复
        """
        messages = []
        
        if system:
            messages.append(Message(role="system", content=system))
        
        messages.append(Message(role="user", content=user_input))
        
        response = await self.chat(messages)
        return response.content
    
    def get_available_models(self, provider: str = None) -> List[str]:
        """获取可用模型列表"""
        if provider:
            return [
                name for name, info in self.MODELS.items()
                if info["provider"] == provider
            ]
        return list(self.MODELS.keys())
    
    def get_providers(self) -> List[str]:
        """获取支持的提供商"""
        return list(set(info["provider"] for info in self.MODELS.values()))


# ============== 便捷函数 ==============

async def create_llm(
    provider: str = "china_whapi",
    model: str = "claude-sonnet-4-20250514",
    api_key: str = None
) -> LLMManager:
    """
    创建LLM管理器
    
    Args:
        provider: 提供商 (openai/anthropic/china_whapi/ollama/groq)
        model: 模型名称
        api_key: API密钥
        
    Returns:
        LLMManager: LLM管理器实例
    """
    config = LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key or ""
    )
    
    llm = LLMManager(config)
    await llm.initialize()
    
    return llm


async def test_llm():
    """测试LLM功能"""
    print("测试LLM功能...")
    
    # 测试ChinaWhAPI
    print("\n1. 测试ChinaWhAPI...")
    try:
        llm = await create_llm("china_whapi", "claude-sonnet-4-20250514")
        
        response = await llm.simple_chat(
            "你好，请用一句话介绍自己",
            system="你是一个友好的AI助手"
        )
        print(f"回复: {response}")
        print("✅ ChinaWhAPI测试成功!")
        
    except Exception as e:
        print(f"❌ ChinaWhAPI测试失败: {e}")
    
    # 测试Ollama
    print("\n2. 测试Ollama...")
    try:
        llm = await create_llm("ollama", "llama3.2:3b")
        
        response = await llm.simple_chat(
            "你好，请用一句话介绍自己",
            system="你是一个友好的AI助手"
        )
        print(f"回复: {response}")
        print("✅ Ollama测试成功!")
        
    except Exception as e:
        print(f"❌ Ollama测试失败: {e}")
    
    # 显示可用模型
    print("\n3. 可用的模型:")
    llm = LLMManager()
    for provider in llm.get_providers():
        models = llm.get_available_models(provider)
        print(f"\n{provider}:")
        for model in models[:5]:
            print(f"  - {model}")


if __name__ == "__main__":
    asyncio.run(test_llm())
