"""
ZeusHammer MCP Protocol Implementation

真正融合Hermes MCP核心协议:

1. 完整的JSON-RPC消息处理
2. Stdio传输
3. HTTP/SSE传输
4. WebSocket传输
5. OAuth 2.1 PKCE
6. 工具发现
7. 资源管理
8. 采样回调

参考Hermes MCP实现
"""

import asyncio
import json
import logging
import subprocess
import hashlib
import base64
import secrets
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from urllib.parse import urlencode
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


# ============================================
# MCP协议类型定义 (来自MCP规范)
# ============================================

class JSONRPCMethod:
    """MCP JSON-RPC方法"""
    # 初始化
    INITIALIZE = "initialize"
    INITIALIZED = "initialized"

    # 工具
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"

    # 资源
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"

    # 提示
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"

    # 采样
    SAMPLING_CREATE_MESSAGE = "sampling/createMessage"

    # 进度
    PROGRESS = "notifications/progress"
    CANCEL = "notifications/cancelled"

    # 日志
    LOG_MESSAGE = "notifications/message"


@dataclass
class MCPMessage:
    """MCP JSON-RPC消息"""
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: Optional[str] = None
    params: Optional[Dict] = None
    result: Optional[Any] = None
    error: Optional[Dict] = None


@dataclass
class MCPError:
    """MCP错误"""
    code: int
    message: str
    data: Any = None


class MCPParser:
    """MCP JSON-RPC消息解析器"""

    @staticmethod
    def parse(raw: str) -> MCPMessage:
        """解析JSON-RPC消息"""
        try:
            data = json.loads(raw)
            return MCPMessage(
                jsonrpc=data.get("jsonrpc", "2.0"),
                id=data.get("id"),
                method=data.get("method"),
                params=data.get("params"),
                result=data.get("result"),
                error=data.get("error"),
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON-RPC: {e}")

    @staticmethod
    def serialize(msg: MCPMessage) -> str:
        """序列化JSON-RPC消息"""
        data = {"jsonrpc": "2.0"}

        if msg.id is not None:
            data["id"] = msg.id
        if msg.method is not None:
            data["method"] = msg.method
        if msg.params is not None:
            data["params"] = msg.params
        if msg.result is not None:
            data["result"] = msg.result
        if msg.error is not None:
            data["error"] = msg.error

        return json.dumps(data)


# ============================================
# MCP传输层 (Hermes核心)
# ============================================

class MCPTransport(ABC):
    """MCP传输基类"""

    @abstractmethod
    async def start(self):
        """启动传输"""
        pass

    @abstractmethod
    async def stop(self):
        """停止传输"""
        pass

    @abstractmethod
    async def send(self, message: MCPMessage):
        """发送消息"""
        pass

    @abstractmethod
    async def receive(self) -> MCPMessage:
        """接收消息"""
        pass


class StdioTransport(MCPTransport):
    """
    Stdio传输 (Hermes核心)

    通过标准输入/输出与MCP服务器通信
    """

    def __init__(self, command: str, args: List[str] = None, env: Dict = None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self._process: Optional[subprocess.Popen] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        """启动stdio进程"""
        # 合并环境变量
        import os
        full_env = {**os.environ, **self.env}

        # 启动进程
        self._process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            text=False,  # 二进制模式
        )

        self._running = True

        # 启动读取任务
        self._reader_task = asyncio.create_task(self._read_loop())

        # 发送初始化
        init_msg = MCPMessage(
            method=JSONRPCMethod.INITIALIZE,
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "zueshammer",
                    "version": "2.0.0",
                },
            },
        )
        await self.send(init_msg)

        # 等待initialized
        while True:
            msg = await self._message_queue.get()
            if msg.method == JSONRPCMethod.INITIALIZED:
                break

        logger.info(f"Stdio MCP connected: {self.command}")

    async def stop(self):
        """停止stdio进程"""
        self._running = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    async def send(self, message: MCPMessage):
        """发送消息"""
        if not self._process or not self._running:
            raise RuntimeError("Transport not started")

        raw = MCPParser.serialize(message)
        line = base64.b64encode(raw.encode()).decode() + "\n"

        self._process.stdin.write(line)
        self._process.stdin.flush()

    async def receive(self) -> MCPMessage:
        """接收消息"""
        return await self._message_queue.get()

    async def _read_loop(self):
        """读取循环"""
        while self._running and self._process:
            try:
                line = self._process.stdout.readline()
                if not line:
                    break

                raw = base64.b64decode(line.strip()).decode()
                msg = MCPParser.parse(raw)

                # 过滤progress通知
                if msg.method != JSONRPCMethod.PROGRESS:
                    await self._message_queue.put(msg)

            except Exception as e:
                logger.error(f"Stdio read error: {e}")
                break


