"""
ZeusHammer 工具系统

真实集成ClaudeCode的CLI工具能力。
通过claude命令直接调用Agent/Bash/File等工具。
"""

import os
import asyncio
import subprocess
import json
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any = None
    error: str = ""
    tool: str = ""


class ClaudeTools:
    """
    ClaudeCode工具集

    真实集成ClaudeCode的CLI工具能力:
    - Agent: 启动子代理
    - Bash: 执行Shell命令
    - FileRead/FileWrite/FileEdit: 文件操作
    - WebSearch/WebFetch: 网络工具
    - Glob/Grep: 搜索工具
    """

    def __init__(self):
        self.name = "claude"
        self._check_claude()

    def _check_claude(self):
        """检查Claude CLI是否可用"""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"Claude CLI可用: {result.stdout.strip()}")
                return True
        except Exception:
            pass
        logger.warning("Claude CLI未安装，部分功能受限")

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """执行Claude工具"""
        methods = {
            "bash": self._bash,
            "read": self._read_file,
            "write": self._write_file,
            "edit": self._edit_file,
            "glob": self._glob,
            "grep": self._grep,
            "agent": self._agent,
            "search": self._web_search,
            "fetch": self._web_fetch,
        }

        if tool_name not in methods:
            return ToolResult(success=False, error=f"未知工具: {tool_name}", tool=tool_name)

        try:
            return await methods[tool_name](**kwargs)
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool=tool_name)

    async def _bash(self, command: str = None, timeout: int = 30, cwd: str = None, **kwargs) -> ToolResult:
        """执行Bash命令"""
        if not command:
            return ToolResult(success=False, error="缺少command参数", tool="bash")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            return ToolResult(
                success=result.returncode == 0,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                },
                tool="bash"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"命令超时({timeout}秒)", tool="bash")
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="bash")

    async def _read_file(self, path: str = None, lines: int = None, offset: int = None, **kwargs) -> ToolResult:
        """读取文件"""
        if not path:
            return ToolResult(success=False, error="缺少path参数", tool="read")

        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}", tool="read")

            content = file_path.read_text(encoding="utf-8")
            num_lines = len(content.splitlines())

            if offset:
                line_list = content.splitlines()
                content = "\n".join(line_list[offset:])
            if lines:
                line_list = content.splitlines()
                content = "\n".join(line_list[:lines])

            return ToolResult(
                success=True,
                output={
                    "path": str(file_path),
                    "content": content,
                    "numLines": num_lines
                },
                tool="read"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="read")

    async def _write_file(self, path: str = None, content: str = None, **kwargs) -> ToolResult:
        """写入文件"""
        if not path:
            return ToolResult(success=False, error="缺少path参数", tool="write")
        if content is None:
            return ToolResult(success=False, error="缺少content参数", tool="write")

        try:
            file_path = Path(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output={"path": str(file_path), "size": len(content)},
                tool="write"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="write")

    async def _edit_file(self, path: str = None, old_string: str = None, new_string: str = None, **kwargs) -> ToolResult:
        """编辑文件"""
        if not path or old_string is None or new_string is None:
            return ToolResult(success=False, error="缺少必要参数", tool="edit")

        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return ToolResult(success=False, error=f"文件不存在: {path}", tool="edit")

            content = file_path.read_text(encoding="utf-8")
            if old_string not in content:
                return ToolResult(success=False, error="未找到要替换的文本", tool="edit")

            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                success=True,
                output={"path": str(file_path), "diff": f"- {old_string}\n+ {new_string}"},
                tool="edit"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="edit")

    async def _glob(self, pattern: str = None, cwd: str = None, **kwargs) -> ToolResult:
        """Glob搜索"""
        if not pattern:
            return ToolResult(success=False, error="缺少pattern参数", tool="glob")

        try:
            import fnmatch

            base = Path(cwd or ".").expanduser()
            matches = []

            for path in base.rglob("*"):
                if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(str(path), pattern):
                    matches.append(str(path))

            return ToolResult(
                success=True,
                output={"matches": matches, "count": len(matches)},
                tool="glob"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="glob")

    async def _grep(self, pattern: str = None, path: str = None, **kwargs) -> ToolResult:
        """Grep搜索"""
        if not pattern:
            return ToolResult(success=False, error="缺少pattern参数", tool="grep")

        try:
            matches = []
            base = Path(path or ".").expanduser()

            for file_path in base.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines(), 1):
                            if pattern in line:
                                matches.append({
                                    "path": str(file_path),
                                    "line": i,
                                    "content": line.strip()
                                })
                    except Exception:
                        pass

            return ToolResult(
                success=True,
                output={"matches": matches, "count": len(matches)},
                tool="grep"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="grep")

    async def _agent(self, prompt: str = None, task: str = None, **kwargs) -> ToolResult:
        """启动Claude Agent"""
        # 使用claude命令执行任务
        prompt_text = prompt or task
        if not prompt_text:
            return ToolResult(success=False, error="缺少prompt参数", tool="agent")

        try:
            # 创建临时文件存储任务
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt_text)
                task_file = f.name

            # 调用Claude CLI
            result = subprocess.run(
                ["claude", "--print", prompt_text],
                capture_output=True,
                text=True,
                timeout=120
            )

            os.unlink(task_file)

            return ToolResult(
                success=result.returncode == 0,
                output={"response": result.stdout, "error": result.stderr},
                tool="agent"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="agent")

    async def _web_search(self, query: str = None, **kwargs) -> ToolResult:
        """Web搜索 - 使用claude --web标志"""
        if not query:
            return ToolResult(success=False, error="缺少query参数", tool="search")

        try:
            # 尝试使用claude --web搜索
            cmd = ["claude", "--print", f"Search the web for: {query}"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            return ToolResult(
                success=result.returncode == 0,
                output={"results": result.stdout, "query": query},
                tool="search"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="search")

    async def _web_fetch(self, url: str = None, **kwargs) -> ToolResult:
        """抓取网页"""
        if not url:
            return ToolResult(success=False, error="缺少url参数", tool="fetch")

        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8", errors="ignore")

            return ToolResult(
                success=True,
                output={"url": url, "content": content[:5000], "size": len(content)},
                tool="fetch"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool="fetch")


# 全局实例
_claude_tools: Optional[ClaudeTools] = None


def get_claude_tools() -> ClaudeTools:
    global _claude_tools
    if _claude_tools is None:
        _claude_tools = ClaudeTools()
    return _claude_tools