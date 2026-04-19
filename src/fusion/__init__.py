"""
ZeusHammer Fusion Modules

真正融合三个顶级开源项目的核心代码：
- ClaudeCode: 工具执行引擎、并发分区、OTel遥测
- Hermes: 记忆系统、工具管理、安全机制、MCP协议
- OpenClaw: 多渠道接入、Canvas、技能管理
"""

from .claude_code.tools_engine import (
    ToolExecutor,
    ToolDependencyAnalyzer,
    ToolConcurrencyType,
    ToolCall,
    ToolResult,
    ToolPartition,
    OTelLogger,
    get_telemetry,
)

from .hermes.security import (
    CircuitBreaker,
    CircuitState,
    ToolRegistry,
    ToolMetadata,
    OSVScanner,
    CredentialGuard,
    ToolPermissions,
    MCPClient,
    MCPMessage,
    get_tool_registry,
    get_osv_scanner,
    get_credential_guard,
)

from .openclaw.channels import (
    ChannelGateway,
    ChannelType,
    ChannelAdapter,
    ChannelMessage,
    ChannelGateway,
    TelegramAdapter,
    DiscordAdapter,
    SlackAdapter,
    CanvasRenderer,
    CanvasElement,
    SkillHub,
    Skill,
    ConfigProtection,
    ProtectedPaths,
    get_channel_gateway,
    get_skill_hub,
)

__all__ = [
    # ClaudeCode
    "ToolExecutor",
    "ToolDependencyAnalyzer",
    "ToolConcurrencyType",
    "ToolCall",
    "ToolResult",
    "ToolPartition",
    "OTelLogger",
    "get_telemetry",
    # Hermes
    "CircuitBreaker",
    "CircuitState",
    "ToolRegistry",
    "ToolMetadata",
    "OSVScanner",
    "CredentialGuard",
    "ToolPermissions",
    "MCPClient",
    "MCPMessage",
    "get_tool_registry",
    "get_osv_scanner",
    "get_credential_guard",
    # OpenClaw
    "ChannelGateway",
    "ChannelType",
    "ChannelAdapter",
    "ChannelMessage",
    "TelegramAdapter",
    "DiscordAdapter",
    "SlackAdapter",
    "CanvasRenderer",
    "CanvasElement",
    "SkillHub",
    "Skill",
    "ConfigProtection",
    "ProtectedPaths",
    "get_channel_gateway",
    "get_skill_hub",
]
