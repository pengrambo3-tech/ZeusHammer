"""
ZeusHammer Web UI Server

Web界面 + 实时语音交互
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logger = logging.getLogger(__name__)

# 尝试导入，失败时提供友好的错误信息
try:
    from fastapi import FastAPI
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class ZeusHammerUI:
    """ZeusHammer Web UI"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.app = None
        self._connected_clients: list = []
        self._voice_mode = False
        self._wake_word = "宙斯"
        self._agent = None

    def set_agent(self, agent):
        """设置智能体"""
        self._agent = agent

    async def start(self):
        """启动UI服务器"""
        if not HAS_FASTAPI:
            logger.error("FastAPI not installed. Run: pip install fastapi uvicorn")
            return

        self.app = FastAPI(title="ZeusHammer", version="2.0.0")

        # 挂载静态文件
        static_path = Path(__file__).parent / "static"
        if static_path.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

        # WebSocket端点
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self._connected_clients.append(websocket)

            try:
                while True:
                    data = await websocket.receive_json()

                    if data.get("type") == "message":
                        # 处理用户消息
                        message = data.get("content", "")

                        if self._agent:
                            response = await self._agent.process(message)

                            # 发送响应
                            await websocket.send_json({
                                "type": "response",
                                "content": response,
                            })

                    elif data.get("type") == "voice":
                        # 处理语音输入
                        audio_data = data.get("audio")

                        if self._agent and self._agent.voice:
                            # 语音转文字
                            text = await self._agent.voice.speech_to_text(audio_data)

                            if text:
                                # 处理消息
                                response = await self._agent.process(text)

                                # 语音合成
                                audio = await self._agent.voice.text_to_speech(response)

                                await websocket.send_json({
                                    "type": "voice_response",
                                    "text": response,
                                    "audio": audio,
                                })

            except WebSocketDisconnect:
                self._connected_clients.remove(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

        # 主页面
        @self.app.get("/")
        async def index():
            return HTMLResponse(content=self._get_html(), media_type="text/html")

        # API端点
        @self.app.get("/api/status")
        async def status():
            return JSONResponse({
                "status": "running",
                "voice_mode": self._voice_mode,
                "wake_word": self._wake_word,
                "skills": len(self._agent.brain._skills) if self._agent else 0,
            })

        @self.app.get("/api/skills")
        async def skills():
            if not self._agent:
                return JSONResponse({"skills": []})
            return JSONResponse({
                "skills": [
                    {
                        "name": s.name,
                        "usage_count": s.usage_count,
                        "success_count": s.success_count,
                    }
                    for s in self._agent.brain._skills.values()
                ]
            })

        @self.app.get("/api/stats")
        async def stats():
            if not self._agent:
                return JSONResponse({})
            return JSONResponse(self._agent.get_stats())

        @self.app.post("/api/voice/wake-word")
        async def set_wake_word(request: Request):
            data = await request.json()
            self._wake_word = data.get("wake_word", "宙斯")
            return JSONResponse({"success": True, "wake_word": self._wake_word})

        @self.app.post("/api/voice/enable")
        async def enable_voice():
            self._voice_mode = True
            return JSONResponse({"success": True, "voice_mode": True})

        @self.app.post("/api/voice/disable")
        async def disable_voice():
            self._voice_mode = False
            return JSONResponse({"success": True, "voice_mode": False})

        # 权限管理API
        @self.app.get("/api/permission")
        async def get_permission():
            """获取当前权限级别"""
            from src.core.permission_manager import get_permission_manager
            pm = get_permission_manager()
            return JSONResponse(pm.get_status())

        @self.app.post("/api/permission")
        async def set_permission(request: Request):
            """设置权限级别"""
            from src.core.permission_manager import get_permission_manager, PermissionLevel
            data = await request.json()
            level = data.get("level", "semi_open")

            pm = get_permission_manager()
            success = pm.switch_level(level)

            return JSONResponse({
                "success": success,
                "level": pm.level.value,
                "description": pm.level.description,
            })

        @self.app.get("/api/permission/history")
        async def permission_history():
            """获取权限历史"""
            from src.core.permission_manager import get_permission_manager
            pm = get_permission_manager()
            return JSONResponse({"history": pm.get_history()})

        @self.app.post("/api/permission/confirm")
        async def confirm_operation(request: Request):
            """确认操作"""
            from src.core.permission_manager import get_permission_manager
            data = await request.json()
            operation = data.get("operation", "")
            details = data.get("details", {})

            pm = get_permission_manager()
            result = pm.check(operation, details)

            return JSONResponse({
                "allowed": result.allowed,
                "reason": result.reason,
            })

        # 启动服务器
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        logger.info(f"ZeusHammer UI started on http://{self.host}:{self.port}")
        await server.serve()

    def _get_html(self) -> str:
        """生成HTML页面"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZeusHammer - 宙斯之锤</title>
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --bg: #0f172a;
            --bg-card: #1e293b;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --success: #22c55e;
            --danger: #ef4444;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            padding: 1.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            font-size: 2rem;
        }

        .logo h1 {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .logo span {
            opacity: 0.8;
            font-size: 0.875rem;
        }

        .status {
            display: flex;
            gap: 1rem;
            align-items: center;
        }

        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        main {
            flex: 1;
            display: grid;
            grid-template-columns: 1fr 320px;
            gap: 1.5rem;
            padding: 1.5rem 2rem;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        .chat-container {
            background: var(--bg-card);
            border-radius: 1rem;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .chat-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-weight: 600;
        }

        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .message {
            max-width: 80%;
            padding: 1rem 1.25rem;
            border-radius: 1rem;
            line-height: 1.6;
        }

        .message.user {
            background: var(--primary);
            align-self: flex-end;
            border-bottom-right-radius: 0.25rem;
        }

        .message.assistant {
            background: rgba(255,255,255,0.1);
            align-self: flex-start;
            border-bottom-left-radius: 0.25rem;
        }

        .message .time {
            font-size: 0.75rem;
            opacity: 0.7;
            margin-top: 0.5rem;
        }

        .chat-input-container {
            padding: 1rem 1.5rem;
            border-top: 1px solid rgba(255,255,255,0.1);
            display: flex;
            gap: 0.75rem;
        }

        .chat-input {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: none;
            padding: 0.875rem 1.25rem;
            border-radius: 9999px;
            color: var(--text);
            font-size: 1rem;
            outline: none;
        }

        .chat-input:focus {
            background: rgba(255,255,255,0.15);
        }

        .chat-input::placeholder {
            color: var(--text-muted);
        }

        .btn {
            padding: 0.875rem 1.5rem;
            border: none;
            border-radius: 9999px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
            transform: translateY(-1px);
        }

        .btn-voice {
            background: var(--success);
            color: white;
            width: 48px;
            height: 48px;
            padding: 0;
            justify-content: center;
            border-radius: 50%;
        }

        .btn-voice.listening {
            background: var(--danger);
            animation: pulse 1s infinite;
        }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        .card {
            background: var(--bg-card);
            border-radius: 1rem;
            overflow: hidden;
        }

        .card-header {
            padding: 1rem 1.25rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-body {
            padding: 1rem 1.25rem;
        }

        .skill-item {
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .skill-item:last-child {
            border-bottom: none;
        }

        .skill-name {
            font-weight: 500;
        }

        .skill-count {
            color: var(--text-muted);
            font-size: 0.875rem;
        }

        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        .stat-item {
            text-align: center;
            padding: 1rem;
            background: rgba(255,255,255,0.05);
            border-radius: 0.75rem;
        }

        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary);
        }

        .stat-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }

        .voice-settings {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .wake-word-input {
            display: flex;
            gap: 0.5rem;
        }

        .wake-word-input input {
            flex: 1;
            background: rgba(255,255,255,0.1);
            border: none;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            color: var(--text);
            font-size: 0.875rem;
        }

        .toggle-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0;
        }

        .toggle {
            width: 48px;
            height: 24px;
            background: rgba(255,255,255,0.2);
            border-radius: 9999px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        }

        .toggle.active {
            background: var(--success);
        }

        .toggle::after {
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: transform 0.2s;
        }

        .toggle.active::after {
            transform: translateX(24px);
        }

        /* Permission styles */
        .permission-settings {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .permission-level {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            padding: 0.75rem;
            background: rgba(255,255,255,0.05);
            border-radius: 0.5rem;
        }

        .level-badge {
            font-weight: 600;
            font-size: 0.875rem;
        }

        .level-desc {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .permission-buttons {
            display: flex;
            gap: 0.5rem;
        }

        .btn-safe {
            background: #22c55e;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 600;
            flex: 1;
        }

        .btn-safe:hover {
            background: #16a34a;
        }

        .btn-semi {
            background: #f59e0b;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 600;
            flex: 1;
        }

        .btn-semi:hover {
            background: #d97706;
        }

        .btn-beast {
            background: #ef4444;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-weight: 600;
            flex: 1;
        }

        .btn-beast:hover {
            background: #dc2626;
        }

        .btn-safe.active, .btn-semi.active, .btn-beast.active {
            box-shadow: 0 0 0 2px white;
        }

        footer {
            padding: 1rem 2rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        @media (max-width: 768px) {
            main {
                grid-template-columns: 1fr;
            }

            .sidebar {
                order: -1;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <span class="logo-icon">⚡</span>
            <div>
                <h1>ZeusHammer</h1>
                <span>宙斯之锤</span>
            </div>
        </div>
        <div class="status">
            <div class="status-item">
                <div class="status-dot"></div>
                <span>在线</span>
            </div>
        </div>
    </header>

    <main>
        <div class="chat-container">
            <div class="chat-header">对话</div>
            <div class="chat-messages" id="messages">
                <div class="message assistant">
                    你好！我是 ZeusHammer，宙斯之锤。
                    <div class="time">系统</div>
                </div>
            </div>
            <div class="chat-input-container">
                <input type="text" class="chat-input" id="messageInput" placeholder="输入消息..." />
                <button class="btn btn-primary" onclick="sendMessage()">
                    <span>发送</span>
                </button>
                <button class="btn btn-voice" id="voiceBtn" onclick="toggleVoice()">
                    <span>🎤</span>
                </button>
            </div>
        </div>

        <div class="sidebar">
            <div class="card">
                <div class="card-header">
                    <span>统计</span>
                </div>
                <div class="card-body">
                    <div class="stat-grid">
                        <div class="stat-item">
                            <div class="stat-value" id="skillCount">0</div>
                            <div class="stat-label">技能</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="llmCalls">0</div>
                            <div class="stat-label">LLM调用</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="skillHits">0</div>
                            <div class="stat-label">技能命中</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value" id="learned">0</div>
                            <div class="stat-label">已学习</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>技能库</span>
                </div>
                <div class="card-body" id="skillsList">
                    <div class="skill-item">
                        <span class="skill-name">暂无技能</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>语音设置</span>
                </div>
                <div class="card-body">
                    <div class="voice-settings">
                        <div class="wake-word-input">
                            <input type="text" id="wakeWord" placeholder="唤醒词" value="宙斯" />
                            <button class="btn btn-primary" onclick="setWakeWord()">设置</button>
                        </div>
                        <div class="toggle-container">
                            <span>实时监听</span>
                            <div class="toggle" id="voiceToggle" onclick="toggleVoiceMode()"></div>
                        </div>
                        <div class="toggle-container">
                            <span>语音唤醒</span>
                            <div class="toggle active" id="wakeToggle" onclick="toggleWakeWord()"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 权限设置 -->
            <div class="card">
                <div class="card-header">
                    <span>权限级别</span>
                </div>
                <div class="card-body">
                    <div class="permission-settings">
                        <div class="permission-level" id="permissionDisplay">
                            <span class="level-badge" id="levelBadge">半开放</span>
                            <span class="level-desc" id="levelDesc">安全操作自动执行，危险操作需确认</span>
                        </div>
                        <div class="permission-buttons">
                            <button class="btn btn-safe" onclick="setPermission('safe')" id="btnSafe">
                                安全
                            </button>
                            <button class="btn btn-semi" onclick="setPermission('semi_open')" id="btnSemi">
                                半开放
                            </button>
                            <button class="btn btn-beast" onclick="setPermission('full_open')" id="btnBeast">
                                野兽
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer>
        ZeusHammer v2.0.0 | Claude + Hermes + OpenClaw
    </footer>

    <script>
        let ws = null;
        let isVoiceMode = false;
        let isListening = false;

        // 连接WebSocket
        function connect() {
            ws = new WebSocket(`ws://${location.host}/ws`);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'response') {
                    addMessage('assistant', data.content);
                } else if (data.type === 'voice_response') {
                    addMessage('assistant', data.text);
                }
            };

            ws.onclose = () => {
                setTimeout(connect, 3000);
            };
        }

        // 发送消息
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();

            if (!message) return;

            addMessage('user', message);
            input.value = '';

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'message',
                    content: message
                }));
            }
        }

        // 添加消息
        function addMessage(role, content) {
            const messages = document.getElementById('messages');
            const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.innerHTML = `
                ${content}
                <div class="time">${role === 'user' ? '你' : 'ZeusHammer'} · ${time}</div>
            `;

            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        // 语音控制
        function toggleVoice() {
            isListening = !isListening;
            const btn = document.getElementById('voiceBtn');

            if (isListening) {
                btn.classList.add('listening');
                startRecording();
            } else {
                btn.classList.remove('listening');
                stopRecording();
            }
        }

        let mediaRecorder = null;
        let audioChunks = [];

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = (e) => {
                    audioChunks.push(e.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();

                    reader.onloadend = () => {
                        if (ws && ws.readyState === WebSocket.OPEN) {
                            ws.send(JSON.stringify({
                                type: 'voice',
                                audio: reader.result
                            }));
                        }
                    };

                    reader.readAsDataURL(audioBlob);
                    audioChunks = [];
                };

                mediaRecorder.start();
            } catch (err) {
                console.error('录音失败:', err);
                alert('无法访问麦克风');
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
        }

        // 语音模式切换
        function toggleVoiceMode() {
            const toggle = document.getElementById('voiceToggle');
            isVoiceMode = !isVoiceMode;
            toggle.classList.toggle('active', isVoiceMode);

            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: isVoiceMode ? 'voice_enable' : 'voice_disable'
                }));
            }
        }

        // 设置唤醒词
        function setWakeWord() {
            const wakeWord = document.getElementById('wakeWord').value;
            fetch('/api/voice/wake-word', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ wake_word: wakeWord })
            });
        }

        // 权限管理
        async function loadPermission() {
            try {
                const res = await fetch('/api/permission');
                const data = await res.json();

                // 更新显示
                const levelBadge = document.getElementById('levelBadge');
                const levelDesc = document.getElementById('levelDesc');

                if (data.level === 'safe') {
                    levelBadge.textContent = '安全模式';
                    levelBadge.style.color = '#22c55e';
                    levelDesc.textContent = '所有操作需要确认';
                } else if (data.level === 'semi_open') {
                    levelBadge.textContent = '半开放';
                    levelBadge.style.color = '#f59e0b';
                    levelDesc.textContent = '安全操作自动执行，危险操作需确认';
                } else if (data.level === 'full_open') {
                    levelBadge.textContent = '野兽模式';
                    levelBadge.style.color = '#ef4444';
                    levelDesc.textContent = '无任何限制';
                }

                // 更新按钮状态
                document.getElementById('btnSafe').classList.toggle('active', data.level === 'safe');
                document.getElementById('btnSemi').classList.toggle('active', data.level === 'semi_open');
                document.getElementById('btnBeast').classList.toggle('active', data.level === 'full_open');
            } catch (err) {
                console.error('加载权限失败:', err);
            }
        }

        async function setPermission(level) {
            if (level === 'full_open') {
                if (!confirm('⚠️ 确定切换到野兽模式？\n\n所有操作将无限制执行！')) {
                    return;
                }
            }

            try {
                const res = await fetch('/api/permission', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ level: level })
                });
                const data = await res.json();

                if (data.success) {
                    loadPermission();
                    addMessage('assistant', `权限已切换为: ${data.description}`);
                }
            } catch (err) {
                console.error('设置权限失败:', err);
            }
        }

        // 加载状态
        async function loadStatus() {
            try {
                const res = await fetch('/api/stats');
                const stats = await res.json();

                document.getElementById('skillCount').textContent = stats.brain_stats?.total_skills || 0;
                document.getElementById('llmCalls').textContent = stats.llm_calls || 0;
                document.getElementById('skillHits').textContent = stats.skill_hits || 0;
                document.getElementById('learned').textContent = stats.skills_learned || 0;
            } catch (err) {
                console.error('加载状态失败:', err);
            }
        }

        // 加载技能列表
        async function loadSkills() {
            try {
                const res = await fetch('/api/skills');
                const data = await res.json();

                const list = document.getElementById('skillsList');
                if (data.skills.length === 0) {
                    list.innerHTML = '<div class="skill-item"><span class="skill-name">暂无技能</span></div>';
                } else {
                    list.innerHTML = data.skills.map(s => `
                        <div class="skill-item">
                            <span class="skill-name">${s.name}</span>
                            <span class="skill-count">${s.usage_count}次</span>
                        </div>
                    `).join('');
                }
            } catch (err) {
                console.error('加载技能失败:', err);
            }
        }

        // 初始化
        connect();
        loadStatus();
        loadSkills();
        loadPermission();
        setInterval(loadStatus, 5000);
        setInterval(loadSkills, 10000);

        // 回车发送
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    </script>
</body>
</html>
        """


async def run_ui(host: str = "0.0.0.0", port: int = 8765):
    """运行UI服务器"""
    ui = ZeusHammerUI(host, port)
    await ui.start()


if __name__ == "__main__":
    import sys
    asyncio.run(run_ui())
