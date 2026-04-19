"""
ZeusHammer Model Manager

Multi-Model Support with Automatic Routing (inspired by OpenClaw)

Features:
- Multiple providers configuration
- Keyword-based routing rules
- Automatic failover on errors/rate limits
- Task-type based model selection
"""

import os
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task types for routing"""
    CODE = "code"           # Code generation, debugging
    REASONING = "reasoning" # Complex reasoning, analysis
    CHAT = "chat"          # Simple conversation
    CREATIVE = "creative"  # Writing, brainstorming
    SEARCH = "search"      # Web search, information retrieval
    UNKNOWN = "unknown"


@dataclass
class ModelProvider:
    """Model provider configuration"""
    name: str
    api_key: str = ""
    api_base: str = ""
    default_model: str = ""
    enabled: bool = True
    priority: int = 100  # Lower = higher priority
    max_tokens: int = 8192
    temperature: float = 0.7
    
    # Provider-specific settings
    timeout: int = 60
    retry_count: int = 3
    
    def is_configured(self) -> bool:
        """Check if provider has required config"""
        return bool(self.api_key or self.api_base)


@dataclass
class RoutingRule:
    """Routing rule for automatic model selection"""
    keywords: List[str] = field(default_factory=list)
    task_type: TaskType = TaskType.UNKNOWN
    provider: str = ""
    model: str = ""
    condition: str = ""  # "rate_limit", "error", "always"
    
    def matches(self, text: str) -> bool:
        """Check if text matches this rule"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.keywords)


@dataclass
class ModelSelection:
    """Selected model for a request"""
    provider: str
    model: str
    api_key: str
    api_base: str
    reason: str = ""


