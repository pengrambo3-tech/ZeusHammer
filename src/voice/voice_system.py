"""
ZeusHammer Complete Voice System

完整语音交互模块:
1. Whisper语音识别 (本地)
2. Edge TTS语音合成
3. 语音活动检测 (VAD)
4. 多语言支持
5. 音频处理
"""

import asyncio
import logging
import wave
import struct
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Language(Enum):
    """支持的语言"""
    CHINESE = "zh"
    ENGLISH = "en"
    JAPANESE = "ja"
    KOREAN = "ko"
    UNKNOWN = "unknown"


@dataclass
class VoiceConfig:
    """语音配置"""
    # STT
    stt_provider: str = "whisper"  # whisper, google, azure
    stt_model: str = "base"  # tiny, base, small, medium, large
    stt_language: str = "auto"

    # TTS
    tts_provider: str = "edge"  # edge, google, elevenlabs
    tts_voice_zh: str = "zh-CN-XiaoxiaoNeural"
    tts_voice_en: str = "en-US-JennyNeural"
    tts_speed: float = 1.0
    tts_pitch: float = 1.0

    # 音频
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024


class LanguageDetector:
    """
    语言检测器

    基于字符和词频统计
    """

    # 中文字符范围
    CHINESE_RANGE = (0x4E00, 0x9FFF)

    # 常用中文词
    CHINESE_WORDS = {
        "的", "是", "我", "你", "他", "她", "它", "们", "这", "那",
        "什么", "怎么", "为什么", "哪里", "谁", "多少",
        "好", "不", "很", "都", "也", "就", "还", "在", "有",
        "可以", "请", "帮", "做", "到", "来", "去", "说",
        "想", "知道", "觉得", "希望", "需要", "能够",
        "你好", "谢谢", "再见", "早上好", "晚上好",
        "执行", "运行", "打开", "关闭", "删除", "创建",
        "文件", "目录", "命令", "程序", "代码",
    }

    # 常用英文词
    ENGLISH_WORDS = {
        "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must",
        "i", "you", "he", "she", "it", "we", "they",
        "this", "that", "these", "those",
        "what", "which", "who", "whom", "where", "when", "why", "how",
        "please", "thanks", "thank", "sorry", "hello", "goodbye",
        "execute", "run", "open", "close", "delete", "create",
        "file", "directory", "command", "program", "code",
    }

    def detect(self, text: str) -> Language:
        """检测语言"""
        if not text or len(text.strip()) == 0:
            return Language.UNKNOWN

        # 统计中文字符
        chinese_count = sum(
            1 for char in text
            if 0x4E00 <= ord(char) <= 0x9FFF
        )

        # 统计ASCII字符
        ascii_count = sum(1 for c in text if c.isascii() and c.isalpha())

        # 统计词频
        text_lower = text.lower()
        chinese_word_count = sum(1 for w in self.CHINESE_WORDS if w in text_lower)
        english_word_count = sum(1 for w in self.ENGLISH_WORDS if w in text_lower)

        # 计算分数
        chinese_score = chinese_count * 2 + chinese_word_count * 3
        english_score = english_word_count * 2

        # 判定
        if chinese_score > english_score * 1.5:
            return Language.CHINESE
        elif english_score > chinese_score * 1.5:
            return Language.ENGLISH

        # 回退到字符比例
        total = chinese_count + ascii_count
        if total > 0:
            ratio = chinese_count / total
            if ratio > 0.3:
                return Language.CHINESE
            elif ratio < 0.1:
                return Language.ENGLISH

        return Language.ENGLISH

    def detect_with_confidence(self, text: str) -> tuple:
        """检测语言并返回置信度"""
        lang = self.detect(text)

        chinese_count = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
        ascii_count = sum(1 for c in text if c.isascii() and c.isalpha())

        total = chinese_count + ascii_count
        if total > 0:
            if lang == Language.CHINESE:
                confidence = chinese_count / total
            else:
                confidence = ascii_count / total
        else:
            confidence = 0.5

        return lang, confidence


