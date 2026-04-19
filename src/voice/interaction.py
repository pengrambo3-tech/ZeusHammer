"""
ZeusHammer Voice System

Voice interaction with Chinese/English recognition.
- Speech recognition (STT)
- Text-to-speech (TTS)
- Language detection for auto-switching
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Language(Enum):
    """Supported languages"""
    CHINESE = "zh"
    ENGLISH = "en"
    UNKNOWN = "unknown"


@dataclass
class VoiceConfig:
    """Voice configuration"""
    # STT settings
    stt_provider: str = "auto"  # auto, google, whisper, azure
    stt_language: str = "auto"  # auto-detect, zh-CN, en-US

    # TTS settings
    tts_provider: str = "auto"  # auto, google, edge, elevenlabs
    tts_voice: str = "default"
    tts_speed: float = 1.0
    tts_pitch: float = 1.0

    # Language detection
    auto_detect_language: bool = True
    response_in_user_language: bool = True


@dataclass
class VoiceMessage:
    """Voice message"""
    text: str
    language: Language
    confidence: float = 1.0
    raw_audio: bytes = None


class LanguageDetector:
    """
    Detect language from text.
    Simple rule-based + statistical approach.
    """

    # Chinese character ranges
    CHINESE_CHARS = range(0x4E00, 0x9FFF)
    CHINESE_PUNCTUATION = "，。！？；：""''（）【】《》"

    # Common Chinese words
    CHINESE_WORDS = {
        "的", "是", "我", "你", "他", "她", "它", "们", "这", "那",
        "什么", "怎么", "为什么", "哪里", "谁", "多少", "几",
        "好", "不", "很", "都", "也", "就", "还", "在", "有",
        "可以", "请", "帮", "做", "到", "来", "去", "说",
        "想", "知道", "觉得", "希望", "需要", "能够",
        "你好", "谢谢", "再见", "早上好", "晚上好",
        "执行", "运行", "打开", "关闭", "删除", "创建",
        "文件", "目录", "命令", "程序", "代码",
    }

    # Common English words
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
        """
        Detect language from text.

        Uses character counting and word matching.
        """
        if not text or len(text.strip()) == 0:
            return Language.UNKNOWN

        # Count Chinese characters
        chinese_count = 0
        for char in text:
            if ord(char) in self.CHINESE_CHARS or char in self.CHINESE_PUNCTUATION:
                chinese_count += 1

        # Count Chinese words
        chinese_word_count = sum(1 for word in self.CHINESE_WORDS if word in text.lower())
        english_word_count = sum(1 for word in self.ENGLISH_WORDS if word in text.lower())

        # Calculate scores
        chinese_score = chinese_count * 2 + chinese_word_count * 3
        english_score = english_word_count * 2

        # Decision
        if chinese_score > english_score * 1.5:
            return Language.CHINESE
        elif english_score > chinese_score * 1.5:
            return Language.ENGLISH
        else:
            # Fallback to character-based detection
            total_chars = len(text.replace(" ", ""))
            if total_chars > 0:
                chinese_ratio = chinese_count / total_chars
                if chinese_ratio > 0.3:
                    return Language.CHINESE
                elif chinese_ratio < 0.1:
                    return Language.ENGLISH

        return Language.ENGLISH  # Default to English

    def detect_with_confidence(self, text: str) -> tuple:
        """Detect with confidence score"""
        lang = self.detect(text)

        # Calculate confidence
        chinese_count = sum(1 for char in text if ord(char) in self.CHINESE_CHARS)
        english_count = sum(1 for c in text if c.isascii() and c.isalpha())
        total = chinese_count + english_count

        if total > 0:
            if lang == Language.CHINESE:
                confidence = chinese_count / total
            else:
                confidence = english_count / total
        else:
            confidence = 0.5

        return lang, confidence


class SpeechRecognizer:
    """
    Speech-to-text converter.

    Supports multiple backends:
    - whisper (local, most accurate)
    - google (cloud)
    - azure (cloud)
    """

    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()
        self._detector = LanguageDetector()
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if STT is available"""
        # Check for whisper
        try:
            import whisper
            logger.info("Whisper STT available")
            return True
        except ImportError:
            pass

        # Check for speech_recognition
        try:
            import speech_recognition
            logger.info("SpeechRecognition available")
            return True
        except ImportError:
            pass

        logger.warning("No STT library available")
        return False

    async def recognize(self, audio_data: bytes, language: str = "auto") -> Optional[VoiceMessage]:
        """
        Convert speech to text.

        Args:
            audio_data: Raw audio bytes (16-bit PCM recommended)
            language: Language hint (auto, zh-CN, en-US)

        Returns:
            VoiceMessage with recognized text
        """
        if not self._available:
            logger.error("STT not available")
            return None

        try:
            # Try whisper first (local, accurate)
            text = await self._recognize_whisper(audio_data, language)
            if text:
                detected_lang = self._detector.detect(text)
                return VoiceMessage(
                    text=text,
                    language=detected_lang,
                    confidence=0.95,
                    raw_audio=audio_data
                )

        except Exception as e:
            logger.error(f"Whisper recognition failed: {e}")

        return None

    async def _recognize_whisper(self, audio_data: bytes, language: str) -> Optional[str]:
        """Use Whisper for recognition"""
        try:
            import whisper
            import tempfile
            import wave

            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                # Write WAV header
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    wav_file.writeframes(audio_data)

            # Load model (use base for speed)
            model = whisper.load_model("base")

            # Transcribe
            result = model.transcribe(temp_path, language=None if language == "auto" else language)

            # Cleanup
            import os
            os.unlink(temp_path)

            return result.get("text", "").strip()

        except Exception as e:
            logger.error(f"Whisper error: {e}")
            return None


