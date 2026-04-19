#!/usr/bin/env python3
"""
ZeusHammer 测试脚本
用于验证项目在沙盒环境中可以正常运行
"""

import asyncio
import sys
from pathlib import Path

# 设置路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("ZeusHammer 本地测试")
print("=" * 60)

async def test():
    errors = []

    # 1. 配置加载
    print("\n[1] 测试配置加载...")
    try:
        from src.core.config import Config
        config = Config()
        print(f"   ✓ Config 创建成功 (permission: {config.permission_level})")
    except Exception as e:
        errors.append(f"Config: {e}")
        print(f"   ✗ Config 失败: {e}")

    # 2. 内存系统
    print("\n[2] 测试内存系统...")
    try:
        from src.memory.memory_system import MemoryManager
        memory = MemoryManager()
        memory.remember("test_key", {"message": "Hello from ZeusHammer!"})
        value = memory.recall("test_key")
        print(f"   ✓ MemoryManager 创建成功, 测试写入/读取: {value}")
    except Exception as e:
        errors.append(f"Memory: {e}")
        print(f"   ✗ Memory 失败: {e}")

    # 3. LLM客户端
    print("\n[3] 测试LLM客户端...")
    try:
        from src.llm.client import LLMClient
        llm = LLMClient(config)
        print(f"   ✓ LLMClient 创建成功 (model: {llm.model})")
    except Exception as e:
        errors.append(f"LLM: {e}")
        print(f"   ✗ LLM 失败: {e}")

    # 4. 工具系统
    print("\n[4] 测试工具系统...")
    try:
        from src.tools.claude_core import get_tool_executor
        executor = get_tool_executor("safe")
        print(f"   ✓ ToolExecutor 创建成功 (permission: {executor.permission_level})")
    except Exception as e:
        errors.append(f"Tools: {e}")
        print(f"   ✗ Tools 失败: {e}")

    # 5. MCP系统
    print("\n[5] 测试MCP系统...")
    try:
        from src.mcp.protocol import MCPServerManager
        mcp = MCPServerManager()
        print(f"   ✓ MCPServerManager 创建成功")
    except Exception as e:
        errors.append(f"MCP: {e}")
        print(f"   ✗ MCP 失败: {e}")

    # 6. 安全系统
    print("\n[6] 测试安全系统...")
    try:
        from src.security.hermes_security import get_security_service
        security = get_security_service()
        print(f"   ✓ SecurityService 创建成功")
    except Exception as e:
        errors.append(f"Security: {e}")
        print(f"   ✗ Security 失败: {e}")

    # 7. 语音系统
    print("\n[7] 测试语音系统...")
    try:
        from src.voice.wake_word import get_voice_manager
        voice = get_voice_manager(config={"wake_words": ["test"]})
        print(f"   ✓ VoiceManager 创建成功")
    except Exception as e:
        errors.append(f"Voice: {e}")
        print(f"   ✗ Voice 失败: {e}")

    # 8. 大脑系统
    print("\n[8] 测试大脑系统...")
    try:
        from src.brain import LocalBrain
        brain = LocalBrain(llm_client=llm)
        print(f"   ✓ LocalBrain 创建成功")
    except Exception as e:
        errors.append(f"Brain: {e}")
        print(f"   ✗ Brain 失败: {e}")

    # 9. 技能系统
    print("\n[9] 测试技能系统...")
    try:
        from src.skills.workflow import SkillEngine
        skills = SkillEngine()
        print(f"   ✓ SkillEngine 创建成功")
    except Exception as e:
        errors.append(f"Skills: {e}")
        print(f"   ✗ Skills 失败: {e}")

    # 10. ZeusHammer 主类
    print("\n[10] 测试ZeusHammer主类...")
    try:
        from src.zueshammer import ZeusHammer
        agent = ZeusHammer(config)
        print(f"   ✓ ZeusHammer 创建成功")
        await agent.start()
        print(f"   ✓ ZeusHammer 启动成功")

        # 测试 process 方法
        response = await agent.process("你好")
        print(f"   ✓ agent.process() 执行成功")

        await agent.stop()
        print(f"   ✓ ZeusHammer 停止成功")
    except Exception as e:
        errors.append(f"ZeusHammer: {e}")
        print(f"   ✗ ZeusHammer 失败: {e}")

    # 结果总结
    print("\n" + "=" * 60)
    if not errors:
        print("✓ 所有测试通过！")
    else:
        print(f"✗ {len(errors)} 个测试失败:")
        for e in errors:
            print(f"   - {e}")
    print("=" * 60)

    return len(errors) == 0

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
