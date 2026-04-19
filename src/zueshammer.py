"""
ZeusHammer - Zeus Hammer
The Super AI Agent

真正融合三大开源项目核心优势 + 本地大脑

ClaudeCode:
- partitionToolCalls 并发分区算法
- isConcurrencySafe 判断
- OTel遥测日志

Hermes:
- OSV恶意软件检测
- MCP完整协议栈
- 断路器模式

OpenClaw:
- 受保护配置路径
- 危险标志检测
- baseHash并发控制

本地大脑:
- 意图理解
- 技能匹配
- 大模型工作
- 技能学习

语音系统:
- 唤醒词检测
- 实时麦克风监听
- 语音转文字
- 声音记忆
"""

__version__ = "2.0.0"

import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import Config
from src.tools.claude_core import (
    ToolOrchestrator,
    ToolExecutor,
    ToolUseBlock,
    get_tool_executor,
)
from src.security.hermes_security import (
    SecurityService,
    get_security_service,
)
from src.config.openclaw_protection import get_config_protection
from src.mcp.protocol import MCPServerManager, get_mcp_manager
from src.browser.playwright_browser import get_browser_manager
from src.memory.memory_system import MemoryManager
from src.brain import (
    LocalBrain,
    WorkflowEngine,
    Skill,
    Intent,
    IntentType,
)
from src.voice.wake_word import (
    VoiceManager,
    get_voice_manager,
    WakeWordDetector,
    VoiceMemory,
)


class ZeusHammer:
    """
    ZeusHammer - 超级智能体

    工作流程:
    1. 接收用户指令/语音
    2. 本地大脑思考
    3. 技能匹配 → 执行
    4. 未匹配 → 大模型工作
    5. 执行完成 → 学习新技能
    """

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._running = False

        # 记忆系统
        self.memory = MemoryManager()

        # LLM客户端
        from src.llm.client import LLMClient
        self.llm = LLMClient(
            api_key=self.config.anthropic_api_key or self.config.api_key,
            model=self.config.model
        )

        # 本地大脑
        self.brain = LocalBrain(
            memory_manager=self.memory,
            llm_client=self.llm
        )
        self.brain.set_executors(
            skill_executor=self._execute_skill_action,
            llm_executor=self._call_llm
        )

        # 工作流引擎
        self.workflow = WorkflowEngine(self.brain)

        # 工具系统
        self.tool_executor = get_tool_executor(self.config.permission_level)

        # 安全系统
        self.security = get_security_service()

        # MCP
        self.mcp = get_mcp_manager()

        # 浏览器
        self.browser_manager = get_browser_manager()

        # 语音系统
        self.voice_manager = get_voice_manager(
            config={"wake_words": ["宙斯", "zues"]},
            memory_manager=self.memory
        )

        # 统计
        self._stats = {
            "total_requests": 0,
            "skill_hits": 0,
            "llm_calls": 0,
            "skills_learned": 0,
            "errors": 0,
        }

        self._history = []

    async def start(self):
        """启动"""
        logger = logging.getLogger(__name__)
        logger.info("Starting ZeusHammer...")

        await self.mcp.connect_all()
        await self.browser_manager.create_browser()
        await self.voice_manager.initialize()

        self._running = True
        logger.info("ZeusHammer started")

    async def stop(self):
        """停止"""
        logger = logging.getLogger(__name__)
        logger.info("Stopping ZeusHammer...")

        await self.mcp.disconnect_all()
        await self.browser_manager.close_all()

        self._running = False
        logger.info(f"ZeusHammer stopped: {self._stats}")

    async def process(self, user_input: str) -> str:
        """处理用户输入"""
        if not self._running:
            return "ZeusHammer not started"

        self._stats["total_requests"] += 1

        # 本地大脑思考
        think_result = self.brain.think(user_input)

        if think_result.matched_skill:
            # 命中技能
            self._stats["skill_hits"] += 1

            intent = self.brain._understand_intent(user_input)
            context = self._extract_context(intent, user_input)

            response = await self.brain.execute_skill(
                think_result.matched_skill,
                context
            )
        else:
            # 需要大模型
            self._stats["llm_calls"] += 1

            response = await self._call_llm(user_input)

            # 学习新技能
            work_record = await self.brain.execute_work(user_input)

            if work_record.converted_to_skill:
                self._stats["skills_learned"] += 1

        # 记忆
        self.memory.remember(f"conv_{len(self._history)}", {
            "user": user_input,
            "assistant": response,
        })

        self._history.append({"user": user_input, "assistant": response})

        return response

    async def _call_llm(self, user_input: str) -> str:
        """调用大模型"""
        try:
            response = await self.llm.think(
                prompt=user_input,
                system=self._build_system_prompt(),
            )
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            self._stats["errors"] += 1
            return f"Error: {str(e)}"

    async def _execute_skill_action(self, tool: str, params: dict) -> str:
        """执行技能动作"""
        block = ToolUseBlock(
            id=f"skill_{tool}",
            name=tool,
            input=params,
        )
        results = await self.tool_executor.run([block])
        if results and results[0].success:
            return str(results[0].output or "Success")
        elif results:
            return f"Error: {results[0].error}"
        return "No result"

    def _extract_context(self, intent, user_input: str) -> dict:
        """提取上下文"""
        context = {"intent_type": intent.type.value}
        context.update(intent.entities)

        import re
        if intent.type == IntentType.FILE_READ:
            paths = intent.entities.get("paths", [])
            if paths:
                context["path"] = paths[0]
        elif intent.type == IntentType.COMMAND_EXEC:
            cmd_match = re.search(r'(?:命令|执行|run)\s+(.*?)(?:\s|$)', user_input, re.I)
            if cmd_match:
                context["command"] = cmd_match.group(1).strip()

        return context

    def _build_system_prompt(self) -> str:
        """系统提示"""
        return """You are ZeusHammer (宙斯之锤), a super AI agent.

Capabilities:
- File tools: read, write, edit, glob, grep
- Bash tools: execute shell commands
- Browser automation: navigate, click, fill, screenshot
- MCP tools: extend via MCP servers
- Skills: learned workflows

Be concise, helpful, and accurate."""

    def get_skills(self) -> list:
        """获取技能"""
        return self.brain.get_skills()

    def get_stats(self) -> dict:
        """获取统计"""
        return {
            **self._stats,
            "brain": self.brain.get_stats(),
        }


async def run_cli():
    """命令行模式"""
    agent = ZeusHammer()
    await agent.start()

    print("""
╔══════════════════════════════════════════════╗
║       ⚡ ZeusHammer - Zeus Hammer ⚡        ║
╚══════════════════════════════════════════════╝
    """)

    while True:
        try:
            user_input = input("\n>>> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                break

            response = await agent.process(user_input)
            print(f"\n[ZeusHammer]\n{response}\n")
        except KeyboardInterrupt:
            break

    await agent.stop()


async def run_voice():
    """语音模式"""
    agent = ZeusHammer()
    await agent.start()

    print("""
╔══════════════════════════════════════════════╗
║       ⚡ ZeusHammer Voice Mode ⚡           ║
║                                              ║
║   唤醒词: "宙斯"                            ║
╚══════════════════════════════════════════════╝
    """)

    await agent.voice_manager.start_voice_mode(agent)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.voice_manager.stop_voice_mode()
        await agent.stop()


async def run_web():
    """Web模式"""
    from src.ui.server import run_ui
    await run_ui()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["cli", "web", "voice"], default="cli")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.mode == "cli":
        asyncio.run(run_cli())
    elif args.mode == "web":
        asyncio.run(run_web())
    elif args.mode == "voice":
        asyncio.run(run_voice())
