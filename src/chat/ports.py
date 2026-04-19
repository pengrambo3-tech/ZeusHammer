"""
ZeusHammer Chat Ports

Multi-port chat integration:
- WhatsApp (international)
- WeChat (微信 - China)
- QQ (中国)
- Telegram (optional)

Each port has its own adapter that handles the specific protocol.
"""

import asyncio
import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatPlatform(Enum):
    """Supported chat platforms"""
    WHATSAPP = "whatsapp"
    WECHAT = "wechat"
    QQ = "qq"
    TELEGRAM = "telegram"
    WEB = "web"  # Built-in web interface


@dataclass
class ChatMessage:
    """Unified chat message"""
    platform: ChatPlatform
    chat_id: str          # Platform-specific chat ID
    user_id: str          # User identifier
    user_name: str         # Display name
    content: str           # Message text
    timestamp: datetime = field(default_factory=datetime.now)
    message_id: str = ""   # Platform message ID
    reply_to: str = ""     # Reply to message ID
    attachments: List[Dict] = field(default_factory=list)  # Files, images, etc.
    raw: Dict = field(default_factory=dict)  # Raw platform data


@dataclass
class ChatPortConfig:
    """Configuration for a chat port"""
    platform: ChatPlatform
    enabled: bool = False
    webhook_url: str = ""   # For receiving messages
    bot_token: str = ""    # Bot/API token
    api_key: str = ""      # Platform API key
    api_secret: str = ""   # Platform API secret
    proxy: str = ""        # HTTP proxy (for China platforms)
    auto_reply: bool = True
    mention_required: bool = False  # Require @mention to trigger


class ChatAdapter(ABC):
    """
    Base adapter for chat platforms.

    Each platform has its own adapter implementing:
    - Connection management
    - Message sending/receiving
    - User management
    """

    def __init__(self, config: ChatPortConfig):
        self.config = config
        self._running = False
        self._message_handler: Optional[Callable] = None

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to platform"""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from platform"""
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, content: str, reply_to: str = "") -> bool:
        """Send message to chat"""
        pass

    @abstractmethod
    async def send_image(self, chat_id: str, image_path: str, caption: str = "") -> bool:
        """Send image to chat"""
        pass

    @abstractmethod
    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> bool:
        """Send file to chat"""
        pass

    async def set_typing(self, chat_id: str, typing: bool = True):
        """Show typing indicator"""
        pass

    def on_message(self, handler: Callable):
        """Register message handler"""
        self._message_handler = handler

    async def _handle_message(self, message: ChatMessage):
        """Internal message handler dispatcher"""
        if self._message_handler:
            try:
                await self._message_handler(message)
            except Exception as e:
                logger.error(f"Message handler error: {e}")


class WhatsAppAdapter(ChatAdapter):
    """
    WhatsApp adapter using WhatsApp Web Protocol or Business API.

    Integration options:
    1. WhatsApp Business API (official, requires phone verification)
    2. WhatsApp Web protocol (third-party, use baileys library)
    """

    def __init__(self, config: ChatPortConfig):
        super().__init__(config)
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to WhatsApp"""
        try:
            # Try using baileys library (WhatsApp Web protocol)
            try:
                from Baileys import WhatsAppWebSocket
                self._client = WhatsAppWebSocket(
                    mobile=self.config.api_key,
                    proxy=self.config.proxy if self.config.proxy else None
                )
                await self._client.connect()
                self._connected = True
                logger.info("WhatsApp connected via Baileys")
                return True
            except ImportError:
                logger.warning("Baileys not installed. Install: pip install baileys")
                # Fallback: webhook-based integration
                logger.info("Using webhook mode for WhatsApp")
                return True

        except Exception as e:
            logger.error(f"WhatsApp connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from WhatsApp"""
        if self._client:
            await self._client.disconnect()
        self._connected = False

    async def send_message(self, chat_id: str, content: str, reply_to: str = "") -> bool:
        """Send WhatsApp message"""
        if not self._connected:
            logger.error("WhatsApp not connected")
            return False

        try:
            if self._client:
                await self._client.sendMessage(chat_id, content)
                return True
            else:
                logger.warning("WhatsApp client not available")
                return False
        except Exception as e:
            logger.error(f"WhatsApp send failed: {e}")
            return False

    async def send_image(self, chat_id: str, image_path: str, caption: str = "") -> bool:
        """Send image via WhatsApp"""
        try:
            if self._client:
                await self._client.sendMediaMessage(
                    chat_id,
                    "image",
                    path=image_path,
                    caption=caption
                )
                return True
        except Exception as e:
            logger.error(f"WhatsApp image send failed: {e}")
        return False

    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> bool:
        """Send file via WhatsApp"""
        try:
            if self._client:
                await self._client.sendMediaMessage(
                    chat_id,
                    "document",
                    path=file_path,
                    caption=caption
                )
                return True
        except Exception as e:
            logger.error(f"WhatsApp file send failed: {e}")
        return False


