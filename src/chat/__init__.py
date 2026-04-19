"""
ZeusHammer Chat Module

多平台聊天集成。
"""

from .ports import (
    ChatPortManager,
    ChatPlatform,
    ChatMessage,
    ChatPortConfig,
    ChatAdapter,
    WhatsAppAdapter,
    WeChatAdapter,
    QQAdapter,
    TelegramAdapter,
    get_chat_manager,
)

# 别名导出
ChatPort = ChatPortManager

__all__ = [
    "ChatPortManager",
    "ChatPort",
    "ChatPlatform",
    "ChatMessage",
    "ChatPortConfig",
    "ChatAdapter",
    "WhatsAppAdapter",
    "WeChatAdapter",
    "QQAdapter",
    "TelegramAdapter",
    "get_chat_manager",
]