class ModelManager:
    """
    Model Manager - OpenClaw-inspired multi-model routing
    
    Configuration format:
    {
        "providers": {
            "claude": { "api_key": "...", "model": "claude-3-5-sonnet" },
            "openai": { "api_key": "...", "model": "gpt-4o" },
            "china": { "api_base": "...", "model": "deepseek-chat" }
        },
        "default_provider": "claude",
        "routing_rules": [
            { "keywords": ["code", "debug"], "provider": "claude", "model": "claude-opus" },
            { "keywords": ["search", "查找"], "provider": "china", "model": "deepseek-chat" }
        ],
        "fallback": [
            { "provider": "claude", "model": "claude-3-5-haiku" }
        ]
    }
    """

    # Default models by task type
    DEFAULT_MODELS = {
        TaskType.CODE: "claude-3-5-sonnet-20241022",
        TaskType.REASONING: "claude-opus-4-5",
        TaskType.CHAT: "claude-3-5-haiku-20241022",
        TaskType.CREATIVE: "gpt-4o",
        TaskType.SEARCH: "deepseek-chat",
    }

    def __init__(self):
        self.providers: Dict[str, ModelProvider] = {}
        self.routing_rules: List[RoutingRule] = []
        self.fallback_chain: List[Dict[str, str]] = []
        self.default_provider: str = "claude"
        self._current_provider: str = ""
        self._error_count: Dict[str, int] = {}

    def configure(self, config: Dict[str, Any]):
        """
        Configure from dict (OpenClaw style)
        
        Example config.yaml:
        models:
          default_provider: claude
          providers:
            claude:
              api_key: ${ANTHROPIC_API_KEY}
              model: claude-3-5-sonnet-20241022
            china:
              api_base: https://api.chinawhapi.com/v1
              api_key: ${CHINAWHAPI_KEY}
              model: deepseek-chat
          routing_rules:
            - keywords: [code, debug, 编程]
              provider: claude
              model: claude-opus-4-5
            - keywords: [search, 搜索, 查找]
              provider: china
              model: deepseek-chat
          fallback:
            - provider: claude
              model: claude-3-5-haiku-20241022
        """
        # Load providers
        providers_config = config.get("providers", {})
        for name, p_config in providers_config.items():
            # Support ${ENV_VAR} syntax
            api_key = p_config.get("api_key", "")
            if api_key and api_key.startswith("${") and api_key.endswith("}"):
                env_var = api_key[2:-1]
                api_key = os.environ.get(env_var, "")

            api_base = p_config.get("api_base", "")
            if api_base and api_base.startswith("${") and api_base.endswith("}"):
                env_var = api_base[2:-1]
                api_base = os.environ.get(env_var, "")

            self.providers[name] = ModelProvider(
                name=name,
                api_key=api_key or os.environ.get(f"{name.upper()}_API_KEY", ""),
                api_base=api_base or p_config.get("base_url", ""),
                default_model=p_config.get("model", ""),
                priority=p_config.get("priority", 100),
                enabled=p_config.get("enabled", True),
            )

        # Load routing rules
        rules_config = config.get("routing_rules", [])
        for rule in rules_config:
            task_str = rule.get("task_type", "unknown")
            try:
                task_type = TaskType(task_str) if task_str != "unknown" else TaskType.UNKNOWN
            except ValueError:
                task_type = TaskType.UNKNOWN

            self.routing_rules.append(RoutingRule(
                keywords=rule.get("keywords", []),
                task_type=task_type,
                provider=rule.get("provider", ""),
                model=rule.get("model", ""),
                condition=rule.get("condition", ""),
            ))

        # Load fallback chain
        self.fallback_chain = config.get("fallback", [])
        
        # Set default provider
        self.default_provider = config.get("default_provider", "claude")

    def select_model(self, query: str = "", task_type: TaskType = None) -> Optional[ModelSelection]:
        """
        Select best model for query
        
        Selection logic:
        1. Check routing rules (keyword match)
        2. Check task type
        3. Use default provider
        """
        # 1. Check routing rules
        for rule in self.routing_rules:
            if rule.matches(query):
                provider = self.providers.get(rule.provider)
                if provider and provider.is_configured():
                    logger.info(f"Routing rule matched: {rule.keywords} -> {rule.provider}/{rule.model}")
                    return ModelSelection(
                        provider=rule.provider,
                        model=rule.model or provider.default_model,
                        api_key=provider.api_key,
                        api_base=provider.api_base,
                        reason=f"Routing rule: {rule.keywords}"
                    )

        # 2. Check task type
        if task_type and task_type != TaskType.UNKNOWN:
            # Find provider with matching rule for task type
            for rule in self.routing_rules:
                if rule.task_type == task_type:
                    provider = self.providers.get(rule.provider)
                    if provider and provider.is_configured():
                        return ModelSelection(
                            provider=rule.provider,
                            model=rule.model or provider.default_model,
                            api_key=provider.api_key,
                            api_base=provider.api_base,
                            reason=f"Task type: {task_type.value}"
                        )

        # 3. Use default provider
        default = self.providers.get(self.default_provider)
        if default and default.is_configured():
            return ModelSelection(
                provider=default.name,
                model=default.default_model,
                api_key=default.api_key,
                api_base=default.api_base,
                reason="Default provider"
            )

        # 4. Fallback: use first configured provider
        for name, provider in sorted(self.providers.items(), key=lambda x: x[1].priority):
            if provider.is_configured() and provider.enabled:
                logger.info(f"Fallback to provider: {name}")
                self._current_provider = name
                return ModelSelection(
                    provider=name,
                    model=provider.default_model,
                    api_key=provider.api_key,
                    api_base=provider.api_base,
                    reason="Fallback"
                )

        logger.error("No configured model provider found")
        return None

    def on_error(self, provider: str, error_type: str = "error"):
        """Handle provider error - track for failover"""
        self._error_count[provider] = self._error_count.get(provider, 0) + 1
        
        # Check if should failover
        if self._error_count[provider] >= 3:
            logger.warning(f"Provider {provider} has {self._error_count[provider]} errors, considering failover")
            return True
        return False

    def get_fallback(self, current_provider: str) -> Optional[ModelSelection]:
        """Get fallback model when current fails"""
        # Check fallback chain
        for fb in self.fallback_chain:
            if fb.get("provider") != current_provider:
                provider = self.providers.get(fb.get("provider", ""))
                if provider and provider.is_configured():
                    return ModelSelection(
                        provider=provider.name,
                        model=fb.get("model", provider.default_model),
                        api_key=provider.api_key,
                        api_base=provider.api_base,
                        reason="Fallback chain"
                    )

        # Default fallback: next available provider
        for name, provider in sorted(self.providers.items(), key=lambda x: x[1].priority):
            if name != current_provider and provider.is_configured() and provider.enabled:
                return ModelSelection(
                    provider=name,
                    model=provider.default_model,
                    api_key=provider.api_key,
                    api_base=provider.api_base,
                    reason="Auto-fallback"
                )

        return None

    def reset_error_count(self, provider: str):
        """Reset error count on successful call"""
        self._error_count[provider] = 0

    def get_available_providers(self) -> List[str]:
        """Get list of configured providers"""
        return [name for name, p in self.providers.items() if p.is_configured()]

    def detect_task_type(self, query: str) -> TaskType:
        """Detect task type from query"""
        query_lower = query.lower()
        
        # Code keywords
        code_keywords = ["code", "debug", "function", "def ", "class ", "import ", "编程", "代码", "调试"]
        if any(kw in query_lower for kw in code_keywords):
            return TaskType.CODE
        
        # Reasoning keywords
        reasoning_keywords = ["think", "reason", "analyze", "explain", "分析", "推理", "思考", "为什么", "how"]
        if any(kw in query_lower for kw in reasoning_keywords):
            return TaskType.REASONING
        
        # Search keywords
        search_keywords = ["search", "find", "lookup", "search", "查找", "搜索", "google"]
        if any(kw in query_lower for kw in search_keywords):
            return TaskType.SEARCH
        
        # Creative keywords
        creative_keywords = ["write", "create", "story", "poem", "creative", "写", "创作", "故事", "诗"]
        if any(kw in query_lower for kw in creative_keywords):
            return TaskType.CREATIVE
        
        return TaskType.CHAT

    def get_stats(self) -> Dict[str, Any]:
        """Get model manager stats"""
        return {
            "providers": {name: {
                "configured": p.is_configured(),
                "enabled": p.enabled,
                "default_model": p.default_model,
            } for name, p in self.providers.items()},
            "routing_rules_count": len(self.routing_rules),
            "fallback_count": len(self.fallback_chain),
            "default_provider": self.default_provider,
            "available_providers": self.get_available_providers(),
        }


# Global instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


def init_model_manager(config: Dict[str, Any]):
    """Initialize model manager with config"""
    manager = get_model_manager()
    manager.configure(config)
    return manager
