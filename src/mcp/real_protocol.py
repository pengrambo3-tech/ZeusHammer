"""
ZeusHammer MCP协议层

真实集成Hermes的MCP协议连接能力。
支持stdio、HTTP、SSE等多种传输方式。
"""

import os
import asyncio
import json
import logging
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server: str


@dataclass
class MCPResource:
    """MCP资源"""
    uri: str
    name: str
    mime_type: str
    server: str


class MCPConnection:
    """单个MCP服务器连接"""

    def __init__(self, name: str, transport: str, config: Dict[str, Any]):
        self.name = name
        self.transport = transport
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.tools: List[MCPTool] = []
        self.resources: List[MCPResource] = []
        self._connected = False

    async def connect(self) -> bool:
        """建立连接"""
        try:
            if self.transport == "stdio":
                return await self._connect_stdio()
            elif self.transport == "http":
                return await self._connect_http()
            elif self.transport == "sse":
                return await self._connect_sse()
            else:
                logger.error(f"未知传输方式: {self.transport}")
                return False
        except Exception as e:
            logger.error(f"MCP连接失败 {self.name}: {e}")
            return False

    async def _connect_stdio(self) -> bool:
        """Stdio传输 - 启动本地MCP服务器进程"""
        command = self.config.get("command", "")
        args = self.config.get("args", [])

        if not command:
            logger.error(f"stdio连接缺少command: {self.name}")
            return False

        try:
            # 启动进程
            self.process = subprocess.Popen(
                [command] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 发送初始化
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "zueshammer",
                        "version": "2.0.0"
                    }
                }
            }

            response = await self._send_request(init_request)
            if response:
                self._connected = True
                # 发现工具
                await self._discover_tools()
                logger.info(f"MCP连接成功: {self.name}")
                return True

        except Exception as e:
            logger.error(f"stdio连接失败: {e}")
            return False

    async def _connect_http(self) -> bool:
        """HTTP传输 - 连接远程MCP服务器"""
        url = self.config.get("url", "")

        if not url:
            logger.error(f"http连接缺少url: {self.name}")
            return False

        try:
            # 发送初始化
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "zueshammer", "version": "2.0.0"}
                }
            }

            response = await self._http_request(url, init_request)
            if response:
                self._connected = True
                await self._discover_tools()
                logger.info(f"MCP HTTP连接成功: {self.name}")
                return True

        except Exception as e:
            logger.error(f"HTTP连接失败: {e}")
            return False

    async def _connect_sse(self) -> bool:
        """SSE传输 - Server-Sent Events"""
        url = self.config.get("url", "")

        if not url:
            logger.error(f"sse连接缺少url: {self.name}")
            return False

        try:
            # SSE连接实现
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    self._connected = True
                    logger.info(f"MCP SSE连接成功: {self.name}")
                    return True

        except ImportError:
            logger.warning("需要安装aiohttp: pip install aiohttp")
            return False
        except Exception as e:
            logger.error(f"SSE连接失败: {e}")
            return False

    async def _send_request(self, request: Dict) -> Optional[Dict]:
        """通过stdio发送请求"""
        if not self.process:
            return None

        try:
            request_json = json.dumps(request) + "\n"
            self.process.stdin.write(request_json)
            self.process.stdin.flush()

            response_line = self.process.stdout.readline()
            if response_line:
                return json.loads(response_line)

        except Exception as e:
            logger.error(f"发送请求失败: {e}")

        return None

    async def _http_request(self, url: str, data: Dict) -> Optional[Dict]:
        """发送HTTP请求"""
        try:
            data_bytes = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))

        except Exception as e:
            logger.error(f"HTTP请求失败: {e}")
            return None

    async def _discover_tools(self):
        """发现可用工具"""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        response = await self._send_request(request)
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            self.tools = [
                MCPTool(
                    name=t["name"],
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {}),
                    server=self.name
                )
                for t in tools
            ]
            logger.info(f"发现{len(self.tools)}个工具: {self.name}")

    async def call_tool(self, tool_name: str, arguments: Dict) -> Dict[str, Any]:
        """调用MCP工具"""
        if not self._connected:
            return {"error": "未连接"}

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        if self.transport == "stdio":
            return await self._send_request(request) or {"error": "请求失败"}
        elif self.transport in ("http", "sse"):
            return await self._http_request(self.config.get("url", ""), request) or {"error": "请求失败"}

        return {"error": "未知传输方式"}

    async def disconnect(self):
        """断开连接"""
        self._connected = False
        if self.process:
            self.process.terminate()
            self.process = None


