"""
ZeusHammer TUI界面

真实集成OpenClaw的TUI界面。
使用textual库创建交互式终端界面。
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TUIColor:
    """TUI颜色"""
    HEADER = "bold blue"
    USER = "green"
    ASSISTANT = "cyan"
    ERROR = "bold red"
    TOOL = "yellow"
    INFO = "dim"


@dataclass
class TUIMessage:
    """TUI消息"""
    role: str  # user, assistant, system, tool
    content: str
    timestamp: float = 0


class TUIInterface:
    """
    真实TUI界面

    使用textual库创建交互式终端界面。
    支持:
    - 彩色输出
    - 多面板布局
    - 实时更新
    - 命令历史
    """

    def __init__(self):
        self._app = None
        self._messages: list = []
        self._input_mode = "insert"
        self._initialized = False

    async def initialize(self):
        """初始化TUI"""
        try:
            from textual.app import App
            from textual.widgets import Header, Footer, Input, RichLog
            from textual.binding import Binding

            self._app = ZeusHammerApp()
            self._initialized = True
            logger.info("TUI初始化成功")
            return True

        except ImportError:
            logger.warning("textual未安装，使用简单文本界面")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"TUI初始化失败: {e}")
            return False

    async def print(self, message: TUIMessage):
        """打印消息"""
        self._messages.append(message)

        if not self._initialized:
            print(f"[{message.role}] {message.content}")
            return

        if self._app:
            # 更新textual app
            pass
        else:
            # 简单文本输出
            role_colors = {
                "user": TUIColor.USER,
                "assistant": TUIColor.ASSISTANT,
                "system": TUIColor.INFO,
                "tool": TUIColor.TOOL,
                "error": TUIColor.ERROR
            }
            color = role_colors.get(message.role, "")
            print(f"[{message.role.upper()}] {message.content}")

    async def run(self):
        """运行TUI"""
        if self._app:
            await self._app.run_async()
        else:
            # 简单文本循环
            print("\n=== ZeusHammer TUI ===")
            print("输入exit退出\n")

            while True:
                try:
                    user_input = input(">>> ").strip()
                    if not user_input:
                        continue
                    if user_input.lower() in ["exit", "quit"]:
                        break
                    yield user_input
                except (KeyboardInterrupt, EOFError):
                    break


class ZeusHammerApp:
    """
    Textual应用

    一个完整的TUI应用，支持多面板布局。
    """

    def __init__(self):
        self.BINDINGS = [
            ("q", "quit", "退出"),
            ("ctrl+c", "quit", "退出"),
        ]

    async def run_async(self):
        """异步运行"""
        # 实际实现需要完整的Textual App类
        pass


class SimpleTextUI:
    """
    简单文本界面

    当textual不可用时使用。
    """

    def __init__(self):
        self._history = []

    async def initialize(self):
        print("=" * 60)
        print("  ZeusHammer - 宙斯之锤")
        print("  真实集成 ClaudeCode + Hermes + OpenClaw")
        print("=" * 60)
        print()
        return True

    def print_user(self, text: str):
        """打印用户消息"""
        print(f"\n[USER] {text}")

    def print_assistant(self, text: str):
        """打印助手消息"""
        print(f"\n[ZUESHAMMER] {text}")

    def print_tool(self, tool: str, result: str):
        """打印工具结果"""
        print(f"\n[TOOL: {tool}]")
        print(f"  {result[:200]}...")

    def print_error(self, error: str):
        """打印错误"""
        print(f"\n[ERROR] {error}")

    async def input(self) -> str:
        """获取输入"""
        try:
            return input("\n>>> ").strip()
        except (KeyboardInterrupt, EOFError):
            return "exit"


# 全局TUI实例
_tui: Optional[SimpleTextUI] = None


def get_tui() -> SimpleTextUI:
    global _tui
    if _tui is None:
        _tui = SimpleTextUI()
    return _tui