class WeChatAdapter(ChatAdapter):
    """
    WeChat adapter (微信).

    Integration via WeChat Work API or third-party libraries.
    Note: Official WeChat API requires enterprise account.
    """

    def __init__(self, config: ChatPortConfig):
        super().__init__(config)
        self._api = None
        self._running = False

    async def connect(self) -> bool:
        """Connect to WeChat Work API"""
        try:
            if not self.config.api_key or not self.config.api_secret:
                logger.warning("WeChat API credentials not configured")
                # Try web hook mode
                return True

            # WeChat Work API integration
            try:
                import requests

                # Get access token
                token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
                params = {
                    "corpid": self.config.api_key,
                    "corpsecret": self.config.api_secret
                }

                response = requests.get(token_url, params=params, timeout=10)
                data = response.json()

                if data.get("errcode") == 0:
                    self._access_token = data.get("access_token")
                    logger.info("WeChat Work API connected")
                    return True
                else:
                    logger.error(f"WeChat API error: {data.get('errmsg')}")
                    return False

            except ImportError:
                logger.warning("requests library needed for WeChat")
                return False

        except Exception as e:
            logger.error(f"WeChat connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from WeChat"""
        self._running = False
        self._api = None

    async def send_message(self, chat_id: str, content: str, reply_to: str = "") -> bool:
        """Send WeChat message"""
        try:
            if not hasattr(self, "_access_token"):
                logger.error("WeChat not authenticated")
                return False

            import requests

            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send"
            params = {"access_token": self._access_token}

            data = {
                "touser": chat_id,
                "msgtype": "text",
                "agentid": self.config.api_key,
                "text": {"content": content}
            }

            response = requests.post(url, params=params, json=data, timeout=10)
            result = response.json()

            if result.get("errcode") == 0:
                return True
            else:
                logger.error(f"WeChat send failed: {result.get('errmsg')}")
                return False

        except Exception as e:
            logger.error(f"WeChat send error: {e}")
            return False

    async def send_image(self, chat_id: str, image_path: str, caption: str = "") -> bool:
        """Upload and send image via WeChat"""
        try:
            import requests

            # Upload image first
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload"
            params = {"access_token": self._access_token, "type": "image"}

            with open(image_path, "rb") as f:
                files = {"file": f}
                response = requests.post(upload_url, params=params, files=files, timeout=30)
                result = response.json()

            if result.get("errcode") == 0:
                media_id = result.get("media_id")

                # Send image message
                msg_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send"
                msg_data = {
                    "touser": chat_id,
                    "msgtype": "image",
                    "agentid": self.config.api_key,
                    "image": {"media_id": media_id}
                }

                msg_response = requests.post(
                    msg_url, params={"access_token": self._access_token},
                    json=msg_data, timeout=10
                )
                return msg_response.json().get("errcode") == 0

        except Exception as e:
            logger.error(f"WeChat image send failed: {e}")
        return False

    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> bool:
        """Upload and send file via WeChat Work"""
        try:
            import requests

            # Upload file
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload"
            params = {"access_token": self._access_token, "type": "file"}

            with open(file_path, "rb") as f:
                files = {"file": f}
                response = requests.post(upload_url, params=params, files=files, timeout=60)
                result = response.json()

            if result.get("errcode") == 0:
                media_id = result.get("media_id")

                # Send file message
                msg_data = {
                    "touser": chat_id,
                    "msgtype": "file",
                    "agentid": self.config.api_key,
                    "file": {"media_id": media_id}
                }

                msg_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send"
                msg_response = requests.post(
                    msg_url, params={"access_token": self._access_token},
                    json=msg_data, timeout=10
                )
                return msg_response.json().get("errcode") == 0

        except Exception as e:
            logger.error(f"WeChat file send failed: {e}")
        return False


class QQAdapter(ChatAdapter):
    """
    QQ adapter (QQ机器人).

    Integration via QQ Guild API or OneBot protocol.
    """

    def __init__(self, config: ChatPortConfig):
        super().__init__(config)
        self._ws_client = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to QQ via OneBot/QQ Guild"""
        try:
            # Option 1: QQ Guild API
            if self.config.bot_token:
                logger.info("Connecting to QQ Guild API...")
                # Implementation would go here
                return True

            # Option 2: OneBot (CQHTTP) for regular QQ
            if self.config.webhook_url:
                logger.info("Using OneBot webhook mode...")
                return True

            logger.warning("No QQ credentials configured")
            return False

        except Exception as e:
            logger.error(f"QQ connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from QQ"""
        self._connected = False
        if self._ws_client:
            await self._ws_client.close()

    async def send_message(self, chat_id: str, content: str, reply_to: str = "") -> bool:
        """Send QQ message"""
        try:
            if self.config.webhook_url:
                # OneBot HTTP API
                import requests

                data = {
                    "action": "send_msg",
                    "params": {
                        "message_type": "group" if chat_id.isdigit() else "private",
                        "group_id" if chat_id.isdigit() else "user_id": int(chat_id),
                        "message": content
                    }
                }

                response = requests.post(
                    self.config.webhook_url,
                    json=data,
                    timeout=10
                )
                return response.json().get("retcode") == 0

            logger.warning("QQ sending not configured")
            return False

        except Exception as e:
            logger.error(f"QQ send failed: {e}")
            return False

    async def send_image(self, chat_id: str, image_path: str, caption: str = "") -> bool:
        """Send image via CQ code"""
        image_code = f"[CQ:image,file=file:///{image_path}]"
        return await self.send_message(chat_id, image_code + caption)

    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> bool:
        """Send file via CQ code"""
        file_code = f"[CQ:file,file=file:///{file_path}]"
        return await self.send_message(chat_id, file_code + caption)


class TelegramAdapter(ChatAdapter):
    """
    Telegram adapter.

    Uses Telegram Bot API.
    """

    def __init__(self, config: ChatPortConfig):
        super().__init__(config)
        self._api_url = ""

    async def connect(self) -> bool:
        """Connect to Telegram Bot API"""
        try:
            if not self.config.bot_token:
                logger.error("Telegram bot token not configured")
                return False

            self._api_url = f"https://api.telegram.org/bot{self.config.bot_token}"

            # Get bot info
            import requests
            response = requests.get(f"{self._api_url}/getMe", timeout=10)
            result = response.json()

            if result.get("ok"):
                logger.info(f"Telegram bot connected: {result['result']['username']}")
                return True
            else:
                logger.error(f"Telegram API error: {result}")
                return False

        except Exception as e:
            logger.error(f"Telegram connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Telegram"""
        pass

    async def send_message(self, chat_id: str, content: str, reply_to: str = "") -> bool:
        """Send Telegram message"""
        try:
            import requests

            data = {
                "chat_id": chat_id,
                "text": content,
                "parse_mode": "Markdown"
            }

            if reply_to:
                data["reply_to_message_id"] = int(reply_to)

            response = requests.post(
                f"{self._api_url}/sendMessage",
                json=data,
                timeout=10
            )

            return response.json().get("ok", False)

        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def send_image(self, chat_id: str, image_path: str, caption: str = "") -> bool:
        """Send image via Telegram"""
        try:
            import requests

            with open(image_path, "rb") as f:
                data = {
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }
                files = {"photo": f}

                response = requests.post(
                    f"{self._api_url}/sendPhoto",
                    data=data,
                    files=files,
                    timeout=30
                )

            return response.json().get("ok", False)

        except Exception as e:
            logger.error(f"Telegram image send failed: {e}")
            return False

    async def send_file(self, chat_id: str, file_path: str, caption: str = "") -> bool:
        """Send file via Telegram"""
        try:
            import requests

            with open(file_path, "rb") as f:
                data = {
                    "chat_id": chat_id,
                    "caption": caption,
                }
                files = {"document": f}

                response = requests.post(
                    f"{self._api_url}/sendDocument",
                    data=data,
                    files=files,
                    timeout=60
                )

            return response.json().get("ok", False)

        except Exception as e:
            logger.error(f"Telegram file send failed: {e}")
            return False


class ChatPortManager:
    """
    Manage all chat ports.

    Unified interface for multiple chat platforms.
    """

    def __init__(self):
        self._ports: Dict[ChatPlatform, ChatAdapter] = {}
        self._running = False
        self._webhook_server = None

    def register_port(self, config: ChatPortConfig) -> bool:
        """Register a chat port"""
        try:
            # Create adapter based on platform
            adapters = {
                ChatPlatform.WHATSAPP: WhatsAppAdapter,
                ChatPlatform.WECHAT: WeChatAdapter,
                ChatPlatform.QQ: QQAdapter,
                ChatPlatform.TELEGRAM: TelegramAdapter,
            }

            adapter_class = adapters.get(config.platform)
            if not adapter_class:
                logger.error(f"Unsupported platform: {config.platform}")
                return False

            adapter = adapter_class(config)
            self._ports[config.platform] = adapter

            logger.info(f"Registered chat port: {config.platform.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to register port: {e}")
            return False

    async def connect_all(self) -> Dict[ChatPlatform, bool]:
        """Connect all enabled ports"""
        results = {}

        for platform, adapter in self._ports.items():
            if adapter.config.enabled:
                results[platform] = await adapter.connect()

        self._running = True
        return results

    async def disconnect_all(self):
        """Disconnect all ports"""
        for adapter in self._ports.values():
            await adapter.disconnect()
        self._running = False

    def get_port(self, platform: ChatPlatform) -> Optional[ChatAdapter]:
        """Get adapter for platform"""
        return self._ports.get(platform)

    async def send_to_platform(
        self, platform: ChatPlatform, chat_id: str, content: str, reply_to: str = ""
    ) -> bool:
        """Send message to specific platform"""
        adapter = self._ports.get(platform)
        if not adapter:
            logger.error(f"Port not registered: {platform}")
            return False

        return await adapter.send_message(chat_id, content, reply_to)

    async def broadcast(
        self, content: str, platforms: List[ChatPlatform] = None, exclude: List[ChatPlatform] = None
    ) -> Dict[ChatPlatform, bool]:
        """Broadcast message to multiple platforms"""
        results = {}

        targets = platforms or list(self._ports.keys())
        if exclude:
            targets = [p for p in targets if p not in exclude]

        for platform in targets:
            adapter = self._ports.get(platform)
            if adapter and adapter.config.enabled:
                # Send to all chats for this platform
                results[platform] = await adapter.send_message(
                    adapter.config.chat_id, content
                )

        return results

    def on_message(self, platform: ChatPlatform, handler: Callable):
        """Register message handler for platform"""
        adapter = self._ports.get(platform)
        if adapter:
            adapter.on_message(handler)

    def get_status(self) -> Dict[str, Any]:
        """Get status of all ports"""
        return {
            platform.value: {
                "enabled": adapter.config.enabled,
                "connected": adapter._connected if hasattr(adapter, "_connected") else False,
            }
            for platform, adapter in self._ports.items()
        }


# Global chat manager
_chat_manager: Optional[ChatPortManager] = None


def get_chat_manager() -> ChatPortManager:
    """Get or create chat manager"""
    global _chat_manager
    if _chat_manager is None:
        _chat_manager = ChatPortManager()
    return _chat_manager


# 别名 - 提供统一的导入接口
ChatPort = ChatPortManager
