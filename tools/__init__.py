#!/usr/bin/env python3
"""
ZeusHammer 工具系统
全功能工具调用系统，支持全开放模式
"""

import asyncio
import subprocess
import os
import sys
import time
import json
import tempfile
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import logging
logger = logging.getLogger(__name__.split(".")[0])

logger = logging.getLogger(__name__)


# ============== 工具定义 ==============

class ToolCategory(Enum):
    """工具分类"""
    SYSTEM = "system"           # 系统操作
    BROWSER = "browser"       # 浏览器操作
    FILE = "file"             # 文件操作
    NETWORK = "network"       # 网络操作
    CODE = "code"             # 代码执行
    MEDIA = "media"           # 媒体操作
    DEVICE = "device"         # 设备控制
    DATABASE = "database"     # 数据库操作
    AI = "ai"                # AI操作


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]
    requires_permission: bool = True
    risk_level: int = 0  # 0-10, 0=安全, 10=极高风险
    examples: List[str] = None
    
    def __post_init__(self):
        if self.examples is None:
            self.examples = []


class ToolRegistry:
    """
    工具注册表
    
    管理所有可用的工具
    """
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        tools = [
            # 文件操作
            Tool(
                name="file_read",
                description="读取文件内容",
                category=ToolCategory.FILE,
                parameters={"path": {"type": "string", "required": True}},
                risk_level=1,
            ),
            Tool(
                name="file_write",
                description="写入文件内容",
                category=ToolCategory.FILE,
                parameters={
                    "path": {"type": "string", "required": True},
                    "content": {"type": "string", "required": True},
                },
                risk_level=3,
            ),
            Tool(
                name="file_delete",
                description="删除文件",
                category=ToolCategory.FILE,
                parameters={"path": {"type": "string", "required": True}},
                risk_level=7,
            ),
            Tool(
                name="file_list",
                description="列出目录内容",
                category=ToolCategory.FILE,
                parameters={"path": {"type": "string"}},
                risk_level=1,
            ),
            Tool(
                name="file_search",
                description="搜索文件",
                category=ToolCategory.FILE,
                parameters={
                    "path": {"type": "string"},
                    "pattern": {"type": "string", "required": True},
                },
                risk_level=1,
            ),
            
            # 终端命令
            Tool(
                name="bash",
                description="执行Bash命令",
                category=ToolCategory.SYSTEM,
                parameters={"command": {"type": "string", "required": True}},
                risk_level=5,
            ),
            Tool(
                name="python",
                description="执行Python代码",
                category=ToolCategory.CODE,
                parameters={"code": {"type": "string", "required": True}},
                risk_level=5,
            ),
            
            # 网络操作
            Tool(
                name="http_request",
                description="发送HTTP请求",
                category=ToolCategory.NETWORK,
                parameters={
                    "url": {"type": "string", "required": True},
                    "method": {"type": "string", "default": "GET"},
                    "headers": {"type": "object"},
                    "body": {"type": "string"},
                },
                risk_level=2,
            ),
            Tool(
                name="web_search",
                description="网络搜索",
                category=ToolCategory.NETWORK,
                parameters={"query": {"type": "string", "required": True}},
                risk_level=1,
            ),
            Tool(
                name="web_fetch",
                description="获取网页内容",
                category=ToolCategory.NETWORK,
                parameters={"url": {"type": "string", "required": True}},
                risk_level=1,
            ),
            
            # 浏览器操作
            Tool(
                name="browser_open",
                description="打开网页",
                category=ToolCategory.BROWSER,
                parameters={"url": {"type": "string", "required": True}},
                risk_level=2,
            ),
            Tool(
                name="browser_click",
                description="点击页面元素",
                category=ToolCategory.BROWSER,
                parameters={
                    "selector": {"type": "string", "required": True},
                },
                risk_level=3,
            ),
            Tool(
                name="browser_type",
                description="输入文本",
                category=ToolCategory.BROWSER,
                parameters={
                    "selector": {"type": "string", "required": True},
                    "text": {"type": "string", "required": True},
                },
                risk_level=3,
            ),
            
            # 系统操作
            Tool(
                name="system_info",
                description="获取系统信息",
                category=ToolCategory.SYSTEM,
                parameters={},
                risk_level=1,
            ),
            Tool(
                name="process_list",
                description="列出运行中的进程",
                category=ToolCategory.SYSTEM,
                parameters={},
                risk_level=2,
            ),
            Tool(
                name="process_kill",
                description="终止进程",
                category=ToolCategory.SYSTEM,
                parameters={"pid": {"type": "integer", "required": True}},
                risk_level=8,
            ),
            
            # 设备操作
            Tool(
                name="screenshot",
                description="截取屏幕截图",
                category=ToolCategory.MEDIA,
                parameters={"path": {"type": "string"}},
                risk_level=1,
            ),
            Tool(
                name="clipboard_get",
                description="获取剪贴板内容",
                category=ToolCategory.DEVICE,
                parameters={},
                risk_level=1,
            ),
            Tool(
                name="clipboard_set",
                description="设置剪贴板内容",
                category=ToolCategory.DEVICE,
                parameters={"content": {"type": "string", "required": True}},
                risk_level=2,
            ),
        ]
        
        for tool in tools:
            self.register(tool)
    
    def register(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")
    
    def get(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(name)
    
    def list_by_category(self, category: ToolCategory) -> List[Tool]:
        """按分类列出工具"""
        return [t for t in self.tools.values() if t.category == category]
    
    def search(self, query: str) -> List[Tool]:
        """搜索工具"""
        query = query.lower()
        return [
            t for t in self.tools.values()
            if query in t.name.lower() or query in t.description.lower()
        ]


# ============== 工具执行器 ==============

class ToolExecutor:
    """
    工具执行器
    
    执行各种工具调用
    支持全开放模式（无限制）
    """
    
    def __init__(
        self,
        permission_guard=None,
        audit_logger=None,
        mode: str = "full_unleashed"
    ):
        self.registry = ToolRegistry()
        self.permission_guard = permission_guard
        self.audit_logger = audit_logger
        self.mode = mode
        
        # 浏览器控制器
        self.browser = None
        
        # 执行历史
        self.execution_history: List[Dict] = []
    
    def set_browser(self, browser):
        """设置浏览器控制器"""
        self.browser = browser
    
    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user: str = "system"
    ) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            user: 用户名
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        # 获取工具定义
        tool = self.registry.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        # 权限检查（全开放模式跳过）
        if self.mode != "full_unleashed" and tool.requires_permission:
            if self.permission_guard:
                context = type('Context', (), {
                    'action': tool_name,
                    'args': parameters,
                    'user': user
                })()
                if not self.permission_guard.check_permission(context):
                    return {"success": False, "error": "Permission denied"}
        
        # 审计日志
        if self.audit_logger:
            audit_id = self.audit_logger.log(
                action=tool_name,
                result="pending",
                args=parameters,
                user=user,
                mode=self.mode,
                risk_level=str(tool.risk_level)
            )
        
        try:
            # 执行工具
            result = await self._execute_tool(tool, parameters)
            
            duration = time.time() - start_time
            
            # 记录执行历史
            self.execution_history.append({
                "tool": tool_name,
                "parameters": parameters,
                "result": result,
                "duration": duration,
                "timestamp": time.time(),
            })
            
            # 更新审计日志
            if self.audit_logger:
                self.audit_logger.log_success(audit_id, duration * 1000)
            
            return {
                "success": True,
                "result": result,
                "duration_ms": duration * 1000,
                "tool": tool_name,
            }
            
        except Exception as e:
            logger.error(f"工具执行失败: {tool_name} - {e}")
            
            if self.audit_logger:
                self.audit_logger.log_failed(audit_id, str(e))
            
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name,
            }
    
    async def _execute_tool(self, tool: Tool, params: Dict) -> Any:
        """执行具体工具"""
        name = tool.name
        
        if name == "file_read":
            return self._file_read(params["path"])
        elif name == "file_write":
            return self._file_write(params["path"], params["content"])
        elif name == "file_delete":
            return self._file_delete(params["path"])
        elif name == "file_list":
            return self._file_list(params.get("path", "."))
        elif name == "file_search":
            return self._file_search(params.get("path", "."), params["pattern"])
        
        elif name == "bash":
            return await self._bash(params["command"])
        elif name == "python":
            return await self._python(params["code"])
        
        elif name == "http_request":
            return await self._http_request(
                params["url"],
                params.get("method", "GET"),
                params.get("headers", {}),
                params.get("body")
            )
        elif name == "web_search":
            return await self._web_search(params["query"])
        elif name == "web_fetch":
            return await self._web_fetch(params["url"])
        
        elif name == "browser_open":
            return await self._browser_open(params["url"])
        elif name == "browser_click":
            return await self._browser_click(params["selector"])
        elif name == "browser_type":
            return await self._browser_type(params["selector"], params["text"])
        
        elif name == "system_info":
            return self._system_info()
        elif name == "process_list":
            return await self._process_list()
        elif name == "process_kill":
            return self._process_kill(params["pid"])
        
        elif name == "screenshot":
            return await self._screenshot(params.get("path"))
        elif name == "clipboard_get":
            return self._clipboard_get()
        elif name == "clipboard_set":
            return self._clipboard_set(params["content"])
        
        else:
            raise ValueError(f"Tool not implemented: {name}")
    
    # ============== 文件操作 ==============
    
    def _file_read(self, path: str) -> str:
        """读取文件"""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return p.read_text(encoding='utf-8')
    
    def _file_write(self, path: str, content: str) -> Dict:
        """写入文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return {"path": str(p.absolute()), "size": len(content)}
    
    def _file_delete(self, path: str) -> Dict:
        """删除文件"""
        p = Path(path)
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
        return {"deleted": str(p)}
    
    def _file_list(self, path: str = ".") -> List[str]:
        """列出目录"""
        p = Path(path)
        if not p.exists():
            return []
        return [str(f.relative_to(p)) for f in p.iterdir()]
    
    def _file_search(self, path: str, pattern: str) -> List[str]:
        """搜索文件"""
        p = Path(path)
        if not p.exists():
            return []
        
        results = []
        for f in p.rglob(f"*{pattern}*"):
            results.append(str(f.relative_to(p)))
        return results
    
    # ============== 命令执行 ==============
    
    async def _bash(self, command: str) -> Dict:
        """执行Bash命令"""
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    
    async def _python(self, code: str) -> Any:
        """执行Python代码"""
        # 在隔离环境中执行
        result = {}
        local_vars = {}
        
        try:
            exec(code, {"__builtins__": __builtins__}, local_vars)
            result["success"] = True
            result["output"] = str(local_vars.get("_", ""))
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
        
        return result
    
    # ============== 网络操作 ==============
    
    async def _http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Dict = None,
        body: str = None
    ) -> Dict:
        """发送HTTP请求"""
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    data=body
                ) as response:
                    return {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text(),
                    }
        except ImportError:
            # 使用urllib
            import urllib.request
            import urllib.parse
            
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": resp.read().decode('utf-8'),
                }
    
    async def _web_search(self, query: str) -> List[Dict]:
        """网络搜索"""
        # 简单实现：使用DuckDuckGo
        try:
            return await self._http_request(
                f"https://api.duckduckgo.com/?q={query}&format=json"
            )
        except Exception as e:
            return {"error": str(e), "results": []}
    
    async def _web_fetch(self, url: str) -> Dict:
        """获取网页"""
        return await self._http_request(url)
    
    # ============== 浏览器操作 ==============
    
    async def _browser_open(self, url: str) -> Dict:
        """打开网页"""
        if self.browser:
            await self.browser.navigate(url)
            return {"url": url, "opened": True}
        
        # 没有浏览器控制器，使用系统默认
        import webbrowser
        webbrowser.open(url)
        return {"url": url, "opened": True}
    
    async def _browser_click(self, selector: str) -> Dict:
        """点击元素"""
        if self.browser:
            await self.browser.click(selector)
        return {"selector": selector, "clicked": True}
    
    async def _browser_type(self, selector: str, text: str) -> Dict:
        """输入文本"""
        if self.browser:
            await self.browser.type(selector, text)
        return {"selector": selector, "text": text}
    
    # ============== 系统操作 ==============
    
    def _system_info(self) -> Dict:
        """获取系统信息"""
        import platform
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
    
    async def _process_list(self) -> List[Dict]:
        """列出进程"""
        if sys.platform == "darwin":
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True
            )
            lines = result.stdout.split("\n")[1:]  # 跳过标题
            processes = []
            for line in lines[:50]:  # 只返回前50个
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": parts[10][:50],
                    })
            return processes
        else:
            return []
    
    def _process_kill(self, pid: int) -> Dict:
        """终止进程"""
        if sys.platform == "darwin" or sys.platform.startswith("linux"):
            result = subprocess.run(["kill", str(pid)], capture_output=True)
            return {"pid": pid, "killed": result.returncode == 0}
        return {"error": "Unsupported platform"}
    
    # ============== 设备操作 ==============
    
    async def _screenshot(self, path: str = None) -> Dict:
        """截图"""
        if path is None:
            path = f"/tmp/screenshot_{int(time.time())}.png"
        
        if sys.platform == "darwin":
            # macOS截图
            subprocess.run([
                "screencapture", "-x", path
            ], check=True)
        elif sys.platform.startswith("linux"):
            # Linux截图
            subprocess.run([
                "scrot", path
            ], check=True)
        else:
            # Windows
            return {"error": "Screenshot not supported on Windows"}
        
        return {"path": path, "saved": True}
    
    def _clipboard_get(self) -> str:
        """获取剪贴板"""
        if sys.platform == "darwin":
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True
            )
            return result.stdout
        elif sys.platform.startswith("linux"):
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True
            )
            return result.stdout
        return ""
    
    def _clipboard_set(self, content: str) -> Dict:
        """设置剪贴板"""
        if sys.platform == "darwin":
            subprocess.run(
                ["pbcopy"],
                input=content.encode(),
                check=True
            )
        elif sys.platform.startswith("linux"):
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=content.encode(),
                check=True
            )
        return {"success": True}
    
    def get_execution_history(self, limit: int = 100) -> List[Dict]:
        """获取执行历史"""
        return self.execution_history[-limit:]


# ============== 便捷函数 ==============

def create_executor(mode: str = "full_unleashed", permission_guard=None, audit_logger=None) -> ToolExecutor:
    """创建工具执行器"""
    return ToolExecutor(
        permission_guard=permission_guard,
        audit_logger=audit_logger,
        mode=mode
    )
