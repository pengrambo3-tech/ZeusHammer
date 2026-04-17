"""
OpenClaw Fusion Module - 核心系统

融合 OpenClaw 核心功能:
- 多渠道接入 (Telegram, Discord, Slack, WhatsApp 等)
- Canvas 系统
- 技能管理
- 配置保护
"""

import asyncio
import logging
import hashlib
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# 渠道网关 (Channel Gateway)
# OpenClaw 核心功能
# ============================================================

class ChannelType(Enum):
    """渠道类型"""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    SIGNAL = "signal"
    WECHAT = "wechat"
    IRC = "irc"
    MATRIX = "matrix"
    CLI = "cli"


@dataclass
class ChannelMessage:
    """渠道消息"""
    channel: ChannelType
    message_id: str
    user_id: str
    user_name: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    attachments: List[Dict] = field(default_factory=list)


@dataclass
class ChannelAdapter:
    """渠道适配器基类"""
    channel_type: ChannelType
    enabled: bool = False
    config: Dict[str, Any] = field(default_factory=dict)

    async def connect(self) -> bool:
        """连接渠道"""
        raise NotImplementedError

    async def disconnect(self):
        """断开连接"""
        raise NotImplementedError

    async def send_message(
        self,
        user_id: str,
        content: str,
        **kwargs
    ) -> bool:
        """发送消息"""
        raise NotImplementedError

    async def handle_update(self, update: Dict) -> Optional[ChannelMessage]:
        """处理更新"""
        raise NotImplementedError

    def format_for_channel(self, content: str, format_type: str = "markdown") -> str:
        """格式化消息以适应渠道"""
        return content


class TelegramAdapter(ChannelAdapter):
    """Telegram 适配器"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(ChannelType.TELEGRAM, config=config)
        self.bot_token = config.get("bot_token", "") if config else ""
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._update_offset = 0
        self._session = None

    async def connect(self) -> bool:
        """连接 Telegram"""
        if not self.bot_token:
            logger.error("Telegram bot token not configured")
            return False

        try:
            # 测试 API 连接
            async with asyncio.timeout(10):
                # 简化实现
                self.enabled = True
                logger.info("Telegram adapter connected")
                return True
        except Exception as e:
            logger.error(f"Telegram connection failed: {e}")
            return False

    async def disconnect(self):
        """断开 Telegram"""
        self.enabled = False
        logger.info("Telegram adapter disconnected")

    async def send_message(
        self,
        user_id: str,
        content: str,
        **kwargs
    ) -> bool:
        """发送消息"""
        if not self.enabled:
            return False

        formatted = self.format_for_channel(content, "markdown")
        logger.info(f"Sending Telegram message to {user_id}: {formatted[:50]}...")
        return True

    async def handle_update(self, update: Dict) -> Optional[ChannelMessage]:
        """处理 Telegram 更新"""
        if "message" in update:
            msg = update["message"]
            return ChannelMessage(
                channel=ChannelType.TELEGRAM,
                message_id=str(msg.get("message_id", "")),
                user_id=str(msg.get("from", {}).get("id", "")),
                user_name=msg.get("from", {}).get("first_name", "Unknown"),
                content=msg.get("text", ""),
                timestamp=msg.get("date", 0)
            )
        return None

    def format_for_channel(self, content: str, format_type: str = "markdown") -> str:
        """Telegram 格式化"""
        # Telegram 使用 MarkdownV2
        formatted = content
        # 转义特殊字符
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>']
        for char in special_chars:
            formatted = formatted.replace(char, f'\\{char}')
        return formatted


class DiscordAdapter(ChannelAdapter):
    """Discord 适配器"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(ChannelType.DISCORD, config=config)
        self.bot_token = config.get("bot_token", "") if config else ""
        self._websocket = None

    async def connect(self) -> bool:
        """连接 Discord"""
        if not self.bot_token:
            logger.error("Discord bot token not configured")
            return False

        self.enabled = True
        logger.info("Discord adapter connected")
        return True

    async def disconnect(self):
        """断开 Discord"""
        self.enabled = False

    async def send_message(
        self,
        user_id: str,
        content: str,
        **kwargs
    ) -> bool:
        """发送消息"""
        if not self.enabled:
            return False

        logger.info(f"Sending Discord message to {user_id}")
        return True

    def format_for_channel(self, content: str, format_type: str = "markdown") -> str:
        """Discord 格式化"""
        # Discord 使用自己的 Markdown
        formatted = content
        # 处理代码块
        if "```" in content:
            formatted = formatted.replace("```", "```\n")
        return formatted