class TextToSpeech:
    """
    Text-to-speech converter.

    Supports multiple backends:
    - edge (Microsoft Edge TTS, free, good quality)
    - google (Google TTS, cloud)
    - elevenlabs (paid, high quality)
    """

    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()
        self._detector = LanguageDetector()
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if TTS is available"""
        try:
            import edge_tts
            logger.info("Edge TTS available")
            return True
        except ImportError:
            pass

        try:
            import gtts
            logger.info("gTTS available")
            return True
        except ImportError:
            pass

        logger.warning("No TTS library available")
        return False

    async def speak(self, text: str, language: Language = None) -> Optional[bytes]:
        """
        Convert text to speech.

        Args:
            text: Text to speak
            language: Target language (auto-detect if None)

        Returns:
            Audio bytes (MP3/WAV)
        """
        if not self._available:
            logger.error("TTS not available")
            return None

        # Auto-detect language
        if language is None:
            language = self._detector.detect(text)

        try:
            # Try Edge TTS first
            audio = await self._speak_edge(text, language)
            if audio:
                return audio

            # Fallback to gTTS
            audio = await self._speak_gtts(text, language)
            if audio:
                return audio

        except Exception as e:
            logger.error(f"TTS error: {e}")

        return None

    async def _speak_edge(self, text: str, language: Language) -> Optional[bytes]:
        """Use Edge TTS"""
        try:
            import edge_tts
            import tempfile

            # Map language to voice
            voice_map = {
                Language.CHINESE: "zh-CN-XiaoxiaoNeural",
                Language.ENGLISH: "en-US-JennyNeural",
            }
            voice = voice_map.get(language, "en-US-JennyNeural")

            # Generate audio
            communicate = edge_tts.Communicate(text, voice)
            audio_data = b""

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            return audio_data if audio_data else None

        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return None

    async def _speak_gtts(self, text: str, language: Language) -> Optional[bytes]:
        """Use gTTS"""
        try:
            from gtts import gTTS
            import io

            lang_map = {
                Language.CHINESE: "zh-CN",
                Language.ENGLISH: "en",
            }
            lang = lang_map.get(language, "en")

            # Generate audio
            tts = gTTS(text=text, lang=lang, slow=False)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)

            return audio_buffer.read()

        except Exception as e:
            logger.error(f"gTTS error: {e}")
            return None


class VoiceInteraction:
    """
    Main voice interaction handler.

    Coordinates STT, TTS, and language detection.
    """

    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()
        self.stt = SpeechRecognizer(config)
        self.tts = TextToSpeech(config)
        self.detector = LanguageDetector()

    async def process_voice_input(self, audio_data: bytes) -> Optional[VoiceMessage]:
        """Process voice input and return text"""
        return await self.stt.recognize(audio_data, self.config.stt_language)

    async def generate_voice_response(self, text: str, user_language: Language = None) -> Optional[bytes]:
        """Generate voice response"""
        return await self.tts.speak(text, user_language)

    async def voice_loop(self, audio_callback: Callable, playback_callback: Callable):
        """
        Main voice interaction loop.

        Args:
            audio_callback: Async function to get audio input
            playback_callback: Async function to play audio output
        """
        logger.info("Starting voice loop...")

        while True:
            try:
                # Get audio input
                audio_data = await audio_callback()
                if audio_data is None:
                    break

                # Recognize speech
                voice_msg = await self.process_voice_input(audio_data)
                if voice_msg is None:
                    await playback_callback(b"")  # Silence
                    continue

                # Check for exit
                if voice_msg.text.lower() in ["exit", "quit", "再见", "退出"]:
                    farewell = "Goodbye!" if voice_msg.language == Language.ENGLISH else "再见！"
                    audio = await self.generate_voice_response(farewell, voice_msg.language)
                    if audio:
                        await playback_callback(audio)
                    break

                # Return voice message for processing
                yield voice_msg

            except Exception as e:
                logger.error(f"Voice loop error: {e}")
                break

    def get_response_language(self, user_text: str, response_text: str) -> Language:
        """
        Determine response language.

        If response_in_user_language is True, respond in user's language.
        Otherwise, respond in the language of the response text.
        """
        if self.config.response_in_user_language:
            return self.detector.detect(user_text)
        return self.detector.detect(response_text)


# Global voice instance
_voice_instance: Optional[VoiceInteraction] = None


def get_voice(config: VoiceConfig = None) -> VoiceInteraction:
    """Get or create voice interaction instance"""
    global _voice_instance
    if _voice_instance is None:
        _voice_instance = VoiceInteraction(config)
    return _voice_instance