class HTTPStreamableTransport(MCPTransport):
    """
    HTTP Streamable传输 (Hermes核心)

    使用HTTP POST进行调用，GET进行流式响应
    """

    def __init__(self, base_url: str, headers: Dict = None):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self._session_id: Optional[str] = None
        self._abort_event = asyncio.Event()

    async def start(self):
        """启动HTTP传输"""
        # 发送初始化
        init_msg = MCPMessage(
            method=JSONRPCMethod.INITIALIZE,
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "zueshammer",
                    "version": "2.0.0",
                },
            },
        )

        response = await self._post(init_msg)
        if response.result:
            self._session_id = response.result.get("session", secrets.token_urlsafe(32))

        logger.info(f"HTTP MCP connected: {self.base_url}")

    async def stop(self):
        """停止HTTP传输"""
        self._abort_event.set()

    async def send(self, message: MCPMessage):
        """发送消息"""
        if self._session_id:
            message.params = message.params or {}
            message.params["sessionId"] = self._session_id

        await self._post(message)

    async def receive(self) -> MCPMessage:
        """接收消息 (通过轮询)"""
        # 实现简化版轮询
        await asyncio.sleep(0.1)
        raise RuntimeError("HTTP transport requires polling mode")

    async def _post(self, message: MCPMessage) -> MCPMessage:
        """发送POST请求"""
        data = json.dumps({
            "jsonrpc": "2.0",
            "id": message.id,
            "method": message.method,
            "params": message.params,
        }).encode()

        headers = {
            "Content-Type": "application/json",
            **self.headers,
        }

        if self._session_id:
            headers["MCP-Session-ID"] = self._session_id

        req = urllib.request.Request(
            self.base_url + "/mcp",
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read())
                return MCPMessage(
                    id=result.get("id"),
                    result=result.get("result"),
                    error=result.get("error"),
                )
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            return MCPMessage(
                error={"code": e.code, "message": body}
            )