class MCPManager:
    """
    MCP协议管理器

    管理多个MCP服务器连接。
    支持:
    - 本地stdio服务器
    - 远程HTTP服务器
    - SSE流式服务器
    """

    def __init__(self, config_path: str = None):
        self.connections: Dict[str, MCPConnection] = {}
        self._config_path = config_path or os.path.expanduser("~/.zueshammer/mcp.json")

    async def initialize(self, servers: List[Dict[str, Any]] = None):
        """初始化并连接所有服务器"""
        # 加载配置
        if servers is None:
            servers = self._load_config()

        # 连接每个服务器
        for server_config in servers:
            name = server_config.get("name", "unknown")
            transport = server_config.get("transport", "stdio")
            config = server_config.get("config", {})

            conn = MCPConnection(name, transport, config)
            if await conn.connect():
                self.connections[name] = conn
                logger.info(f"已连接MCP服务器: {name}")

    def _load_config(self) -> List[Dict[str, Any]]:
        """加载MCP配置"""
        config_path = Path(self._config_path)

        if not config_path.exists():
            # 默认配置
            return self._default_config()

        try:
            with open(config_path) as f:
                config = json.load(f)
                return config.get("mcpServers", [])
        except Exception as e:
            logger.error(f"加载MCP配置失败: {e}")
            return []

    def _default_config(self) -> List[Dict[str, Any]]:
        """默认MCP配置"""
        return [
            {
                "name": "filesystem",
                "transport": "stdio",
                "config": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", os.getcwd()]
                }
            },
            {
                "name": "github",
                "transport": "stdio",
                "config": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"]
                }
            }
        ]

    def get_tools(self) -> List[MCPTool]:
        """获取所有可用工具"""
        tools = []
        for conn in self.connections.values():
            tools.extend(conn.tools)
        return tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Dict:
        """调用指定服务器的指定工具"""
        if server_name not in self.connections:
            return {"error": f"未知服务器: {server_name}"}

        return await self.connections[server_name].call_tool(tool_name, arguments)

    async def close(self):
        """关闭所有连接"""
        for conn in self.connections.values():
            await conn.disconnect()
        self.connections.clear()


# 全局MCP管理器
_mcp_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager


# ============================================
# MCP协议封装 (engine.py所需接口)
# ============================================

class MCPProtocol:
    """
    MCP协议封装层

    为ZeusHammerCore提供统一的MCP接口。
    封装MCPManager，提供初始化和关闭等生命周期方法。
    """

    def __init__(self, timeout: int = 30, event_bus=None):
        self.timeout = timeout
        self.event_bus = event_bus
        self._manager = MCPManager()
        self._initialized = False

    async def initialize(self):
        """初始化MCP协议"""
        if self._initialized:
            return

        try:
            await self._manager.initialize()
            self._initialized = True
            logger.info("MCPProtocol初始化完成")
        except Exception as e:
            logger.error(f"MCPProtocol初始化失败: {e}")
            raise

    async def shutdown(self):
        """关闭MCP协议"""
        if not self._initialized:
            return

        try:
            await self._manager.close()
            self._initialized = False
            logger.info("MCPProtocol已关闭")
        except Exception as e:
            logger.error(f"MCPProtocol关闭失败: {e}")

    def get_tools(self):
        """获取所有MCP工具"""
        return self._manager.get_tools()

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """调用MCP工具"""
        return await self._manager.call_tool(server_name, tool_name, arguments)