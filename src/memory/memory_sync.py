"""
ZeusHammer 记忆同步系统

同步 OpenClaw 和 Hermes 的记忆文件

支持的记忆格式:
1. OpenClaw: ~/.openclaw/memory/*.md
2. Hermes: ~/.hermes/memory/*.db
3. ZeusHammer: ~/.zeushammer/memory.db
"""

import os
import re
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class MemorySource:
    """记忆源"""
    name: str
    path: Path
    format: str  # "markdown" or "sqlite"
    last_sync: Optional[float] = None
    memory_count: int = 0


@dataclass
class SyncedMemory:
    """同步的记忆"""
    id: str
    source: str
    content: str
    category: str
    tags: List[str]
    created_at: float
    updated_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemorySync:
    """
    记忆同步系统

    功能:
    1. 识别 OpenClaw 和 Hermes 记忆文件
    2. 解析不同格式的记忆
    3. 同步到 ZeusHammer 统一记忆系统
    4. 双向同步支持
    """

    def __init__(self, target_db: str = "~/.zeushammer/memory.db"):
        self.target_db = Path(target_db).expanduser()
        
        # 记忆源
        self.sources: List[MemorySource] = []
        
        # 已同步的记忆
        self._synced_memories: Dict[str, SyncedMemory] = {}
        
        # 同步统计
        self._sync_stats = {
            "total_synced": 0,
            "from_openclaw": 0,
            "from_hermes": 0,
            "errors": 0,
        }
        
        # 发现记忆源
        self._discover_sources()

    def _discover_sources(self):
        """自动发现记忆源"""
        logger.info("正在发现记忆源...")

        # 1. OpenClaw 记忆
        openclaw_paths = [
            Path.home() / ".openclaw" / "MEMORY.md",
            Path.home() / ".openclaw" / "workspace" / "MEMORY.md",
            Path.home() / ".openclaw" / "memory",
        ]
        
        for path in openclaw_paths:
            if path.exists():
                self.sources.append(MemorySource(
                    name="OpenClaw",
                    path=path,
                    format="markdown",
                ))
                logger.info(f"发现 OpenClaw 记忆：{path}")

        # 2. Hermes 记忆
        hermes_paths = [
            Path.home() / ".hermes" / "memory.db",
            Path.home() / ".hermes" / "data" / "memory.db",
        ]
        
        for path in hermes_paths:
            if path.exists():
                self.sources.append(MemorySource(
                    name="Hermes",
                    path=path,
                    format="sqlite",
                ))
                logger.info(f"发现 Hermes 记忆：{path}")

        logger.info(f"共发现 {len(self.sources)} 个记忆源")

    def sync_all(self) -> Dict[str, int]:
        """
        同步所有记忆源

        Returns:
            同步统计信息
        """
        logger.info("开始同步所有记忆源...")
        
        stats = {
            "synced": 0,
            "skipped": 0,
            "errors": 0,
        }

        for source in self.sources:
            try:
                if source.format == "markdown":
                    count = self._sync_markdown_source(source)
                elif source.format == "sqlite":
                    count = self._sync_sqlite_source(source)
                else:
                    logger.warning(f"未知格式：{source.format}")
                    continue
                
                stats["synced"] += count
                source.last_sync = datetime.now().timestamp()
                source.memory_count = count
                
            except Exception as e:
                logger.error(f"同步 {source.name} 失败：{e}")
                stats["errors"] += 1
                self._sync_stats["errors"] += 1

        self._sync_stats["total_synced"] = stats["synced"]
        
        logger.info(f"同步完成：{stats['synced']} 条记忆")
        
        return stats

    def _sync_markdown_source(self, source: MemorySource) -> int:
        """
        同步 Markdown 格式记忆 (OpenClaw)

        OpenClaw 记忆格式:
        ```markdown
        # MEMORY.md - 重要教训库

        ## 记住：不要重复犯错！

        ### ⚠️ 失忆症问题（2026-04-10）

        **问题：** 每次会话重启，我就像失忆症患者...

        **表现：**
        - Boss 问"你找一下记忆"，我还在那里猜测

        **根本原因：**
        - 每次会话开始，我没有自动读取 MEMORY.md

        **解决方案：**
        1. ✅ 已更新 HEARTBEAT.md
        2. ✅ 已更新 SOUL.md
        ```
        """
        logger.info(f"同步 Markdown 记忆：{source.path}")
        
        synced_count = 0
        
        if source.path.is_file():
            # 单个文件
            memories = self._parse_openclaw_memory(source.path)
            for memory in memories:
                self._save_memory(memory)
                synced_count += 1
                
        elif source.path.is_dir():
            # 目录（多个 .md 文件）
            for md_file in source.path.glob("*.md"):
                memories = self._parse_openclaw_memory(md_file)
                for memory in memories:
                    self._save_memory(memory)
                    synced_count += 1
        
        self._sync_stats["from_openclaw"] = synced_count
        
        return synced_count

    def _parse_openclaw_memory(self, file_path: Path) -> List[SyncedMemory]:
        """解析 OpenClaw 记忆文件"""
        memories = []
        
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # 按章节分割
            sections = re.split(r'###\s+', content)
            
            for section in sections[1:]:  # 跳过标题
                # 提取标题
                title_match = re.match(r'(.+?)\n', section)
                if not title_match:
                    continue
                
                title = title_match.group(1).strip()
                
                # 提取内容
                body = section[len(title)+1:].strip()
                
                # 提取标签
                tags = self._extract_tags(body)
                
                # 提取日期
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title)
                created_at = datetime.strptime(date_match.group(1), '%Y-%m-%d').timestamp() if date_match else datetime.now().timestamp()
                
                # 创建记忆对象
                memory = SyncedMemory(
                    id=f"openclaw_{hashlib.md5(title.encode()).hexdigest()[:12]}",
                    source="OpenClaw",
                    content=f"{title}\n\n{body}",
                    category="lesson",
                    tags=tags,
                    created_at=created_at,
                    updated_at=datetime.now().timestamp(),
                    metadata={
                        "file": str(file_path),
                        "original_title": title,
                    }
                )
                
                memories.append(memory)
            
            logger.info(f"从 {file_path} 解析出 {len(memories)} 条记忆")
            
        except Exception as e:
            logger.error(f"解析 {file_path} 失败：{e}")
        
        return memories

    def _sync_sqlite_source(self, source: MemorySource) -> int:
        """
        同步 SQLite 格式记忆 (Hermes)

        Hermes 记忆表结构:
        ```sql
        CREATE TABLE memories (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            importance INTEGER DEFAULT 1,
            category TEXT DEFAULT 'general',
            tags TEXT,
            created_at REAL NOT NULL,
            last_accessed REAL,
            access_count INTEGER DEFAULT 0
        );
        ```
        """
        logger.info(f"同步 SQLite 记忆：{source.path}")
        
        synced_count = 0
        
        try:
            conn = sqlite3.connect(str(source.path))
            conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories")
            
            for row in cursor.fetchall():
                memory = SyncedMemory(
                    id=f"hermes_{row['key']}",
                    source="Hermes",
                    content=row['value'],
                    category=row.get('category', 'general'),
                    tags=json.loads(row.get('tags', '[]')) if row.get('tags') else [],
                    created_at=row.get('created_at', datetime.now().timestamp()),
                    updated_at=row.get('last_accessed', datetime.now().timestamp()),
                    metadata={
                        "importance": row.get('importance', 1),
                        "access_count": row.get('access_count', 0),
                        "original_key": row['key'],
                    }
                )
                
                self._save_memory(memory)
                synced_count += 1
            
            conn.close()
            
            self._sync_stats["from_hermes"] = synced_count
            
            logger.info(f"从 Hermes 同步 {synced_count} 条记忆")
            
        except Exception as e:
            logger.error(f"同步 Hermes 记忆失败：{e}")
            self._sync_stats["errors"] += 1
        
        return synced_count

    def _extract_tags(self, content: str) -> List[str]:
        """从内容提取标签"""
        tags = []
        
        # 提取 #标签
        hashtag_matches = re.findall(r'#(\w+)', content)
        tags.extend(hashtag_matches)
        
        # 提取关键词（简单实现）
        if "问题" in content:
            tags.append("问题")
        if "解决" in content:
            tags.append("解决")
        if "错误" in content:
            tags.append("错误")
        if "教训" in content:
            tags.append("教训")
        
        return list(set(tags))

    def _save_memory(self, memory: SyncedMemory):
        """保存记忆到 ZeusHammer 数据库"""
        try:
            # 创建数据库连接
            self.target_db.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.target_db))
            
            cursor = conn.cursor()
            
            # 创建表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS synced_memories (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    tags TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL,
                    metadata TEXT
                )
            """)
            
            # 插入或更新
            cursor.execute("""
                INSERT OR REPLACE INTO synced_memories 
                (id, source, content, category, tags, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id,
                memory.source,
                memory.content,
                memory.category,
                json.dumps(memory.tags),
                memory.created_at,
                memory.updated_at,
                json.dumps(memory.metadata),
            ))
            
            conn.commit()
            conn.close()
            
            self._synced_memories[memory.id] = memory
            
        except Exception as e:
            logger.error(f"保存记忆失败：{e}")
            raise

    def search_memories(self, query: str, source: Optional[str] = None) -> List[SyncedMemory]:
        """
        搜索记忆

        Args:
            query: 搜索关键词
            source: 限定来源（OpenClaw/Hermes/None）

        Returns:
            匹配的记忆列表
        """
        results = []
        
        try:
            conn = sqlite3.connect(str(self.target_db))
            conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            
            if source:
                cursor.execute("""
                    SELECT * FROM synced_memories 
                    WHERE content LIKE ? AND source = ?
                """, (f"%{query}%", source))
            else:
                cursor.execute("""
                    SELECT * FROM synced_memories 
                    WHERE content LIKE ?
                """, (f"%{query}%",))
            
            for row in cursor.fetchall():
                memory = SyncedMemory(
                    id=row['id'],
                    source=row['source'],
                    content=row['content'],
                    category=row['category'],
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                )
                results.append(memory)
            
            conn.close()
            
        except Exception as e:
            logger.error(f"搜索记忆失败：{e}")
        
        return results

    def get_sync_stats(self) -> Dict[str, Any]:
        """获取同步统计信息"""
        return {
            "sources": [
                {
                    "name": s.name,
                    "path": str(s.path),
                    "format": s.format,
                    "last_sync": datetime.fromtimestamp(s.last_sync).isoformat() if s.last_sync else None,
                    "memory_count": s.memory_count,
                }
                for s in self.sources
            ],
            "stats": self._sync_stats,
            "total_memories": len(self._synced_memories),
        }

    def export_memories(self, output_path: str, format: str = "json"):
        """导出记忆"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            data = [
                {
                    "id": m.id,
                    "source": m.source,
                    "content": m.content,
                    "category": m.category,
                    "tags": m.tags,
                    "created_at": m.created_at,
                    "metadata": m.metadata,
                }
                for m in self._synced_memories.values()
            ]
            
            with open(output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"已导出 {len(data)} 条记忆到 {output}")
        
        elif format == "markdown":
            # 按来源分组
            by_source = {}
            for m in self._synced_memories.values():
                if m.source not in by_source:
                    by_source[m.source] = []
                by_source[m.source].append(m)
            
            with open(output, "w", encoding="utf-8") as f:
                f.write("# ZeusHammer 同步记忆\n\n")
                f.write(f"同步时间：{datetime.now().isoformat()}\n\n")
                
                for source, memories in by_source.items():
                    f.write(f"## {source} ({len(memories)} 条)\n\n")
                    for i, m in enumerate(memories, 1):
                        f.write(f"### {i}. {m.content[:100]}...\n\n")
                        f.write(f"**标签:** {', '.join(m.tags)}\n\n")
                        f.write(f"**创建时间:** {datetime.fromtimestamp(m.created_at).isoformat()}\n\n")
                        f.write("---\n\n")
            
            logger.info(f"已导出记忆到 {output}")


class MemoryBridge:
    """
    记忆桥梁

    在 ZeusHammer、OpenClaw、Hermes 之间双向同步记忆
    """

    def __init__(self):
        self.sync = MemorySync()
        
        # 同步方向
        self.sync_directions = {
            "openclaw_to_zeushammer": True,
            "hermes_to_zeushammer": True,
            "zeushammer_to_openclaw": False,
            "zeushammer_to_hermes": False,
        }

    def enable_bidirectional_sync(self):
        """启用双向同步"""
        self.sync_directions["zeushammer_to_openclaw"] = True
        self.sync_directions["zeushammer_to_hermes"] = True
        logger.info("已启用双向同步")

    def sync_now(self) -> Dict[str, int]:
        """立即同步"""
        return self.sync.sync_all()

    def get_memories(self, source: Optional[str] = None) -> List[SyncedMemory]:
        """获取记忆"""
        if source:
            return self.sync.search_memories("", source)
        else:
            return list(self.sync._synced_memories.values())

    def search(self, query: str) -> List[SyncedMemory]:
        """搜索记忆"""
        return self.sync.search_memories(query)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.sync.get_sync_stats()