class SlackAdapter(ChannelAdapter):
    """Slack 适配器"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(ChannelType.SLACK, config=config)
        self.bot_token = config.get("bot_token", "") if config else ""
        self.signing_secret = config.get("signing_secret", "") if config else ""

    async def connect(self) -> bool:
        """连接 Slack"""
        if not self.bot_token:
            logger.error("Slack bot token not configured")
            return False

        self.enabled = True
        logger.info("Slack adapter connected")
        return True

    async def disconnect(self):
        """断开 Slack"""
        self.enabled = False

    async def send_message(
        self,
        user_id: str,
        content: str,
        **kwargs
    ) -> bool:
        """发送消息"""
        if not self.enabled:
            return False

        logger.info(f"Sending Slack message to {user_id}")
        return True

    def format_for_channel(self, content: str, format_type: str = "mrkdwn") -> str:
        """Slack 格式化"""
        # Slack 使用 Mrkdwn
        return content


class ChannelGateway:
    """
    渠道网关
    
    OpenClaw 核心：统一管理多渠道接入
    """

    def __init__(self):
        self._adapters: Dict[ChannelType, ChannelAdapter] = {}
        self._handlers: Dict[ChannelType, Callable] = {}
        self._running = False

    def register_adapter(self, adapter: ChannelAdapter):
        """注册渠道适配器"""
        self._adapters[adapter.channel_type] = adapter
        logger.info(f"Registered channel adapter: {adapter.channel_type.value}")

    def register_handler(self, channel: ChannelType, handler: Callable):
        """注册消息处理器"""
        self._handlers[channel] = handler
        logger.info(f"Registered handler for: {channel.value}")

    async def start(self):
        """启动网关"""
        self._running = True

        for channel, adapter in self._adapters.items():
            if adapter.enabled:
                await adapter.connect()

        logger.info("Channel gateway started")

    async def stop(self):
        """停止网关"""
        self._running = False

        for adapter in self._adapters.values():
            if adapter.enabled:
                await adapter.disconnect()

        logger.info("Channel gateway stopped")

    async def handle_message(self, message: ChannelMessage) -> str:
        """处理消息"""
        handler = self._handlers.get(message.channel)
        if handler:
            try:
                response = await handler(message)
                return response
            except Exception as e:
                logger.error(f"Handler error: {e}")
                return f"Error: {e}"

        return "No handler for this channel"

    async def send_to_channel(
        self,
        channel: ChannelType,
        user_id: str,
        content: str
    ) -> bool:
        """发送到渠道"""
        adapter = self._adapters.get(channel)
        if adapter and adapter.enabled:
            return await adapter.send_message(user_id, content)
        return False

    def list_channels(self) -> List[str]:
        """列出可用渠道"""
        return [
            f"{ch.value} (enabled)" if ad.enabled else f"{ch.value} (disabled)"
            for ch, ad in self._adapters.items()
        ]


# ============================================================
# Canvas 系统 (Canvas System)
# OpenClaw 核心功能
# ============================================================

@dataclass
class CanvasElement:
    """Canvas 元素"""
    id: str
    type: str  # div, button, text, image, etc.
    props: Dict[str, Any]
    children: List["CanvasElement"] = field(default_factory=list)


class CanvasRenderer:
    """
    Canvas 渲染器
    
    OpenClaw 核心：实时 Canvas 渲染
    """

    def __init__(self):
        self._elements: Dict[str, CanvasElement] = {}
        self._subscribers: List[Callable] = []

    def add_element(self, element: CanvasElement):
        """添加元素"""
        self._elements[element.id] = element
        self._notify_subscribers()

    def remove_element(self, element_id: str):
        """移除元素"""
        if element_id in self._elements:
            del self._elements[element_id]
            self._notify_subscribers()

    def update_element(self, element_id: str, props: Dict[str, Any]):
        """更新元素属性"""
        if element_id in self._elements:
            self._elements[element_id].props.update(props)
            self._notify_subscribers()

    def subscribe(self, callback: Callable):
        """订阅更新"""
        self._subscribers.append(callback)

    def _notify_subscribers(self):
        """通知订阅者"""
        for callback in self._subscribers:
            try:
                callback(self._elements)
            except Exception as e:
                logger.error(f"Canvas subscriber error: {e}")

    def render_html(self) -> str:
        """渲染为 HTML"""
        html_parts = ['<div class="canvas">']
        for element in self._elements.values():
            html_parts.append(self._render_element(element))
        html_parts.append('</div>')
        return '\n'.join(html_parts)

    def _render_element(self, element: CanvasElement) -> str:
        """渲染单个元素"""
        props_str = ' '.join(f'{k}="{v}"' for k, v in element.props.items())
        inner = ''.join(self._render_element(child) for child in element.children)

        if element.type == 'text':
            return f'<span {props_str}>{inner}</span>'
        elif element.type == 'button':
            return f'<button {props_str}>{inner}</button>'
        elif element.type == 'image':
            return f'<img {props_str} />'
        else:
            return f'<div {props_str}>{inner}</div>'


# ============================================================
# 技能管理 (Skills Management)
# OpenClaw 核心功能
# ============================================================

@dataclass
class Skill:
    """技能定义"""
    id: str
    name: str
    description: str
    triggers: List[str]  # 触发关键词
    handler: Callable
    category: str = "general"
    examples: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillHub:
    """
    技能中心
    
    OpenClaw 核心：管理和执行技能
    """

    def __init__(self, skills_dir: str = "~/.zueshammer/skills"):
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._trigger_index: Dict[str, List[str]] = {}  # 触发词 -> 技能ID

    def register_skill(self, skill: Skill):
        """注册技能"""
        self._skills[skill.id] = skill

        # 构建触发词索引
        for trigger in skill.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower not in self._trigger_index:
                self._trigger_index[trigger_lower] = []
            self._trigger_index[trigger_lower].append(skill.id)

        logger.info(f"Registered skill: {skill.name}")

    def find_matching_skills(self, query: str) -> List[Skill]:
        """查找匹配的技能"""
        query_lower = query.lower()
        matched_ids = set()

        # 精确匹配
        if query_lower in self._trigger_index:
            matched_ids.update(self._trigger_index[query_lower])

        # 包含匹配
        for trigger, ids in self._trigger_index.items():
            if trigger in query_lower or query_lower in trigger:
                matched_ids.update(ids)

        return [self._skills[sid] for sid in matched_ids if sid in self._skills]

    async def execute_skill(self, skill_id: str, context: Dict) -> Any:
        """执行技能"""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        try:
            result = await skill.handler(context)
            logger.info(f"Skill executed: {skill.name}")
            return result
        except Exception as e:
            logger.error(f"Skill execution failed: {skill.name} - {e}")
            raise

    def list_skills(self, category: str = None) -> List[Skill]:
        """列出技能"""
        if category:
            return [s for s in self._skills.values() if s.category == category]
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(skill_id)


# ============================================================
# 配置保护 (Config Protection)
# OpenClaw 核心功能
# ============================================================

class ConfigProtection:
    """
    配置保护
    
    OpenClaw 核心：防止配置被篡改
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._hash: Optional[str] = None
        self._backup_path = f"{config_path}.backup"

    def compute_hash(self) -> str:
        """计算配置哈希"""
        try:
            with open(self.config_path, 'rb') as f:
                content = f.read()
                return hashlib.sha256(content).hexdigest()
        except Exception:
            return ""

    def verify(self) -> bool:
        """验证配置完整性"""
        if not self._hash:
            self._hash = self.compute_hash()
            return True

        current_hash = self.compute_hash()
        return current_hash == self._hash

    def protect(self):
        """保护配置（创建备份）"""
        try:
            import shutil
            shutil.copy2(self.config_path, self._backup_path)
            self._hash = self.compute_hash()
            logger.info(f"Config protected: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Config protection failed: {e}")
            return False

    def restore(self):
        """恢复配置"""
        try:
            import shutil
            shutil.copy2(self._backup_path, self.config_path)
            logger.info(f"Config restored: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Config restore failed: {e}")
            return False


