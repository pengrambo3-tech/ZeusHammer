"""
ZeusHammer China LLM Support

通过 chinawhapi.com 接入中国大模型API
支持: DeepSeek, Qwen, GLM, Moonshot, ERNIE, Doubao, MiniMax 等
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChinaLLMResponse:
    """中国大模型响应"""
    content: str
    tool_calls: List[Dict] = None
    usage: Dict = None
    model: str = ""


class ChinaLLMClient:
    """
    中国大模型客户端
    
    通过 chinawhapi.com 统一API接入中国主流大模型
    特点:
    - 单一API Key调用所有中国模型
    - OpenAI兼容接口
    - 透明官方定价 + 5.5%服务费
    """

    # 支持的模型列表
    SUPPORTED_MODELS = {
        # DeepSeek
        "deepseek-chat": "DeepSeek V3",
        "deepseek-coder": "DeepSeek Coder",
        
        # 通义千问
        "qwen-turbo": "Qwen Turbo",
        "qwen-plus": "Qwen Plus",
        "qwen-max": "Qwen Max",
        "qwen-max-longcontext": "Qwen Max Long Context",
        
        # 智谱GLM
        "glm-4": "GLM-4",
        "glm-4-flash": "GLM-4 Flash",
        "glm-4-plus": "GLM-4 Plus",
        "glm-4v": "GLM-4V (视觉)",
        
        # 月之暗面
        "moonshot-v1-8k": "Moonshot V1 8K",
        "moonshot-v1-32k": "Moonshot V1 32K",
        "moonshot-v1-128k": "Moonshot V1 128K",
        
        # 百度文心
        "ernie-bot": "ERNIE Bot",
        "ernie-bot-4": "ERNIE Bot 4.0",
        "ernie-bot-8k": "ERNIE Bot 8K",
        "ernie-bot-long": "ERNIE Bot Long",
        
        # 字节豆包
        "doubao-pro-32k": "Doubao Pro 32K",
        "doubao-pro-128k": "Doubao Pro 128K",
        "doubao-lite-32k": "Doubao Lite 32K",
        
        # MiniMax
        "abab6-chat": "MiniMax ABAB6 Chat",
        "abab6-gspt": "MiniMax ABAB6 GSPT",
    }

    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.chinawhapi.com/v1",
        model: str = "deepseek-chat"
    ):
        self.api_key = api_key or os.environ.get("CHINAWHAPI_KEY", "")
        self.base_url = base_url
        self.model = model
        
        if not self.api_key:
            logger.warning("CHINAWHAPI_KEY not set, China LLM will not be available")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> ChinaLLMResponse:
        """
        调用中国大模型
        
        Args:
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称 (默认使用初始化时的模型)
            temperature: 温度参数
            max_tokens: 最大token数
        """
        if not self.api_key:
            raise RuntimeError("CHINAWHAPI_KEY not configured")
        
        model = model or self.model
        
        # 验证模型
        if model not in self.SUPPORTED_MODELS:
            logger.warning(f"Unknown model: {model}, available: {list(self.SUPPORTED_MODELS.keys())}")
        
        try:
            import urllib.request
            import urllib.error
            
            url = f"{self.base_url}/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            
            data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            # 添加可选参数
            if "stream" in kwargs:
                data["stream"] = kwargs["stream"]
            if "tools" in kwargs:
                data["tools"] = kwargs["tools"]
            
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                return ChinaLLMResponse(
                    content=result["choices"][0]["message"]["content"],
                    usage=result.get("usage", {}),
                    model=result.get("model", model)
                )
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"China LLM API error: {e.code} - {error_body}")
            raise RuntimeError(f"API调用失败: {e.code}")
        except Exception as e:
            logger.error(f"China LLM error: {e}")
            raise

    async def think(
        self,
        prompt: str,
        system: str = "",
        **kwargs
    ) -> ChinaLLMResponse:
        """
        简化调用 - 输入prompt直接返回内容
        
        Args:
            prompt: 用户输入
            system: 系统提示
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        messages.append({"role": "user", "content": prompt})
        
        return await self.chat(messages, **kwargs)

    def list_models(self) -> List[str]:
        """列出支持的模型"""
        return list(self.SUPPORTED_MODELS.keys())

    def get_model_info(self, model: str) -> Optional[str]:
        """获取模型信息"""
        return self.SUPPORTED_MODELS.get(model)


# 全局实例
_china_llm_client: Optional[ChinaLLMClient] = None


def get_china_llm_client() -> ChinaLLMClient:
    """获取中国大模型客户端实例"""
    global _china_llm_client
    if _china_llm_client is None:
        _china_llm_client = ChinaLLMClient()
    return _china_llm_client


async def china_llm_chat(
    messages: List[Dict[str, str]],
    model: str = "deepseek-chat"
) -> ChinaLLMResponse:
    """快速调用中国大模型"""
    client = get_china_llm_client()
    return await client.chat(messages, model=model)


async def china_llm_think(
    prompt: str,
    system: str = "",
    model: str = "deepseek-chat"
) -> ChinaLLMResponse:
    """快速调用 - 简化接口"""
    client = get_china_llm_client()
    return await client.think(prompt, system, model=model)
