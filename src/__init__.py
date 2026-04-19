"""
ZeusHammer - Zeus Hammer
The Super AI Agent

真正融合三大开源项目核心优势 + 本地大脑 + 语音系统

Usage:
    python -m src.main --mode cli    # 命令行模式
    python -m src.main --mode web    # Web界面
    python -m src.main --mode voice # 语音模式
"""

__version__ = "2.0.0"
__author__ = "ZeusHammer Team"

from .zueshammer import ZeusHammer
from .brain import LocalBrain, WorkflowEngine, Skill, Intent, IntentType
from .memory import MemoryManager
from .voice.wake_word import VoiceManager, WakeWordDetector, VoiceMemory

__all__ = [
    "ZeusHammer",
    "LocalBrain",
    "WorkflowEngine",
    "Skill",
    "Intent",
    "IntentType",
    "MemoryManager",
    "VoiceManager",
    "WakeWordDetector",
    "VoiceMemory",
]
