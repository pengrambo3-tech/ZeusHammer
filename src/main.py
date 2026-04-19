"""
ZeusHammer Main Entry

主入口 - 整合所有功能

支持:
1. 命令行模式
2. Web UI模式
3. 语音模式
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ZeusHammer - 宙斯之锤")
    parser.add_argument("--mode", choices=["cli", "web", "voice"], default="cli")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--permission", choices=["safe", "semi_open", "full_open"])
    parser.add_argument("--beast", action="store_true")
    parser.add_argument("--config", default="~/.zueshammer/config.yaml")

    args = parser.parse_args()

    # 导入核心模块
    from src.core.config import Config
    from src.zueshammer import ZeusHammer
    from src.voice.wake_word import get_voice_manager

    # 加载配置
    config = Config.from_default_locations()

    if args.beast:
        config.permission_level = "full_open"
    elif args.permission:
        config.permission_level = args.permission

    # 创建智能体
    agent = ZeusHammer(config)

    if args.mode == "cli":
        # 命令行模式
        await run_cli(agent)

    elif args.mode == "web":
        # Web UI模式
        await run_web(agent, args.host, args.port)

    elif args.mode == "voice":
        # 语音模式
        await run_voice(agent)


async def run_cli(agent):
    """命令行模式"""
    print(f"""
╔══════════════════════════════════════════════╗
║       ⚡ ZeusHammer - Zeus Hammer ⚡        ║
║   Super AI Agent | Claude + Hermes + OpenClaw ║
╚══════════════════════════════════════════════╝
    """)

    await agent.start()

    print("Type your message, 'exit' to quit, 'stats' for stats")
    print()

    while True:
        try:
            user_input = input("\n>>> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                break

            if user_input.lower() == "stats":
                print(f"\n{agent.get_stats()}")
                continue

            if user_input.lower() == "skills":
                skills = agent.get_skills()
                print(f"\nSkills ({len(skills)}):")
                for s in skills:
                    print(f"  - {s.name}")
                continue

            response = await agent.process(user_input)
            print(f"\n[ZeusHammer]\n{response}\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[Error] {e}")

    await agent.stop()
    print("\nGoodbye!")


async def run_web(agent, host, port):
    """Web模式"""
    try:
        from src.ui.server import run_ui
        logger.info(f"Starting Web UI on http://{host}:{port}")
        await run_ui(host, port)
    except ImportError as e:
        print(f"Error: {e}")
        print("Web mode requires: pip install fastapi uvicorn websockets")


async def run_voice(agent):
    """语音模式"""
    logger.info("Starting Voice Mode...")

    # 启动智能体
    await agent.start()

    # 获取语音管理器
    from src.voice.wake_word import get_voice_manager
    voice_manager = get_voice_manager(
        config={"wake_words": ["宙斯", "zues", "hey"]},
        memory_manager=agent.memory,
    )

    # 初始化语音系统
    await voice_manager.initialize()

    # 启动语音模式
    await voice_manager.start_voice_mode(agent)

    print("""
╔══════════════════════════════════════════════╗
║       ⚡ ZeusHammer Voice Mode ⚡           ║
║                                              ║
║   唤醒词: "宙斯"                            ║
║   说 "退出" 结束                            ║
╚══════════════════════════════════════════════╝
    """)

    # 等待退出
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await voice_manager.stop_voice_mode()
        await agent.stop()
        print("\nVoice mode stopped!")


if __name__ == "__main__":
    asyncio.run(main())
