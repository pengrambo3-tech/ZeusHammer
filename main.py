#!/usr/bin/env python3
"""
ZeusHammer - 命令行快捷入口

Usage:
    python main.py                    # 默认CLI模式
    python main.py --mode web        # Web界面
    python main.py --mode voice     # 语音模式
"""

import sys
from pathlib import Path

# 确保能正确导入 src 模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 转发到 src.main
from src.main import main as src_main

if __name__ == "__main__":
    import asyncio
    asyncio.run(src_main())