class WhisperSTT:
    """
    Whisper语音识别 (本地)

    支持模型: tiny, base, small, medium, large
    """

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._model = None

    async def initialize(self):
        """初始化模型"""
        try:
            import whisper

            logger.info(f"Loading Whisper model: {self.config.stt_model}")
            self._model = whisper.load_model(self.config.stt_model)
            logger.info("Whisper model loaded")

        except ImportError:
            logger.error("Whisper not installed: pip install openai-whisper")
            raise

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = None,
    ) -> Dict:
        """
        转录音频

        Args:
            audio_data: WAV格式音频数据
            language: 语言代码 (zh, en, auto)

        Returns:
            {"text": str, "language": str, "segments": [...]}
        """
        if not self._model:
            await self.initialize()

        # 保存临时文件
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            # 写入WAV
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(self.config.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.config.sample_rate)
                wav_file.writeframes(audio_data)

        try:
            # 转录
            options = {}
            if language and language != "auto":
                options["language"] = language

            result = self._model.transcribe(temp_path, **options)

            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", []),
                "duration": result.get("duration", 0),
            }

        finally:
            # 清理
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    async def transcribe_file(self, file_path: str) -> Dict:
        """转录音频文件"""
        if not self._model:
            await self.initialize()

        result = self._model.transcribe(
            file_path,
            language=None if self.config.stt_language == "auto" else self.config.stt_language,
        )

        return {
            "text": result.get("text", "").strip(),
            "language": result.get("language", "unknown"),
            "segments": result.get("segments", []),
            "duration": result.get("duration", 0),
        }


class EdgeTTS:
    """
    Edge TTS语音合成

    免费、高质量的语音合成
    """

    def __init__(self, config: VoiceConfig):
        self.config = config

    async def synthesize(
        self,
        text: str,
        language: Language = Language.ENGLISH,
        output_path: str = None,
    ) -> bytes:
        """
        合成语音

        Args:
            text: 要合成的文本
            language: 语言
            output_path: 输出文件路径

        Returns:
            MP3音频数据
        """
        try:
            import edge_tts

            # 选择语音
            voice = (
                self.config.tts_voice_zh
                if language == Language.CHINESE
                else self.config.tts_voice_en
            )

            # 生成音频
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=f"+{int((self.config.tts_speed - 1) * 100)}%",
                pitch=f"+{int((self.config.tts_pitch - 1) * 50)}Hz",
            )

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            # 保存文件
            if output_path:
                with open(output_path, "wb") as f:
                    f.write(audio_data)

            return audio_data

        except ImportError:
            logger.error("edge-tts not installed: pip install edge-tts")
            raise


