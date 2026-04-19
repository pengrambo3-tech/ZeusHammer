"""
ZeusHammer 内置工具

提供基础工具实现。
"""

import os
import asyncio
import subprocess
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List

from .executor import Tool, ToolSchema, PermissionLevel


class FileTools(Tool):
    """文件工具"""

    def __init__(self):
        super().__init__("file", "文件系统操作", "filesystem")

    async def execute(self, action: str = "list", path: str = ".", **kwargs) -> Dict:
        actions = {
            "read": self._read,
            "write": self._write,
            "list": self._list,
            "mkdir": self._mkdir,
            "delete": self._delete,
            "copy": self._copy,
            "move": self._move,
            "stat": self._stat,
        }
        return await actions.get(action, self._list)(path, **kwargs)

    async def _read(self, path: str, **kwargs) -> Dict:
        try:
            file_path = Path(path).expanduser().resolve()
            content = file_path.read_text(encoding="utf-8")
            return {
                "success": True,
                "path": str(file_path),
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _write(self, path: str, content: str = "", **kwargs) -> Dict:
        try:
            file_path = Path(path).expanduser().resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {
                "success": True,
                "path": str(file_path),
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _list(self, path: str = ".", **kwargs) -> Dict:
        try:
            dir_path = Path(path).expanduser().resolve()
            items = []
            for item in dir_path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "path": str(item)
                })
            return {
                "success": True,
                "path": str(dir_path),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _mkdir(self, path: str, **kwargs) -> Dict:
        try:
            dir_path = Path(path).expanduser().resolve()
            dir_path.mkdir(parents=True, exist_ok=True)
            return {"success": True, "path": str(dir_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _delete(self, path: str, **kwargs) -> Dict:
        try:
            file_path = Path(path).expanduser().resolve()
            if file_path.is_dir():
                file_path.rmdir()
            else:
                file_path.unlink()
            return {"success": True, "path": str(file_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _copy(self, src: str, dst: str, **kwargs) -> Dict:
        try:
            import shutil
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser().resolve()
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
            return {"success": True, "src": str(src_path), "dst": str(dst_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _move(self, src: str, dst: str, **kwargs) -> Dict:
        try:
            import shutil
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser().resolve()
            shutil.move(str(src_path), str(dst_path))
            return {"success": True, "src": str(src_path), "dst": str(dst_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _stat(self, path: str, **kwargs) -> Dict:
        try:
            file_path = Path(path).expanduser().resolve()
            stat = file_path.stat()
            return {
                "success": True,
                "path": str(file_path),
                "type": "dir" if file_path.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class TerminalTool(Tool):
    """终端工具"""

    def __init__(self):
        super().__init__("terminal", "执行Shell命令", "system")

    async def execute(self, command: str, timeout: int = 30, cwd: str = None, **kwargs) -> Dict:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return {
                "success": proc.returncode == 0,
                "command": command,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace")
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "error": f"超时: {timeout}秒"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class WebTools(Tool):
    """Web工具"""

    def __init__(self):
        super().__init__("web", "HTTP请求", "network")

    async def execute(self, action: str = "get", url: str = "", **kwargs) -> Dict:
        actions = {
            "get": self._get,
            "post": self._post,
            "fetch": self._fetch,
            "download": self._download,
        }
        return await actions.get(action, self._get)(url, **kwargs)

    async def _get(self, url: str, headers: Dict = None, **kwargs) -> Dict:
        try:
            import urllib.request
            req = urllib.request.Request(url)
            if headers:
                for k, v in headers.items():
                    req.add_header(k, v)

            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8", errors="replace")
                return {
                    "success": True,
                    "url": url,
                    "status": response.status,
                    "content": content,
                    "size": len(content)
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _post(self, url: str, data: str = "", content_type: str = "application/json", **kwargs) -> Dict:
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                data=data.encode("utf-8") if data else None
            )
            req.add_header("Content-Type", content_type)

            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8", errors="replace")
                return {
                    "success": True,
                    "url": url,
                    "status": response.status,
                    "content": content
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _fetch(self, url: str, **kwargs) -> Dict:
        return await self._get(url, **kwargs)

    async def _download(self, url: str, path: str, **kwargs) -> Dict:
        try:
            import urllib.request
            save_path = Path(path).expanduser()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, str(save_path))
            return {
                "success": True,
                "url": url,
                "path": str(save_path),
                "size": save_path.stat().st_size
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class GitTools(Tool):
    """Git工具"""

    def __init__(self):
        super().__init__("git", "Git版本控制", "vcs")

    async def execute(self, action: str = "status", path: str = ".", **kwargs) -> Dict:
        actions = {
            "status": self._status,
            "log": self._log,
            "diff": self._diff,
            "commit": self._commit,
            "push": self._push,
            "pull": self._pull,
            "branch": self._branch,
            "checkout": self._checkout,
            "clone": self._clone,
        }
        return await actions.get(action, self._status)(path, **kwargs)

    def _run_git(self, args: List[str], cwd: str = ".") -> Dict:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _status(self, path: str = ".", **kwargs) -> Dict:
        return self._run_git(["status", "-s"], path)

    async def _log(self, path: str = ".", limit: int = 10, **kwargs) -> Dict:
        return self._run_git(["log", f"-n{limit}", "--oneline"], path)

    async def _diff(self, path: str = ".", staged: bool = False, **kwargs) -> Dict:
        args = ["diff"]
        if staged:
            args.append("--cached")
        return self._run_git(args, path)

    async def _commit(self, path: str = ".", message: str = "", **kwargs) -> Dict:
        return self._run_git(["commit", "-m", message], path)

    async def _push(self, path: str = ".", remote: str = "origin", **kwargs) -> Dict:
        return self._run_git(["push", remote], path)

    async def _pull(self, path: str = ".", remote: str = "origin", **kwargs) -> Dict:
        return self._run_git(["pull", remote], path)

    async def _branch(self, path: str = ".", **kwargs) -> Dict:
        return self._run_git(["branch", "-a"], path)

    async def _checkout(self, path: str = ".", branch: str = "", create: bool = False, **kwargs) -> Dict:
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(branch)
        return self._run_git(args, path)

    async def _clone(self, path: str = ".", repo: str = "", **kwargs) -> Dict:
        return self._run_git(["clone", repo, path])


class SearchTool(Tool):
    """搜索工具"""

    def __init__(self):
        super().__init__("search", "搜索工具", "general")

    async def execute(self, query: str = "", **kwargs) -> Dict:
        return {
            "success": True,
            "query": query,
            "message": "搜索功能需要实现"
        }


class MemoryTools(Tool):
    """记忆工具"""

    def __init__(self, memory=None):
        super().__init__("memory", "记忆操作", "system")
        self.memory = memory

    async def execute(self, action: str = "store", key: str = "", value: str = "", **kwargs) -> Dict:
        if not self.memory:
            return {"success": False, "error": "记忆系统未初始化"}

        if action == "store":
            await self.memory.store(key, value)
            return {"success": True, "key": key}

        elif action == "recall":
            result = await self.memory.recall(key)
            return {"success": True, "key": key, "value": result}

        elif action == "search":
            results = await self.memory.search(value)
            return {"success": True, "results": results}

        return {"success": False, "error": f"未知操作: {action}"}


class BuiltinTools:
    """内置工具集合"""

    def __init__(self):
        self._tools = [
            FileTools(),
            TerminalTool(),
            WebTools(),
            GitTools(),
            SearchTool(),
        ]

    def get_all(self) -> List[Tool]:
        return self._tools

    def get_by_category(self, category: str) -> List[Tool]:
        return [t for t in self._tools if t.category == category]