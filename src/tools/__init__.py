"""
ZeusHammer Tools Module

工具系统集成。
"""

from .executor import ToolExecutor
from .builtin import BuiltinTools, FileTools, TerminalTool, WebTools, GitTools, SearchTool, MemoryTools
from .claude_tools import ClaudeTools, ToolResult, get_claude_tools
from .claude_core import get_tool_executor
from .fusion_executor import (
    AdvancedToolExecutor,
    ToolPartitioner,
    SecurityDetector,
    ConfigProtection,
    ToolCall,
    ToolResult as AdvancedToolResult,
    get_advanced_executor,
)

__all__ = [
    "ToolExecutor",
    "BuiltinTools",
    "FileTools",
    "TerminalTool",
    "WebTools",
    "GitTools",
    "SearchTool",
    "MemoryTools",
    "ClaudeTools",
    "ToolResult",
    "get_claude_tools",
    "get_tool_executor",
    "AdvancedToolExecutor",
    "ToolPartitioner",
    "SecurityDetector",
    "ConfigProtection",
    "ToolCall",
    "AdvancedToolResult",
    "get_advanced_executor",
]
