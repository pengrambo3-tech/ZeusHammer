"""
ZeusHammer 核心引擎

真正的ZeusHammer智能体核心。
集成ClaudeCode、Hermes、OpenClaw的真实能力。
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.llm.client import LLMClient, LLMResponse
from src.tools.claude_tools import ClaudeTools, ToolResult
from src.browser.real_browser import create_browser, RealBrowser, FallbackBrowser
from src.mcp.real_protocol import MCPManager, get_mcp_manager
from src.tui.interface import SimpleTextUI, TUIMessage
from src.memory.unified import UnifiedMemory
from src.core.event_bus import EventBus, Event

logger = logging.getLogger(__name__)

from src.core.config import Config

class ZeusHammerCore:
    """
    ZeusHammer核心引擎

    真正集成了三个项目的优势:

    1. ClaudeCode优势:
       - Anthropic API真实调用
       - 完整的CLI工具集
       - 代码编辑能力

    2. Hermes优势:
       - MCP协议真实连接
       - Playwright浏览器控制
       - 多服务器管理

    3. OpenClaw优势:
       - TUI交互界面
       - 网关通信
       - 配置管理
    """

    def __init__(self, config: Config = None):
        self.config = config or Config()
        self._running = False

        # 事件总线 - 先初始化，其他组件可能需要
        self.event_bus = EventBus()

        # 核心组件
        self.llm = LLMClient(
            api_key=self.config.anthropic_api_key,
            model=self.config.model
        )
        self.tools = ClaudeTools()
        self.browser: Optional[RealBrowser] = None
        self.mcp = get_mcp_manager()
        self.memory = UnifiedMemory(
            short_max=self.config.memory_short_max,
            short_ttl=self.config.memory_short_ttl,
            long_db=self.config.memory_long_db,
            long_enabled=self.config.memory_long_enabled,
            event_bus=self.event_bus
        )
        self.tui = SimpleTextUI()

        # 状态
        self.conversation_history: List[Dict[str, str]] = []

    async def start(self):
        """启动ZeusHammer"""
        logger.info("启动ZeusHammer...")

        # 初始化各组件
        await self.tui.initialize()
        await self.memory.initialize()

        # 初始化MCP (如果启用)
        if self.config.mcp_enabled:
            await self.mcp.initialize()
            tools = self.mcp.get_tools()
            logger.info(f"MCP工具: {len(tools)}个")

        # 初始化浏览器 (如果启用)
        if self.config.browser_enabled:
            self.browser = await create_browser(headless=True)
            logger.info("浏览器已就绪")

        self._running = True
        await self.event_bus.publish(Event(type="system", data={"message": "ZeusHammer启动成功"}))

    async def process(self, user_input: str) -> str:
        """
        处理用户输入

        真正的思考-执行循环。
        """
        if not self._running:
            return "ZeusHammer未启动"

        # 添加到历史
        self.conversation_history.append({"role": "user", "content": user_input})

        # 记录记忆
        await self.memory.store(
            f"用户: {user_input}",
            value={"role": "user", "content": user_input},
            importance=0.8,
            category="conversation"
        )

        # 调用LLM思考
        await self.event_bus.publish(Event(type="thinking", data={"message": "正在思考..."}))

        response = await self._think(user_input)

        # 记录回复
        self.conversation_history.append({"role": "assistant", "content": response})
        await self.memory.store(
            f"ZeusHammer: {response[:100]}",
            value={"role": "assistant", "content": response},
            importance=0.7,
            category="conversation"
        )

        return response

    async def _think(self, prompt: str) -> str:
        """
        真正的LLM思考

        集成ClaudeCode的API调用能力。
        """
        # 构建系统提示
        system = self._build_system_prompt()

        # 获取MCP工具描述
        mcp_tools = self._get_mcp_tools_schema()

        try:
            # 调用真实LLM
            response = await self.llm.think(
                prompt=prompt,
                system=system,
                tools=mcp_tools
            )

            if response.content:
                # 检查是否需要执行工具
                if response.tool_calls:
                    return await self._execute_tools(response)
                return response.content

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"思考失败: {e}"

        return "无法获取响应"

    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return """你 是 ZeusHammer，宙斯之锤，一个超级智能体。

