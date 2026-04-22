"""
ZeusHammer - Zeus Hammer
The Super AI Agent

Fusion of:
- ClaudeCode: Local tool calling, code editing, concurrency partitioning
- Hermes: MCP automation, workflow skills, memory system
- OpenClaw: Skill invocation, browser automation, chat ports

Version: 2.0.0
Author: ZeusHammer Team
"""

__version__ = "2.1.0"
__author__ = "ZeusHammer Team"

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Core exports
from src.core.config import Config
from src.core.permission import PermissionLevel, get_permission_manager
from src.core.event_bus import EventBus, Event

# Main class
from src.zueshammer import ZeusHammer

__all__ = [
    "__version__",
    "ZeusHammer",
    "Config",
    "PermissionLevel",
    "EventBus",
    "Event",
]


async def main():
    """Main entry"""
    print("""
╔══════════════════════════════════════════════╗
║       ⚡ ZeusHammer - Zeus Hammer ⚡        ║
║   Super AI Agent | Claude + Hermes + OpenClaw ║
╚══════════════════════════════════════════════╝
    """)

    config = Config.from_default_locations()
    agent = ZeusHammer(config)

    try:
        await agent.start()

        print(f"Permission: {config.permission_level}")
        print(f"Model: {config.model}")
        print(f"Voice: {'Enabled' if config.voice_enabled else 'Disabled'}")
        print()
        print("Type your message, 'exit' to quit")
        print()

        while True:
            try:
                user_input = input("\n>>> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    break

                response = await agent.process(user_input)
                print(f"\n[ZeusHammer]\n{response}\n")

            except KeyboardInterrupt:
                break

    finally:
        await agent.stop()

    print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
