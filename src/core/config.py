"""
ZeusHammer Configuration System

All configuration in English.
Supports layered config: defaults < file < environment variables.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """
    ZeusHammer Configuration Center

    Design:
    - Layered override: defaults -> config file -> environment
    - Type-safe
    - Nested access
    - Change listeners
    """

    # === Basic ===
    name: str = "ZeusHammer"
    version: str = "2.0.0"
    debug: bool = False

    # === API Config ===
    anthropic_api_key: str = ""
    api_provider: str = "anthropic"  # anthropic, openai, local, chinawhapi
    api_key: str = ""
    api_base: str = "https://api.anthropic.com"
    # China LLM (chinawhapi.com)
    chinawhapi_key: str = ""
    chinawhapi_base: str = "https://api.chinawhapi.com/v1"
    model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 8192
    temperature: float = 0.7

    # === Permission Config ===
    permission_level: str = "semi_open"  # safe, semi_open, full_open
    protected_paths: list = field(default_factory=lambda: [
        "/System",
        "/Applications/Carbon",
        "/Library/Application Support/com.apple.TCC",
    ])

    # === Voice Config ===
    voice_enabled: bool = False
    voice_stt_provider: str = "auto"  # auto, whisper, google, azure
    voice_tts_provider: str = "edge"  # edge, google, elevenlabs
    voice_auto_language: bool = True
    voice_response_in_user_lang: bool = True

    # === Chat Ports ===
    telegram_enabled: bool = False
    telegram_bot_token: str = ""

    whatsapp_enabled: bool = False
    whatsapp_api_key: str = ""

    wechat_enabled: bool = False
    wechat_corp_id: str = ""
    wechat_corp_secret: str = ""

    qq_enabled: bool = False
    qq_bot_token: str = ""

    # === Memory Config ===
    memory_enabled: bool = True
    memory_short_max: int = 100
    memory_short_ttl: int = 3600
    memory_long_enabled: bool = False
    memory_long_db: str = "~/.zueshammer/memory.db"

    # === Tools Config ===
    tools_enabled: bool = True
    tool_timeout: int = 30

    # === MCP Config ===
    mcp_enabled: bool = True
    mcp_timeout: int = 120
    mcp_servers: list = field(default_factory=list)

    # === Skills Config ===
    skills_enabled: bool = True
    skills_dir: str = "~/.zueshammer/skills"
    skills_auto_load: bool = True

    # === Browser Config ===
    browser_enabled: bool = False
    browser_provider: str = "playwright"
    browser_headless: bool = True
    browser_viewport: tuple = (1280, 720)

    # === Logging ===
    log_level: str = "INFO"
    log_file: str = ""
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5

    def __post_init__(self):
        """Post-initialization"""
        self._listeners: Dict[str, list] = {}
        self._raw: Dict[str, Any] = {}
        self._load_env()

    def _load_env(self):
        """Load from environment variables"""
        env_mappings = {
            # API
            "ZUESHAMMER_API_KEY": "api_key",
            "ANTHROPIC_API_KEY": "api_key",
            "ZUESHAMMER_API_BASE": "api_base",
            "ZUESHAMMER_MODEL": "model",
            "API_PROVIDER": "api_provider",

            # China LLM (chinawhapi.com)
            "CHINAWHAPI_KEY": "chinawhapi_key",

            # Permission
            "ZUESHAMMER_PERMISSION": "permission_level",

            # Debug
            "ZUESHAMMER_DEBUG": ("debug", lambda x: x.lower() in ("true", "1", "yes")),

            # Voice
            "ZUESHAMMER_VOICE_ENABLED": ("voice_enabled", lambda x: x.lower() in ("true", "1", "yes")),

            # Features
            "ZUESHAMMER_BROWSER_ENABLED": ("browser_enabled", lambda x: x.lower() in ("true", "1", "yes")),
            "ZUESHAMMER_MCP_ENABLED": ("mcp_enabled", lambda x: x.lower() in ("true", "1", "yes")),
            "ZUESHAMMER_SKILLS_ENABLED": ("skills_enabled", lambda x: x.lower() in ("true", "1", "yes")),

            # Chat
            "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
            "WECHAT_CORP_ID": "wechat_corp_id",
            "WECHAT_CORP_SECRET": "wechat_corp_secret",
            "QQ_BOT_TOKEN": "qq_bot_token",
        }

        for env_var, mapping in env_mappings.items():
            value = os.environ.get(env_var)
            if value is None:
                continue

            if isinstance(mapping, tuple):
                key, type_fn = mapping
                try:
                    setattr(self, key, type_fn(value))
                except (ValueError, AttributeError):
                    pass
            else:
                setattr(self, mapping, value)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Config":
        """Load from file"""
        path = Path(path).expanduser()
        if not path.exists():
            logger.warning(f"Config file not found: {path}")
            return cls()

        try:
            with open(path) as f:
                if path.suffix == ".json":
                    data = json.load(f)
                elif path.suffix in (".yaml", ".yml"):
                    import yaml
                    data = yaml.safe_load(f) or {}
                else:
                    data = {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return cls()

        # 展平嵌套配置
        flat_data = cls._flatten_dict(data)

        # 过滤 None 值
        flat_data = {k: v for k, v in flat_data.items() if v is not None}

        # 只保留 Config 类支持的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in flat_data.items() if k in valid_fields}

        return cls(**filtered_data)

    @classmethod
    def _flatten_dict(cls, d, parent_key: str = '', sep: str = '_') -> Dict:
        """展平嵌套字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(cls._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    @classmethod
    def from_default_locations(cls) -> "Config":
        """Load from default locations"""
        locations = [
            "~/.zueshammer/config.yaml",
            "~/.zueshammer/config.json",
            "./config.yaml",
            "./config.json",
        ]

        for loc in locations:
            path = Path(loc).expanduser()
            if path.exists():
                return cls.from_file(path)

        return cls()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value with dot notation"""
        keys = key.split(".")
        value = self.__dict__
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = getattr(value, k, default)
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set value with dot notation"""
        keys = key.split(".")
        obj = self
        for k in keys[:-1]:
            obj = getattr(obj, k)

        old_value = getattr(obj, keys[-1], None)
        setattr(obj, keys[-1], value)
        self._notify(key, old_value, value)

    def _notify(self, key: str, old, new):
        """Notify listeners"""
        if key in self._listeners:
            for callback in self._listeners[key]:
                try:
                    callback(key, old, new)
                except Exception:
                    pass

    def watch(self, key: str, callback):
        """Watch for changes"""
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)

    def save(self, path: Optional[str] = None):
        """Save config"""
        if path is None:
            path = f"{self.get('log_file', '~/.zueshammer')}/config.json"
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            json.dump(self.__dict__, f, indent=2, default=str)

        logger.info(f"Config saved to: {path}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return self.__dict__.copy()

    def merge(self, other: "Config"):
        """Merge another config"""
        for key, value in other.__dict__.items():
            if value is not None and key not in self._raw:
                setattr(self, key, value)