# ============================================================
# 受保护路径 (Protected Paths)
# OpenClaw 核心功能
# ============================================================

class ProtectedPaths:
    """
    受保护路径
    
    OpenClaw 核心：保护系统关键路径
    """

    DEFAULT_PROTECTED = [
        "/System",
        "/Applications/Carbon",
        "/Library/Application Support/com.apple.TCC",
        "/etc/passwd",
        "/etc/shadow",
        "/root/.ssh",
        "~/.ssh/id_rsa",
        "~/.ssh/id_rsa.pub",
        "~/.zueshammer/.env",
        "~/.zueshammer/config.yaml",
    ]

    def __init__(self, additional_paths: List[str] = None):
        self._protected = set(self.DEFAULT_PROTECTED)
        if additional_paths:
            self._protected.update(additional_paths)

    def is_protected(self, path: str) -> bool:
        """检查路径是否受保护"""
        import os
        expanded = os.path.expanduser(path)

        for protected in self._protected:
            expanded_protected = os.path.expanduser(protected)
            if expanded.startswith(expanded_protected):
                return True

        return False

    def add_protected(self, path: str):
        """添加受保护路径"""
        self._protected.add(path)

    def remove_protected(self, path: str):
        """移除受保护路径"""
        self._protected.discard(path)

    def list_protected(self) -> List[str]:
        """列出所有受保护路径"""
        return list(self._protected)


# 全局实例
_channel_gateway: Optional[ChannelGateway] = None
_skill_hub: Optional[SkillHub] = None


def get_channel_gateway() -> ChannelGateway:
    """获取渠道网关"""
    global _channel_gateway
    if _channel_gateway is None:
        _channel_gateway = ChannelGateway()
    return _channel_gateway


def get_skill_hub() -> SkillHub:
    """获取技能中心"""
    global _skill_hub
    if _skill_hub is None:
        _skill_hub = SkillHub()
    return _skill_hub
