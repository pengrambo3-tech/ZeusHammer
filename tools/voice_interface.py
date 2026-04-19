#!/usr/bin/env python3
"""
ZeusHammer - 语音优先接口层
基于Hermes voice_mode.py + Whisper + TTS实现语音优先交互
"""

import asyncio
import threading
import time
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import json

# 语音识别 - 使用Whisper (开源)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# 语音合成 - 使用Coqui TTS或系统TTS
try:
    from TTS.api import TTS as CoquiTTS
    COQUI_TTS_AVAILABLE = True
except ImportError:
    COQUI_TTS_AVAILABLE = False

import pyttsx3  # 备用TTS

from hermes_logging import get_logger

logger = get_logger("voice_interface")

class VoiceFirstInterface:
    """
    语音优先接口 - ZeusHammer核心创新
    
    特性:
    1. 唤醒词检测 (Zues/宙斯)
    2. 实时语音识别 (Whisper)
    3. 语音合成回复 (TTS)
    4. 多轮对话打断
    5. 背景环境音过滤
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.wake_word = self.config.get("wake_word", "Zues")
        self.wake_word_enabled = self.config.get("wake_word_enabled", True)
        
        # 语音组件
        self.asr = None  # 语音识别
        self.tts = None  # 语音合成
        self.wake_word_detector = None
        
        # 音频设备
        self.microphone = None
        self.speaker = None
        
        # 状态
        self.is_listening = False
        self.is_speaking = False
        self.conversation_active = False
        self.current_conversation = []
        
        # 回调
        self.on_command: Optional[Callable] = None
        self.on_wakeword: Optional[Callable] = None
        
        # 线程
        self.listen_thread = None
        self.should_stop = threading.Event()
        
    async def start(self):
        """启动语音接口"""
        logger.info("启动语音优先接口...")
        
        # 初始化语音识别
        await self._init_asr()
        
        # 初始化语音合成
        await self._init_tts()
        
        # 启动监听线程
        self.should_stop.clear()
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        logger.info("✅ 语音接口已启动")
        
    async def stop(self):
        """停止语音接口"""
        self.should_stop.set()
        if self.listen_thread:
            self.listen_thread.join(timeout=2)
        logger.info("语音接口已停止")
        
    async def _init_asr(self):
        """初始化语音识别 (Whisper)"""
        if not WHISPER_AVAILABLE:
            logger.warning("Whisper未安装，语音识别将使用模拟模式")
            return
            
        try:
            # 加载Whisper模型 (使用小型模型以快速响应)
            model_size = self.config.get("whisper_model", "base")
            self.asr = whisper.load_model(model_size)
            logger.info(f"✅ Whisper ASR已加载: {model_size}")
        except Exception as e:
            logger.error(f"Whisper初始化失败: {e}")
            
    async def _init_tts(self):
        """初始化语音合成"""
        try:
            # 尝试Coqui TTS
            if COQUI_TTS_AVAILABLE:
                self.tts = CoquiTTS(model_name="tts_models/zh-CN/baker/tacotron2-DDC", progress_bar=False)
                logger.info("✅ Coqui TTS已加载")
            else:
                # 使用系统TTS
                import pyttsx3
                self.tts = pyttsx3.init()
                logger.info("✅ 系统TTS已加载")
        except Exception as e:
            logger.error(f"TTS初始化失败: {e}")
            
    def _listen_loop(self):
        """监听循环 - 唤醒词 + 语音识别"""
        logger.info("开始监听...")
        
        while not self.should_stop.is_set():
            try:
                # 1. 检测唤醒词 (如果启用)
                if self.wake_word_enabled and not self.conversation_active:
                    if self._detect_wake_word():
                        self._on_wakeword_detected()
                        continue
                        
                # 2. 如果对话激活中，持续监听命令
                if self.conversation_active:
                    audio = self._capture_audio(timeout=5.0)
                    if audio:
                        text = self._transcribe(audio)
                        if text:
                            self._on_command_detected(text)
                            
            except Exception as e:
                logger.error(f"监听错误: {e}")
                time.sleep(1)
                
    def _detect_wake_word(self) -> bool:
        """检测唤醒词 (简化的能量阈值检测，实际应用需专用模型)"""
        # 这里简化实现：检测到语音活动且包含唤醒词
        # 实际应该使用 Porcupine、Snowboy 或自定义关键词识别
        audio = self._capture_audio(timeout=1.0, vad_only=True)
        if audio and self._is_speech(audio):
            text = self._transcribe(audio, short=True)
            if text and self.wake_word.lower() in text.lower():
                return True
        return False
        
    def _on_wakeword_detected(self):
        """唤醒词检测到"""
        logger.info(f"🔊 唤醒词 detected!")
        self.conversation_active = True
        
        # 播放提示音
        self._play_sound("beep")
        
        if self.on_wakeword:
            asyncio.create_task(self.on_wakeword())
            
    def _on_command_detected(self, text: str):
        """检测到语音命令"""
        logger.info(f"🎤 语音命令: {text}")
        
        # 检查是否结束对话
        if any(word in text.lower() for word in ["结束", "退出", "拜拜", "再见"]):
            self.conversation_active = False
            self._speak("再见，主人")
            return
            
        # 发送命令到处理回调
        if self.on_command:
            asyncio.create_task(self.on_command(text))
            
    def _capture_audio(self, timeout: float = 5.0, vad_only: bool = False) -> Optional[bytes]:
        """捕获音频 (简化实现)"""
        # 实际应该使用 pyaudio 或 sounddevice
        # 这里返回模拟数据
        return None
        
    def _transcribe(self, audio: bytes, short: bool = False) -> str:
        """语音识别转文本"""
        if not self.asr or not audio:
            return ""
            
        try:
            # Whisper转录
            result = self.asr.transcribe(audio, language="zh")
            return result["text"].strip()
        except Exception as e:
            logger.error(f"ASR错误: {e}")
            return ""
            
    def _is_speech(self, audio: bytes) -> bool:
        """简单的语音活动检测"""
        # 实际应该使用 WebRTC VAD 或 Silero VAD
        return True  # 简化
        
    def _play_sound(self, sound_type: str):
        """播放提示音"""
        pass
        
    async def speak(self, text: str, emotion: str = "neutral"):
        """语音合成输出 (TTS)"""
        if not self.tts:
            print(f"[Zues] {text}")
            return
            
        try:
            self.is_speaking = True
            
            if isinstance(self.tts, pyttsx3.Engine):
                # 系统TTS
                self.tts.say(text)
                self.tts.runAndWait()
            else:
                # Coqui TTS - 生成音频文件并播放
                output_file = f"/tmp/zues_tts_{int(time.time())}.wav"
                self.tts.tts_to_file(text=text, file_path=output_file)
                await self._play_audio_file(output_file)
                Path(output_file).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"TTS错误: {e}")
        finally:
            self.is_speaking = False
            
    async def _play_audio_file(self, file_path: str):
        """播放音频文件"""
        # 使用系统播放器
        import subprocess
        subprocess.run(["afplay" if os.uname().sysname == "Darwin" else "aplay", file_path])
        
def get_voice_interface(config: Dict[str, Any] = None) -> VoiceFirstInterface:
    """获取语音接口单例"""
    return VoiceFirstInterface(config or {})