你融合了以下项目的精华:
- ClaudeCode: 真实的代码编辑和终端能力
- Hermes: MCP协议和浏览器自动化
- OpenClaw: TUI交互和配置管理

你的能力:
1. 文件操作: 读取、写入、编辑文件
2. 终端命令: 执行任何shell命令
3. 浏览器控制: 自动化网页操作
4. MCP工具: 使用各种MCP服务器扩展
5. 代码理解: 理解并修改代码库

保持简洁，直接回答问题。
执行复杂任务时，先解释计划再执行。"""

    def _get_mcp_tools_schema(self) -> List[Dict]:
        """获取MCP工具的schema"""
        tools = self.mcp.get_tools()
        schemas = []

        for tool in tools:
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            })

        return schemas

    async def _execute_tools(self, response: LLMResponse) -> str:
        """执行工具调用"""
        results = []

        for call in response.tool_calls:
            name = call.get("name")
            args = call.get("input", {})

            await self.event_bus.publish(Event(type="tool_call", data={"tool": name}))

            # 优先使用MCP工具
            mcp_tool = self._find_mcp_tool(name)
            if mcp_tool:
                result = await self.mcp.call_tool(mcp_tool.server, name, args)
                results.append(f"[{name}] {result}")
            else:
                # 使用内置工具
                result = await self.tools.execute(name, **args)
                if result.success:
                    results.append(f"[{name}] 成功")
                else:
                    results.append(f"[{name}] 失败: {result.error}")

        return "\n".join(results) if results else "工具执行完成"

    def _find_mcp_tool(self, name: str):
        """查找MCP工具"""
        for tool in self.mcp.get_tools():
            if tool.name == name:
                return tool
        return None

    async def run_interactive(self):
        """交互式运行"""
        await self.start()

        print("\n" + "=" * 60)
        print("  ZeusHammer - 宙斯之锤")
        print("  融合 ClaudeCode + Hermes + OpenClaw")
        print("=" * 60)
        print("\n输入问题或命令，exit退出\n")

        while self._running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "\n>>> "
                )
                user_input = user_input.strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit"]:
                    break

                response = await self.process(user_input)
                print(f"\n[ZeusHammer]\n{response}\n")

            except (KeyboardInterrupt, EOFError):
                break
            except Exception as e:
                print(f"\n[错误] {e}")

        await self.stop()

    async def stop(self):
        """停止ZeusHammer"""
        logger.info("停止ZeusHammer...")

        if self.browser:
            await self.browser.close()

        await self.mcp.close()
        await self.memory.close()

        self._running = False
        await self.event_bus.publish(Event(type="system", data={"message": "ZeusHammer已停止"}))


def main():
    """入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description="ZeusHammer - 宙斯之锤")
    parser.add_argument("--api-key", help="Anthropic API Key")
    parser.add_argument("--model", default="claude-opus-4-5", help="模型")
    parser.add_argument("--headless", action="store_true", help="无头浏览器")
    parser.add_argument("--no-mcp", action="store_true", help="禁用MCP")
    parser.add_argument("--no-browser", action="store_true", help="禁用浏览器")

    args = parser.parse_args()

    # 配置
    config = Config(
        anthropic_api_key=args.api_key or os.environ.get("ANTHROPIC_API_KEY", ""),
        model=args.model,
        mcp_enabled=not args.no_mcp,
        browser_enabled=not args.no_browser
    )

    # 运行
    agent = ZeusHammerCore(config)
    asyncio.run(agent.run_interactive())


if __name__ == "__main__":
    main()