class VoiceActivityDetector:
    """
    语音活动检测 (VAD)

    检测何时有人说话
    """

    def __init__(self, threshold: float = 0.5, min_speech_duration: float = 0.3):
        self.threshold = threshold
        self.min_speech_duration = min_speech_duration
        self._speaking = False
        self._speech_start = 0

    def detect(self, audio_chunk: bytes) -> bool:
        """
        检测语音活动

        Returns:
            True 如果检测到语音
        """
        import struct

        # 计算RMS
        if len(audio_chunk) < 2:
            return False

        # 解码音频样本
        try:
            samples = struct.unpack("<" + "h" * (len(audio_chunk) // 2), audio_chunk)
        except Exception:
            return False

        if not samples:
            return False

        # 计算RMS
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        normalized = min(rms / 32768, 1.0)

        return normalized > self.threshold


class AudioCapture:
    """
    音频捕获

    从麦克风捕获音频
    """

    def __init__(self, config: VoiceConfig):
        self.config = config
        self._stream = None

    async def open(self):
        """打开音频流"""
        try:
            import pyaudio

            self._pyaudio = pyaudio.PyAudio()

            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
            )

            logger.info("Audio stream opened")

        except ImportError:
            logger.error("pyaudio not installed: pip install pyaudio")
            raise

    def read(self, chunk_size: int = None) -> bytes:
        """读取音频数据"""
        if not self._stream:
            return b""

        size = chunk_size or self.config.chunk_size
        return self._stream.read(size, exception_on_overflow=False)

    def close(self):
        """关闭音频流"""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        if self._pyaudio:
            self._pyaudio.terminate()
            self._pyaudio = None


class VoiceInteraction:
    """
    语音交互系统

    整合STT、TTS和VAD
    """

    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()

        # 组件
        self.stt = WhisperSTT(self.config)
        self.tts = EdgeTTS(self.config)
        self.vad = VoiceActivityDetector()
        self.lang_detector = LanguageDetector()

        # 状态
        self._initialized = False

    async def initialize(self):
        """初始化"""
        if self._initialized:
            return

        await self.stt.initialize()
        self._initialized = True

    async def speech_to_text(self, audio_data: bytes) -> Dict:
        """
        语音转文字

        Args:
            audio_data: WAV格式音频数据

        Returns:
            {"text": str, "language": Language, "confidence": float}
        """
        if not self._initialized:
            await self.initialize()

        result = await self.stt.transcribe(
            audio_data,
            language=self.config.stt_language,
        )

        text = result.get("text", "")
        detected_lang = self.lang_detector.detect(text)
        _, confidence = self.lang_detector.detect_with_confidence(text)

        return {
            "text": text,
            "language": detected_lang,
            "confidence": confidence,
        }

    async def text_to_speech(
        self,
        text: str,
        language: Language = None,
        output_path: str = None,
    ) -> bytes:
        """
        文字转语音

        Args:
            text: 要合成的文本
            language: 语言 (自动检测如果不指定)
            output_path: 输出文件路径

        Returns:
            MP3音频数据
        """
        # 自动检测语言
        if language is None:
            language = self.lang_detector.detect(text)
            if language == Language.UNKNOWN:
                language = Language.ENGLISH

        return await self.tts.synthesize(text, language, output_path)

    async def process_voice_input(
        self,
        audio_callback: Callable,
        silence_threshold: float = 2.0,
    ) -> Optional[Dict]:
        """
        处理语音输入

        等待用户说话，检测静音后转录

        Args:
            audio_callback: 获取音频数据的回调
            silence_threshold: 静音阈值(秒)

        Returns:
            转录结果或None
        """
        import time

        audio_buffer = []
        silence_duration = 0
        speaking = False
        chunk_duration = self.config.chunk_size / self.config.sample_rate

        while True:
            chunk = await audio_callback()
            if chunk is None:
                break

            # VAD检测
            is_speech = self.vad.detect(chunk)

            if is_speech:
                speaking = True
                silence_duration = 0
                audio_buffer.append(chunk)
            elif speaking:
                silence_duration += chunk_duration
                audio_buffer.append(chunk)

                # 检测到静音结束
                if silence_duration >= silence_threshold:
                    break

        if not audio_buffer:
            return None

        # 合并音频
        audio_data = b"".join(audio_buffer)

        # 转录
        return await self.speech_to_text(audio_data)


class AudioPlayer:
    """音频播放器"""

    def __init__(self):
        self._pyaudio = None

    async def play_mp3(self, mp3_data: bytes):
        """播放MP3"""
        try:
            import pydub
            import io

            # 转换MP3为原始音频
            audio = pydub.AudioSegment.from_mp3(io.BytesIO(mp3_data))

            if not self._pyaudio:
                import pyaudio
                self._pyaudio = pyaudio.PyAudio()

            # 播放
            stream = self._pyaudio.open(
                format=self._pyaudio.get_format_from_width(audio.sample_width),
                channels=audio.channels,
                rate=audio.frame_rate,
                output=True,
            )

            stream.write(audio.raw_data)
            stream.stop_stream()
            stream.close()

        except ImportError as e:
            logger.error(f"Missing library: {e}")

    async def play_wav(self, wav_data: bytes):
        """播放WAV"""
        if not self._pyaudio:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()

        # 解析WAV
        with wave.open(io.BytesIO(wav_data), 'rb') as wav:
            stream = self._pyaudio.open(
                format=self._pyaudio.get_format_from_width(wav.getsampwidth()),
                channels=wav.getnchannels(),
                rate=wav.getframerate(),
                output=True,
            )

            stream.write(wav.readframes(wav.getnframes()))
            stream.stop_stream()
            stream.close()


import io