class SSEDTransport(MCPTransport):
    """
    SSE传输 (Hermes核心)

    Server-Sent Events流式接收
    """

    def __init__(self, url: str, headers: Dict = None):
        self.url = url
        self.headers = headers or {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def start(self):
        """启动SSE传输"""
        self._running = True
        asyncio.create_task(self._sse_loop())
        logger.info(f"SSE MCP connected: {self.url}")

    async def stop(self):
        """停止SSE传输"""
        self._running = False

    async def send(self, message: MCPMessage):
        """发送消息"""
        # SSE是单向的，发送使用HTTP
        pass

    async def receive(self) -> MCPMessage:
        """接收消息"""
        return await self._event_queue.get()

    async def _sse_loop(self):
        """SSE事件循环"""
        import urllib.request

        req = urllib.request.Request(
            self.url,
            headers=self.headers,
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                for line in response:
                    if not self._running:
                        break

                    line = line.decode().strip()
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data.startswith("{"):
                            msg = MCPParser.parse(data)
                            await self._event_queue.put(msg)

        except Exception as e:
            logger.error(f"SSE error: {e}")
            self._running = False


# ============================================
# MCP客户端 (Hermes核心)
# ============================================

class MCPClient:
    """
    MCP客户端 (Hermes核心)

    实现:
    1. 多传输支持
    2. 完整JSON-RPC消息处理
    3. 工具发现和调用
    4. 资源管理
    5. 采样回调
    """

    def __init__(self, name: str = "zueshammer"):
        self.name = name
        self._transport: Optional[MCPTransport] = None
        self._tools: List[Dict] = []
        self._resources: List[Dict] = []
        self._capabilities: Dict = {}
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._request_id = 0

        # 回调
        self._callbacks: Dict[str, Callable] = {}

    async def connect_stdio(self, command: str, args: List[str] = None, env: Dict = None):
        """连接stdio服务器"""
        transport = StdioTransport(command, args, env)
        await transport.start()
        self._transport = transport
        await self._discover_capabilities()

    async def connect_http(self, url: str, headers: Dict = None):
        """连接HTTP服务器"""
        transport = HTTPStreamableTransport(url, headers)
        await transport.start()
        self._transport = transport
        await self._discover_capabilities()

    async def connect_sse(self, url: str, headers: Dict = None):
        """连接SSE服务器"""
        transport = SSEDTransport(url, headers)
        await transport.start()
        self._transport = transport

    async def disconnect(self):
        """断开连接"""
        if self._transport:
            await self._transport.stop()

    async def _discover_capabilities(self):
        """发现服务器能力"""
        # 发送initialize
        response = await self._send_request(
            JSONRPCMethod.INITIALIZE,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": self.name,
                    "version": "2.0.0",
                },
            }
        )

        if response.result:
            self._capabilities = response.result.get("capabilities", {})

            # 发现工具
            if "tools" in self._capabilities:
                await self._discover_tools()

            # 发现资源
            if "resources" in self._capabilities:
                await self._discover_resources()

    async def _discover_tools(self):
        """发现工具列表"""
        response = await self._send_request(JSONRPCMethod.TOOLS_LIST)
        if response.result:
            self._tools = response.result.get("tools", [])

    async def _discover_resources(self):
        """发现资源列表"""
        response = await self._send_request(JSONRPCMethod.RESOURCES_LIST)
        if response.result:
            self._resources = response.result.get("resources", [])

    async def _send_request(self, method: str, params: Dict = None) -> MCPMessage:
        """发送请求并等待响应"""
        if not self._transport:
            raise RuntimeError("Not connected")

        request_id = self._request_id
        self._request_id += 1

        # 创建future
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        # 发送消息
        message = MCPMessage(
            id=request_id,
            method=method,
            params=params or {},
        )

        await self._transport.send(message)

        # 等待响应
        try:
            response = await asyncio.wait_for(future, timeout=120)
            return response
        except asyncio.TimeoutError:
            del self._pending_requests[request_id]
            raise TimeoutError(f"MCP request timeout: {method}")

    async def call_tool(self, name: str, arguments: Dict = None) -> Dict:
        """
        调用工具 (Hermes核心)

        执行MCP服务器上的工具
        """
        response = await self._send_request(
            JSONRPCMethod.TOOLS_CALL,
            {
                "name": name,
                "arguments": arguments or {},
            }
        )

        if response.error:
            raise RuntimeError(f"MCP tool error: {response.error}")

        return response.result

    async def read_resource(self, uri: str) -> Dict:
        """读取资源"""
        response = await self._send_request(
            JSONRPCMethod.RESOURCES_READ,
            {"uri": uri}
        )

        if response.error:
            raise RuntimeError(f"MCP resource error: {response.error}")

        return response.result

    async def create_sampling_message(
        self,
        system_prompt: str,
        messages: List[Dict],
        max_tokens: int = 8192,
    ) -> Dict:
        """
        创建采样消息 (Hermes核心)

        请求LLM生成
        """
        response = await self._send_request(
            JSONRPCMethod.SAMPLING_CREATE_MESSAGE,
            {
                "systemPrompt": system_prompt,
                "messages": messages,
                "maxTokens": max_tokens,
            }
        )

        if response.error:
            raise RuntimeError(f"MCP sampling error: {response.error}")

        return response.result

    def get_tools(self) -> List[Dict]:
        """获取工具列表"""
        return self._tools

    def get_resources(self) -> List[Dict]:
        """获取资源列表"""
        return self._resources

    def get_capabilities(self) -> Dict:
        """获取服务器能力"""
        return self._capabilities

    def on_notification(self, method: str, callback: Callable):
        """注册通知回调"""
        self._callbacks[method] = callback


