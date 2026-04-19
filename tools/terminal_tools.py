#!/usr/bin/env python3
"""
ZeusHammer - 终端工具包装器
基于Hermes terminal_tool.py + ClaudeCode exec能力
"""

import asyncio
import subprocess
import shlex
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from hermes_logging import get_logger

logger = get_logger("terminal_tools")

class TerminalTool:
    """终端命令执行器"""
    
    def __init__(self):
        self.working_dir = Path.home()
        self.env = {}
        
    async def execute(self, command: str, timeout: int = 30, 
                     working_dir: str = None) -> Dict[str, Any]:
        """执行终端命令"""
        try:
            cwd = Path(working_dir or self.working_dir).expanduser()
            
            # 创建子进程
            proc = await asyncio.create_subprocess_exec(
                *shlex.split(command),
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "success": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace')
                }
            except asyncio.TimeoutError:
                proc.kill()
                return {"success": False, "error": f"命令超时 ({timeout}s)"}
                
        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            return {"success": False, "error": str(e)}
            
    async def execute_shell(self, command: str) -> Dict[str, Any]:
        """执行Shell命令 (支持管道等)"""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            stdout, stderr = await proc.communicate()
            
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# 全局实例
_terminal_tool = TerminalTool()

async def terminal(command: str, timeout: int = 30, 
                   working_dir: str = None) -> Dict[str, Any]:
    """执行终端命令 (Hermes风格)"""
    return await _terminal_tool.execute(command, timeout, working_dir)
    
async def terminal_shell(command: str) -> str:
    """执行Shell并返回输出"""
    result = await _terminal_tool.execute_shell(command)
    return result.get("stdout", "") if result.get("success") else result.get("stderr", "")

def get_active_processes() -> list:
    """获取活动进程列表"""
    try:
        result = subprocess.run(
            ["ps", "aux"], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        return result.stdout.splitlines()
    except:
        return []

def is_persistent_env() -> bool:
    """检查是否为持久化环境"""
    return Path("/.dockerenv").exists() or os.environ.get("CONTAINER")
