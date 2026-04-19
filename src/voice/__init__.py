"""
ZeusHammer Voice Module
"""

from .voice_system import (
    VoiceInteraction as VoiceInteractionSTT,
    LanguageDetector,
    WhisperSTT,
    EdgeTTS,
    VoiceConfig,
    Language,
)

from .wake_word import (
    VoiceInteraction,
    VoiceManager,
    WakeWordDetector,
    VoiceMemory,
    VoiceProfile,
)

__all__ = [
    "VoiceInteraction",
    "VoiceInteractionSTT",
    "LanguageDetector",
    "WhisperSTT",
    "EdgeTTS",
    "VoiceConfig",
    "Language",
    "VoiceManager",
    "WakeWordDetector",
    "VoiceMemory",
    "VoiceProfile",
]