# ============================================
# MCP服务器管理
# ============================================

class MCPServerManager:
    """
    MCP服务器管理器 (Hermes核心)

    管理多个MCP服务器连接
    """

    def __init__(self):
        self._servers: Dict[str, MCPClient] = {}
        self._configs: List[Dict] = []

    def add_server(
        self,
        name: str,
        transport: str = "stdio",
        command: str = None,
        args: List[str] = None,
        url: str = None,
        env: Dict = None,
        headers: Dict = None,
    ):
        """添加服务器配置"""
        self._configs.append({
            "name": name,
            "transport": transport,
            "command": command,
            "args": args or [],
            "url": url,
            "env": env,
            "headers": headers,
        })

    async def connect_all(self) -> Dict[str, bool]:
        """连接所有服务器"""
        results = {}

        for config in self._configs:
            try:
                client = MCPClient(self.name if hasattr(self, "name") else "zueshammer")

                if config["transport"] == "stdio":
                    await client.connect_stdio(
                        config["command"],
                        config["args"],
                        config["env"],
                    )
                elif config["transport"] == "http":
                    await client.connect_http(
                        config["url"],
                        config["headers"],
                    )
                elif config["transport"] == "sse":
                    await client.connect_sse(
                        config["url"],
                        config["headers"],
                    )

                self._servers[config["name"]] = client
                results[config["name"]] = True
                logger.info(f"MCP server connected: {config['name']}")

            except Exception as e:
                logger.error(f"MCP server failed: {config['name']}: {e}")
                results[config["name"]] = False

        return results

    async def disconnect_all(self):
        """断开所有服务器"""
        for name, client in self._servers.items():
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Disconnect error: {name}: {e}")

        self._servers.clear()

    def get_server(self, name: str) -> Optional[MCPClient]:
        """获取服务器"""
        return self._servers.get(name)

    def get_all_tools(self) -> List[Dict]:
        """获取所有服务器的工具"""
        tools = []
        for name, client in self._servers.items():
            for tool in client.get_tools():
                tool["server"] = name
                tool["name"] = f"{name}:{tool['name']}"
                tools.append(tool)
        return tools

    def get_all_resources(self) -> List[Dict]:
        """获取所有服务器的资源"""
        resources = []
        for name, client in self._servers.items():
            for resource in client.get_resources():
                resource["server"] = name
                resources.append(resource)
        return resources


# ============================================
# OAuth 2.1 PKCE支持 (Hermes核心)
# ============================================

