"""
ZeusHammer Voice Wake Word System

语音唤醒 + 实时监听 + 声音记忆

功能:
1. 唤醒词检测 (Wake Word)
2. 实时麦克风监听
3. 语音转文字
4. 用户声音记忆
5. 安装后语音自我介绍
"""

import asyncio
import logging
import time
import struct
import hashlib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class WakeWordStatus(Enum):
    """唤醒状态"""
    IDLE = "idle"
    LISTENING = "listening"
    WAKE_DETECTED = "wake_detected"
    PROCESSING = "processing"


@dataclass
class VoiceProfile:
    """用户声音档案"""
    user_id: str
    name: str
    voice_hash: str  # 声音特征哈希
    embeddings: List[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    interaction_count: int = 0


class WakeWordDetector:
    """
    唤醒词检测器

    使用简单的能量检测 + 关键词匹配
    未来可升级为Porcupine等专业的唤醒词引擎
    """

    def __init__(
        self,
        wake_words: List[str] = None,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
    ):
        self.wake_words = wake_words or ["宙斯", "zues"]
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        # 音频参数
        self.energy_threshold = 500
        self.min_wake_duration = 0.3  # 秒
        self.silence_timeout = 2.0  # 秒

        # 状态
        self._status = WakeWordStatus.IDLE
        self._audio_buffer: List[bytes] = []
        self._silence_frames = 0

        # 回调
        self._on_wake_callback: Optional[Callable] = None

    def set_wake_callback(self, callback: Callable):
        """设置唤醒回调"""
        self._on_wake_callback = callback

    async def process_audio_chunk(self, audio_chunk: bytes) -> bool:
        """
        处理音频块

        Returns:
            True 如果检测到唤醒词
        """
        # 计算能量
        energy = self._calculate_energy(audio_chunk)

        # 能量检测
        if energy > self.energy_threshold:
            self._audio_buffer.append(audio_chunk)
            self._silence_frames = 0

            # 检查是否有足够的音频
            total_duration = len(self._audio_buffer) * self.chunk_size / self.sample_rate

            if total_duration >= self.min_wake_duration:
                # 提取音频并检测唤醒词
                audio_data = b"".join(self._audio_buffer)

                if self._detect_wake_word(audio_data):
                    self._status = WakeWordStatus.WAKE_DETECTED
                    logger.info("Wake word detected!")

                    # 调用回调
                    if self._on_wake_callback:
                        await self._on_wake_callback(audio_data)

                    # 清空缓冲区
                    self._audio_buffer = []
                    self._status = WakeWordStatus.IDLE
                    return True

        else:
            # 静音处理
            self._silence_frames += 1

            # 超时清空缓冲区
            total_duration = len(self._audio_buffer) * self.chunk_size / self.sample_rate
            if total_duration > self.silence_timeout:
                self._audio_buffer = []

        return False

    def _calculate_energy(self, audio_chunk: bytes) -> float:
        """计算音频能量"""
        if len(audio_chunk) < 2:
            return 0

        try:
            samples = struct.unpack("<" + "h" * (len(audio_chunk) // 2), audio_chunk)
            energy = sum(s * s for s in samples) / len(samples)
            return energy ** 0.5
        except Exception:
            return 0

    def _detect_wake_word(self, audio_data: bytes) -> bool:
        """检测唤醒词 (简化版，实际应该用ASR)"""
        # 这里简化处理，实际应该用Whisper或专门的唤醒词引擎
        # 暂时返回False，让VAD检测静默来触发

        # 检查能量是否持续高于阈值
        if len(self._audio_buffer) < 3:
            return False

        # 简单启发式：连续多帧高能量
        return True

    async def run(self, audio_source: Callable) -> asyncio.Future:
        """
        运行唤醒检测

        Args:
            audio_source: 返回音频数据的异步生成器
        """
        self._status = WakeWordStatus.LISTENING

        try:
            async for chunk in audio_source():
                detected = await self.process_audio_chunk(chunk)

                if detected:
                    logger.info("Wake word detected, triggering callback")

        except asyncio.CancelledError:
            self._status = WakeWordStatus.IDLE
            raise


class VoiceMemory:
    """
    用户声音记忆

    记住用户的声音特征
    """

    def __init__(self, memory_manager=None):
        self.memory = memory_manager
        self._profiles: Dict[str, VoiceProfile] = {}
        self._current_user: Optional[VoiceProfile] = None

        # 加载已有档案
        self._load_profiles()

    def _load_profiles(self):
        """加载声音档案"""
        if not self.memory:
            return

        try:
            # 从记忆系统加载
            profiles_data = self.memory.recall("voice_profiles")
            if profiles_data:
                for user_id, data in profiles_data.items():
                    self._profiles[user_id] = VoiceProfile(**data)
        except Exception:
            # 忽略加载错误（可能数据库只读）
            pass

    def _save_profiles(self):
        """保存声音档案"""
        if not self.memory:
            return

        profiles_data = {
            user_id: {
                "user_id": p.user_id,
                "name": p.name,
                "voice_hash": p.voice_hash,
                "embeddings": p.embeddings,
                "created_at": p.created_at,
                "last_seen": p.last_seen,
                "interaction_count": p.interaction_count,
            }
            for user_id, p in self._profiles.items()
        }

        self.memory.remember("voice_profiles", profiles_data)

    def register_user(
        self,
        user_id: str,
        name: str,
        audio_sample: bytes = None,
    ) -> VoiceProfile:
        """注册用户声音"""
        # 生成声音哈希
        voice_hash = self._generate_voice_hash(audio_sample or b"")

        profile = VoiceProfile(
            user_id=user_id,
            name=name,
            voice_hash=voice_hash,
        )

        self._profiles[user_id] = profile
        self._save_profiles()

        logger.info(f"Registered voice profile for: {name}")
        return profile

    def identify_user(self, audio_data: bytes) -> Optional[VoiceProfile]:
        """
        识别用户

        当前简化实现，未来可用声纹识别
        """
        # 简单实现：生成音频哈希并比较
        audio_hash = self._generate_voice_hash(audio_data)

        for profile in self._profiles.values():
            if profile.voice_hash == audio_hash:
                # 更新最后访问时间
                profile.last_seen = time.time()
                profile.interaction_count += 1
                self._current_user = profile
                self._save_profiles()
                return profile

        return None

    def get_current_user(self) -> Optional[VoiceProfile]:
        """获取当前用户"""
        return self._current_user

    def get_all_profiles(self) -> List[VoiceProfile]:
        """获取所有档案"""
        return list(self._profiles.values())

    def delete_profile(self, user_id: str):
        """删除档案"""
        if user_id in self._profiles:
            del self._profiles[user_id]
            self._save_profiles()

    def _generate_voice_hash(self, audio_data: bytes) -> str:
        """生成声音哈希"""
        if not audio_data:
            return hashlib.md5(str(time.time()).encode()).hexdigest()

        # 取音频的哈希
        return hashlib.md5(audio_data[:10000]).hexdigest()


class VoiceInteraction:
    """
    语音交互系统

    整合唤醒、监听、识别
    """

    def __init__(
        self,
        voice_config: Dict = None,
        memory_manager=None,
    ):
        config = voice_config or {}

        self.wake_words = config.get("wake_words", ["宙斯", "zues", "zueshammer"])
        self.sample_rate = config.get("sample_rate", 16000)

        # 组件
        self.wake_detector = WakeWordDetector(
            wake_words=self.wake_words,
            sample_rate=self.sample_rate,
        )

        self.voice_memory = VoiceMemory(memory_manager)

        # STT/TTS
        self._stt = None
        self._tts = None

        # 状态
        self._status = WakeWordStatus.IDLE
        self._listening = False
        self._running = False

        # 回调
        self._on_user_speak_callback: Optional[Callable] = None
        self._on_response_callback: Optional[Callable] = None

    def set_callbacks(
        self,
        on_user_speak: Callable = None,
        on_response: Callable = None,
    ):
        """设置回调"""
        self._on_user_speak_callback = on_user_speak
        self._on_response_callback = on_response

        # 设置唤醒回调
        self.wake_detector.set_wake_callback(self._on_wake_detected)

    async def _on_wake_detected(self, audio_data: bytes):
        """唤醒词检测到"""
        self._status = WakeWordStatus.WAKE_DETECTED
        logger.info("Wake word detected, ready to listen...")

        # 继续监听用户说话
        await self._listen_for_command(audio_data)

    async def _listen_for_command(self, wake_audio: bytes = None):
        """监听用户命令"""
        self._status = WakeWordStatus.LISTENING

        # 收集音频直到静音
        audio_chunks = [wake_audio] if wake_audio else []

        # 这里简化处理，实际应该持续监听
        # 并在检测到静音后进行ASR

    async def start_listening(self):
        """开始监听"""
        self._listening = True
        self._running = True
        self._status = WakeWordStatus.LISTENING

        logger.info("Voice listening started")

    async def stop_listening(self):
        """停止监听"""
        self._listening = False
        self._running = False
        self._status = WakeWordStatus.IDLE

        logger.info("Voice listening stopped")

    async def speech_to_text(self, audio_data: bytes) -> str:
        """语音转文字"""
        if not self._stt:
            # 延迟导入
            try:
                from ..voice.voice_system import WhisperSTT
                self._stt = WhisperSTT(self._get_voice_config())
            except Exception:
                logger.error("STT not available")
                return ""

        result = await self._stt.transcribe(audio_data)
        return result.get("text", "")

    async def text_to_speech(self, text: str, language: str = "zh") -> bytes:
        """文字转语音"""
        if not self._tts:
            try:
                from ..voice.voice_system import EdgeTTS
                self._tts = EdgeTTS(self._get_voice_config())
            except Exception:
                logger.error("TTS not available")
                return b""

        from ..voice.voice_system import Language
        lang = Language.CHINESE if language == "zh" else Language.ENGLISH

        return await self._tts.synthesize(text, lang)

    def _get_voice_config(self):
        """获取语音配置"""
        from ..voice.voice_system import VoiceConfig
        return VoiceConfig()

    def get_status(self) -> str:
        """获取状态"""
        return self._status.value

    def get_current_user(self) -> Optional[VoiceProfile]:
        """获取当前用户"""
        return self.voice_memory.get_current_user()


class VoiceManager:
    """
    语音管理器

    统一管理语音交互
    """

    def __init__(self, config: Dict = None, memory_manager=None):
        self.config = config or {}

        # 创建语音交互
        self.interaction = VoiceInteraction(
            voice_config=self.config,
            memory_manager=memory_manager,
        )

        # 音频捕获
        self._audio_capture = None
        self._capture_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """初始化"""
        logger.info("Initializing voice system...")

        # 初始化STT
        await self._init_stt()

        # 初始化TTS
        await self._init_tts()

        logger.info("Voice system initialized")

    async def _init_stt(self):
        """初始化STT"""
        try:
            from ..voice.voice_system import WhisperSTT
            voice_config = self._get_voice_config()
            self.interaction._stt = WhisperSTT(voice_config)
        except Exception as e:
            logger.warning(f"STT init failed: {e}")

    async def _init_tts(self):
        """初始化TTS"""
        try:
            from ..voice.voice_system import EdgeTTS
            voice_config = self._get_voice_config()
            self.interaction._tts = EdgeTTS(voice_config)
        except Exception as e:
            logger.warning(f"TTS init failed: {e}")

    async def start_voice_mode(self, agent):
        """
        启动语音模式

        Args:
            agent: ZeusHammer智能体
        """
        logger.info("Starting voice mode...")

        # 设置回调
        self.interaction.set_callbacks(
            on_user_speak=self._on_user_speak,
            on_response=self._on_response,
        )

        # 开始监听
        await self.interaction.start_listening()

        # 启动音频捕获循环
        self._capture_task = asyncio.create_task(self._capture_loop(agent))

        # 语音自我介绍
        await self._introduction(agent)

        logger.info("Voice mode started")

    async def stop_voice_mode(self):
        """停止语音模式"""
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass

        await self.interaction.stop_listening()

        logger.info("Voice mode stopped")

    async def _capture_loop(self, agent):
        """音频捕获循环"""
        try:
            import pyaudio

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )

            logger.info("Audio capture started")

            while self.interaction._running:
                try:
                    # 读取音频
                    audio_chunk = stream.read(1024, exception_on_overflow=False)

                    # 处理音频
                    detected = await self.interaction.wake_detector.process_audio_chunk(audio_chunk)

                    if detected:
                        # 唤醒词检测到，等待用户说完
                        command_audio = await self._capture_until_silence(stream)

                        if command_audio:
                            # 语音转文字
                            text = await self.interaction.speech_to_text(command_audio)

                            if text:
                                logger.info(f"User said: {text}")

                                # 检测用户语言
                                user_language = self._detect_language(text)
                                logger.info(f"Detected user language: {user_language}")

                                # 处理用户输入
                                response = await agent.process(text)

                                # 确定回复语言
                                response_language = user_language if user_language == "zh" else "en"

                                # 特殊回复处理：无模型/无记忆时
                                if not response or response.startswith("Error"):
                                    response = self._handle_no_model_memory(agent, user_language)

                                # 语音合成并播放
                                audio = await self.interaction.text_to_speech(response, language=response_language)
                                if audio:
                                    await self._play_audio(audio)

                except Exception as e:
                    logger.error(f"Capture error: {e}")

            stream.stop_stream()
            stream.close()
            p.terminate()

        except ImportError:
            logger.error("pyaudio not installed")
        except asyncio.CancelledError:
            if stream:
                stream.stop_stream()
                stream.close()
            if p:
                p.terminate()
            raise

    async def _capture_until_silence(self, stream, max_duration: float = 10.0) -> bytes:
        """捕获到静音"""
        chunks = []
        silence_threshold = 500
        silence_frames = 0
        max_silence_frames = 40  # 约2秒静音

        start = time.time()

        while True:
            # 超时检查
            if time.time() - start > max_duration:
                break

            # 读取音频
            chunk = stream.read(1024, exception_on_overflow=False)
            chunks.append(chunk)

            # 检查能量
            energy = self._calculate_energy(chunk)

            if energy < silence_threshold:
                silence_frames += 1
                if silence_frames > max_silence_frames:
                    break
            else:
                silence_frames = 0

        return b"".join(chunks)

    def _calculate_energy(self, audio_chunk: bytes) -> float:
        """计算音频能量"""
        if len(audio_chunk) < 2:
            return 0

        try:
            samples = struct.unpack("<" + "h" * (len(audio_chunk) // 2), audio_chunk)
            energy = sum(s * s for s in samples) / len(samples)
            return energy ** 0.5
        except Exception:
            return 0

    async def _on_user_speak(self, audio_data: bytes):
        """用户说话回调"""
        logger.info("User speaking...")

    async def _on_response(self, text: str):
        """响应回调"""
        logger.info(f"Response: {text}")

    def _detect_language(self, text: str) -> str:
        """
        检测文本语言
        
        通过中文字符数量比例来判断
        """
        if not text:
            return "en"
        
        chinese_chars = 0
        total_chars = 0
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
                chinese_chars += 1
            if char.isalpha():
                total_chars += 1
        
        if total_chars > 0 and chinese_chars / total_chars > 0.3:
            return "zh"
        return "en"

    def _handle_no_model_memory(self, agent, language: str) -> str:
        """
        处理无模型或无记忆的情况
        
        Args:
            agent: ZeusHammer智能体
            language: 用户语言
            
        Returns:
            合适的回复文本
        """
        has_model = self._check_llm_available(agent)
        has_memory = self._check_memory_available(agent)
        
        if language == "zh":
            if not has_model and not has_memory:
                return "抱歉，我目前没有记忆，请给我配置模型进行学习。"
            elif not has_model:
                return "抱歉，大模型暂时不可用，但我可以使用记忆库来帮助你。"
            else:
                return "抱歉，遇到了一些问题，请稍后再试。"
        else:
            if not has_model and not has_memory:
                return "I currently don't have any memories. Please configure a language model so I can learn and assist you better."
            elif not has_model:
                return "Sorry, the language model is currently unavailable, but I can use my memory to help you."
            else:
                return "Sorry, I encountered an issue. Please try again later."

    async def _play_audio(self, audio_data: bytes):
        """播放音频"""
        try:
            import pyaudio
            import wave
            import io

            # 解码MP3
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
                raw_data = audio.raw_data
                sample_rate = audio.frame_rate
            except Exception:
                raw_data = audio_data
                sample_rate = 16000

            # 播放
            p = pyaudio.PyAudio()
            stream = p.open(
                format=p.get_format_from_width(2),
                channels=1,
                rate=sample_rate,
                output=True,
            )

            stream.write(raw_data)
            stream.stop_stream()
            stream.close()
            p.terminate()

        except ImportError:
            logger.warning("Audio playback not available")
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")

    async def _introduction(self, agent):
        """
        自我介绍 - 中英双语
        
        根据是否有模型和记忆来决定自我介绍内容
        """
        # 检查模型和记忆状态
        has_model = self._check_llm_available(agent)
        has_memory = self._check_memory_available(agent)
        
        # 生成自我介绍（英文为主，如果检测到中文用户则切换）
        intro = self._generate_introduction(has_model, has_memory)
        
        logger.info(f"Introduction generated (model={has_model}, memory={has_memory})")
        
        # 语音合成（默认英文）
        audio = await self.interaction.text_to_speech(intro, language="en")
        
        if audio:
            await self._play_audio(audio)
            logger.info("Introduction played")
        
        return intro

    def _check_llm_available(self, agent) -> bool:
        """检查大模型是否可用"""
        try:
            if hasattr(agent, 'llm') and agent.llm:
                api_key = getattr(agent.llm, 'api_key', None)
                return api_key is not None and api_key != ""
            return False
        except Exception:
            return False

    def _check_memory_available(self, agent) -> bool:
        """检查记忆系统是否有数据"""
        try:
            if hasattr(agent, 'memory') and agent.memory:
                # 检查短期和长期记忆
                short_keys = self.interaction.voice_memory.memory.short_term.keys()
                long_stats = self.interaction.voice_memory.memory.long_term.get_stats()
                total_memories = long_stats.get('total_memories', 0)
                return len(short_keys) > 0 or total_memories > 0
            return False
        except Exception:
            return False

    def _generate_introduction(self, has_model: bool, has_memory: bool) -> str:
        """
        生成自我介绍内容（英文为主）
        
        逻辑：
        - 有模型 + 有记忆：完整自我介绍
        - 有模型 + 无记忆：提示配置
        - 无模型 + 有记忆：使用记忆库回复
        - 无模型 + 无记忆：提示配置模型
        """
        if has_model and has_memory:
            return (
                "Hello! I am Zues, your AI super assistant. "
                "I can understand your intentions and match them with the right skills. "
                "If I don't have a matching skill, I will use my memory to help you. "
                "If needed, I will call the large language model to work for you. "
                "After completing a task, I will learn and store the new skill. "
                "Next time you ask a similar question, I can answer directly! "
                "You can talk to me by voice. Just say ZUES or ZHE SI to wake me up. "
                "What can I help you with today?"
            )
        elif has_model and not has_memory:
            return (
                "Hello! I am Zues, your AI super assistant. "
                "I am ready to help you. "
                "I can call the large language model to assist you with any task. "
                "After we work together, I will learn and remember your preferences. "
                "You can talk to me by voice. Just say ZUES or ZHE SI to wake me up. "
                "What can I help you with today?"
            )
        elif not has_model and has_memory:
            return (
                "Hello! I am Zues, your AI super assistant. "
                "I currently don't have access to the language model, but I have memories from our previous conversations. "
                "I can use my memory to help you with tasks. "
                "You can talk to me by voice. Just say ZUES or ZHE SI to wake me up. "
                "What can I help you with today?"
            )
        else:
            # 无模型 + 无记忆
            return (
                "Hello! I am Zues, your AI super assistant. "
                "I currently don't have any memories. "
                "Please configure a language model so I can learn and assist you better. "
                "You can talk to me by voice. Just say ZUES or ZHE SI to wake me up. "
                "What can I help you with?"
            )

    def _generate_introduction_chinese(self, has_model: bool, has_memory: bool) -> str:
        """
        生成中文自我介绍（用于中文用户）
        """
        if has_model and has_memory:
            return (
                "你好！我是宙斯，你的超级助手。"
                "我可以理解你的意图并匹配合适的技能。"
                "如果找不到技能，我会使用记忆库来帮助你。"
                "必要时，我会调用大模型来工作。"
                "完成工作后，我会学习并存储新的技能。"
                "下次你问类似的问题，我可以直接回答！"
                "你可以用语音和我对话，只需说「宙斯」或「ZUES」来唤醒我。"
                "有什么我可以帮你的吗？"
            )
        elif has_model and not has_memory:
            return (
                "你好！我是宙斯，你的超级助手。"
                "我已经准备好帮助你。"
                "我可以调用大模型来协助你完成任何任务。"
                "我们一起工作后，我会学习和记住你的偏好。"
                "你可以用语音和我对话，只需说「宙斯」或「ZUES」来唤醒我。"
                "有什么我可以帮你的吗？"
            )
        elif not has_model and has_memory:
            return (
                "你好！我是宙斯，你的超级助手。"
                "我目前无法访问大模型，但我有我们之前对话的记忆。"
                "我可以使用记忆库来帮助你完成任务。"
                "你可以用语音和我对话，只需说「宙斯」或「ZUES」来唤醒我。"
                "有什么我可以帮你的吗？"
            )
        else:
            # 无模型 + 无记忆
            return (
                "你好！我是宙斯，你的超级助手。"
                "我目前没有记忆，请给我配置模型进行学习。"
                "你可以用语音和我对话，只需说「宙斯」或「ZUES」来唤醒我。"
                "有什么我可以帮你的吗？"
            )

    def _get_voice_config(self) -> Dict:
        """获取语音配置"""
        return self.config


# 全局实例
_voice_manager: Optional[VoiceManager] = None


def get_voice_manager(config: Dict = None, memory_manager=None) -> VoiceManager:
    """获取语音管理器"""
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager(config, memory_manager)
    return _voice_manager
