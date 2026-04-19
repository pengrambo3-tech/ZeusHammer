#!/usr/bin/env python3
"""
ZeusHammer - 文件工具包装器
基于Hermes file_tools.py + ClaudeCode读写能力
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import json

from hermes_logging import get_logger

logger = get_logger("file_tools")

def read_file(file_path: str, limit: int = None, offset: int = 0) -> Dict[str, Any]:
    """读取文件 (ClaudeCode read工具)"""
    try:
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        with open(path, 'r', encoding='utf-8') as f:
            if offset > 0:
                for _ in range(offset):
                    f.readline()
                    
            if limit:
                lines = [f.readline() for _ in range(limit)]
                content = "".join(lines)
            else:
                content = f.read()
                
        return {
            "success": True,
            "file": {
                "filePath": str(path),
                "content": content,
                "numLines": len(content.splitlines()),
                "startLine": offset + 1,
                "totalLines": sum(1 for _ in open(path, 'r', encoding='utf-8'))
            }
        }
    except UnicodeDecodeError:
        # 二进制文件
        return {"success": False, "error": "无法读取二进制文件"}
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {e}")
        return {"success": False, "error": str(e)}


def write_file(file_path: str, content: str) -> Dict[str, Any]:
    """写入文件 (ClaudeCode write工具)"""
    try:
        path = Path(file_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return {
            "success": True,
            "file": {"filePath": str(path)},
            "message": f"文件已写入: {file_path}"
        }
    except Exception as e:
        logger.error(f"写入文件失败 {file_path}: {e}")
        return {"success": False, "error": str(e)}


def edit_file(file_path: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """编辑文件 (ClaudeCode edit工具)"""
    try:
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 精确替换 (ClaudeCode风格)
        if old_string not in content:
            return {"success": False, "error": "未找到要替换的字符串"}
            
        new_content = content.replace(old_string, new_string, 1)  # 只替换第一次出现
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return {"success": True, "message": "文件已编辑"}
    except Exception as e:
        logger.error(f"编辑文件失败 {file_path}: {e}")
        return {"success": False, "error": str(e)}


def search_files(pattern: str, path: str = ".", exclude_dirs: list = None) -> Dict[str, Any]:
    """搜索文件 (ClaudeCode glob工具)"""
    try:
        base = Path(path).expanduser().resolve()
        exclude = set(exclude_dirs or [])
        
        matches = []
        for file in base.rglob(pattern):
            if any(part in exclude for part in file.parts):
                continue
            matches.append(str(file))
            
        return {
            "success": True,
            "matches": matches,
            "count": len(matches)
        }
    except Exception as e:
        logger.error(f"搜索文件失败: {e}")
        return {"success": False, "error": str(e)}


def list_files(path: str = ".") -> Dict[str, Any]:
    """列出文件"""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return {"success": False, "error": f"路径不存在: {path}"}
            
        files = []
        for item in p.iterdir():
            files.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0
            })
            
        return {"success": True, "files": files}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_file_info(file_path: str) -> Dict[str, Any]:
    """获取文件信息"""
    try:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            return {"success": False, "error": f"文件不存在"}
            
        stat = path.stat()
        return {
            "success": True,
            "info": {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "is_dir": path.is_dir(),
                "is_file": path.is_file()
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