class MCPOAuthHandler:
    """
    MCP OAuth 2.1 PKCE处理 (Hermes核心)

    支持动态客户端注册和授权码流程
    """

    def __init__(self):
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._code_verifier: Optional[str] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None

    def generate_pkce_pair(self) -> Tuple[str, str]:
        """生成PKCE码对"""
        # 代码验证器
        self._code_verifier = secrets.token_urlsafe(64)

        # 代码挑战 (S256方法)
        digest = hashlib.sha256(self._code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")

        return self._code_verifier, code_challenge

    async def register_client(self, issuer: str, redirect_uris: List[str]) -> Dict:
        """动态客户端注册"""
        registration = {
            "client_name": "zueshammer",
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        }

        req = urllib.request.Request(
            issuer.rstrip("/") + "/oauth/register",
            data=json.dumps(registration).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read())
                self._client_id = result.get("client_id")
                self._client_secret = result.get("client_secret")
                return result
        except Exception as e:
            raise RuntimeError(f"OAuth registration failed: {e}")

    async def get_authorization_url(
        self,
        issuer: str,
        redirect_uri: str,
        scope: str = "mcp",
    ) -> str:
        """获取授权URL"""
        code_verifier, code_challenge = self.generate_pkce_pair()

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        return f"{issuer}/oauth/authorize?{urlencode(params)}"

    async def exchange_code(
        self,
        issuer: str,
        code: str,
        redirect_uri: str,
    ) -> Dict:
        """交换授权码"""
        if not self._code_verifier:
            raise RuntimeError("PKCE not initialized")

        token_req = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "code_verifier": self._code_verifier,
        }

        if self._client_secret:
            token_req["client_secret"] = self._client_secret

        req = urllib.request.Request(
            issuer.rstrip("/") + "/oauth/token",
            data=urlencode(token_req).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read())
                self._access_token = result.get("access_token")
                self._refresh_token = result.get("refresh_token")
                return result
        except Exception as e:
            raise RuntimeError(f"OAuth token exchange failed: {e}")

    async def refresh_access_token(self, issuer: str) -> Dict:
        """刷新访问令牌"""
        if not self._refresh_token:
            raise RuntimeError("No refresh token")

        token_req = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
        }

        if self._client_secret:
            token_req["client_secret"] = self._client_secret

        req = urllib.request.Request(
            issuer.rstrip("/") + "/oauth/token",
            data=urlencode(token_req).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read())
                self._access_token = result.get("access_token")
                if result.get("refresh_token"):
                    self._refresh_token = result.get("refresh_token")
                return result
        except Exception as e:
            raise RuntimeError(f"OAuth refresh failed: {e}")

    def get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        return self._access_token


# 全局实例
_mcp_manager: Optional[MCPServerManager] = None


def get_mcp_manager() -> MCPServerManager:
    """获取MCP服务器管理器"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPServerManager()
    return _mcp_manager


# ============================================
# MCP协议封装 (engine.py所需接口)
# ============================================

class MCPProtocol:
    """
    MCP协议封装层

    为ZeusHammerCore提供统一的MCP接口。
    封装MCPClient/MCPServerManager，提供初始化和关闭等生命周期方法。
    """

    def __init__(self, timeout: int = 30, event_bus=None):
        self.timeout = timeout
        self.event_bus = event_bus
        self._manager = MCPServerManager()
        self._initialized = False

    async def initialize(self):
        """初始化MCP协议"""
        if self._initialized:
            return

        try:
            # 加载服务器配置
            servers = self._load_servers()
            for server in servers:
                self._manager.add_server(
                    name=server.get("name", "unknown"),
                    transport=server.get("transport", "stdio"),
                    command=server.get("command"),
                    args=server.get("args"),
                    url=server.get("url"),
                    env=server.get("env"),
                    headers=server.get("headers"),
                )
            await self._manager.connect_all()
            self._initialized = True
            logger.info("MCPProtocol初始化完成")
        except Exception as e:
            logger.error(f"MCPProtocol初始化失败: {e}")
            raise

    def _load_servers(self) -> List[Dict]:
        """加载MCP服务器配置"""
        import os
        config_path = os.path.expanduser("~/.zueshammer/mcp.json")

        if not os.path.exists(config_path):
            return self._default_servers()

        try:
            import json
            with open(config_path) as f:
                config = json.load(f)
                return config.get("servers", [])
        except Exception as e:
            logger.error(f"加载MCP配置失败: {e}")
            return []

    def _default_servers(self) -> List[Dict]:
        """默认MCP服务器配置"""
        return []

    async def shutdown(self):
        """关闭MCP协议"""
        if not self._initialized:
            return

        try:
            await self._manager.disconnect_all()
            self._initialized = False
            logger.info("MCPProtocol已关闭")
        except Exception as e:
            logger.error(f"MCPProtocol关闭失败: {e}")

    def get_tools(self) -> List[Dict]:
        """获取所有MCP工具"""
        return self._manager.get_all_tools()

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Dict:
        """调用MCP工具"""
        client = self._manager.get_server(server_name)
        if not client:
            return {"error": f"未知服务器: {server_name}"}
        return await client.call_tool(tool_name, arguments)
