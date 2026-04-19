"""
ZeusHammer Complete Memory System

完整记忆系统:
1. 短期记忆 (LRU缓存)
2. 长期记忆 (SQLite)
3. 向量记忆 (可选)
4. 上下文管理
5. 自动压缩
"""

import asyncio
import logging
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    VECTOR = "vector"
    WORKING = "working"


@dataclass
class MemoryItem:
    """记忆项"""
    key: str
    value: Any
    memory_type: MemoryType
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 1.0  # 0-1, 重要性分数
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class MemoryQuery:
    """记忆查询"""
    text: str = ""
    tags: List[str] = None
    memory_type: MemoryType = None
    limit: int = 10
    time_range: Tuple[float, float] = None  # (start, end)


class ShortTermMemory:
    """
    短期记忆 - LRU缓存

    快速访问，高频使用的数据
    """

    def __init__(self, max_items: int = 100, ttl: float = 3600):
        self.max_items = max_items
        self.ttl = ttl
        self._cache: OrderedDict[str, MemoryItem] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """获取记忆"""
        if key not in self._cache:
            return None

        item = self._cache[key]

        # TTL检查
        if time.time() - item.created_at > self.ttl:
            del self._cache[key]
            return None

        # 更新访问时间和计数
        item.accessed_at = time.time()
        item.access_count += 1

        # 移动到末尾 (LRU)
        self._cache.move_to_end(key)

        return item.value

    def set(self, key: str, value: Any, importance: float = 1.0, tags: List[str] = None):
        """设置记忆"""
        if key in self._cache:
            item = self._cache[key]
            item.value = value
            item.accessed_at = time.time()
            item.access_count += 1
            item.importance = importance
            if tags:
                item.tags = tags
        else:
            item = MemoryItem(
                key=key,
                value=value,
                memory_type=MemoryType.SHORT_TERM,
                importance=importance,
                tags=tags or [],
            )
            self._cache[key] = item

        # LRU淘汰
        while len(self._cache) > self.max_items:
            self._cache.popitem(last=False)

    def delete(self, key: str):
        """删除记忆"""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """清空"""
        self._cache.clear()

    def keys(self) -> List[str]:
        """获取所有键"""
        return list(self._cache.keys())

    def items(self) -> List[Tuple[str, Any]]:
        """获取所有项"""
        return [(k, v.value) for k, v in self._cache.items()]

    def search(self, pattern: str) -> List[Tuple[str, Any]]:
        """搜索记忆"""
        results = []
        pattern_lower = pattern.lower()

        for key, item in self._cache.items():
            if pattern_lower in str(item.value).lower():
                results.append((key, item.value))

        return results

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "type": "short_term",
            "size": len(self._cache),
            "max_items": self.max_items,
            "ttl": self.ttl,
        }


class LongTermMemory:
    """
    长期记忆 - SQLite

    持久化存储重要信息
    """

    def __init__(self, db_path: str = "~/.zueshammer/memory.db"):
        self.db_path = Path(db_path).expanduser()
        self._conn = None
        self._initialize_db()

    def _initialize_db(self):
        """初始化数据库"""
        import sqlite3
        import logging
        logger = logging.getLogger(__name__)

        self._use_memory_only = False
        self._memory_store = {}

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            logger.warning(f"无法创建目录 {self.db_path.parent}，使用内存存储")
            self._use_memory_only = True
            self._conn = None
            return

        try:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row

            # 创建表
            self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                importance REAL DEFAULT 1.0,
                tags TEXT,
                metadata TEXT,
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);

            CREATE TABLE IF NOT EXISTS memory_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_key TEXT NOT NULL,
                to_key TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_relations_from ON memory_relations(from_key);
            CREATE INDEX IF NOT EXISTS idx_relations_to ON memory_relations(to_key);
            """)

            self._conn.commit()
        except Exception as e:
            logger.warning(f"数据库初始化失败: {e}，使用内存存储")
            self._use_memory_only = True
            self._conn = None

    def get(self, key: str) -> Optional[Any]:
        """获取记忆"""
        if self._use_memory_only:
            return self._memory_store.get(key)

        cursor = self._conn.execute(
            """
            UPDATE memories
            SET accessed_at = ?, access_count = access_count + 1
            WHERE key = ?
            """,
            (time.time(), key)
        )

        if cursor.rowcount == 0:
            return None

        self._conn.commit()

        cursor = self._conn.execute(
            "SELECT value FROM memories WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()

        if row:
            return json.loads(row["value"])
        return None

    def set(
        self,
        key: str,
        value: Any,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        importance: float = 1.0,
        tags: List[str] = None,
    ):
        """设置记忆"""
        if self._use_memory_only:
            self._memory_store[key] = value
            return

        value_json = json.dumps(value, default=str)
        tags_json = json.dumps(tags or [])

        self._conn.execute(
            """
            INSERT INTO memories (key, value, memory_type, importance, tags, created_at, accessed_at, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                importance = excluded.importance,
                tags = excluded.tags,
                accessed_at = excluded.accessed_at,
                access_count = memories.access_count + 1
            """,
            (key, value_json, memory_type.value, importance, tags_json, time.time(), time.time())
        )

        self._conn.commit()

    def delete(self, key: str):
        """删除记忆"""
        if self._use_memory_only:
            self._memory_store.pop(key, None)
            return
        self._conn.execute("DELETE FROM memories WHERE key = ?", (key,))
        self._conn.execute("DELETE FROM memory_relations WHERE from_key = ? OR to_key = ?", (key, key))
        self._conn.commit()

    def search(
        self,
        text: str = None,
        tags: List[str] = None,
        memory_type: MemoryType = None,
        limit: int = 10,
    ) -> List[Dict]:
        """搜索记忆"""
        if self._use_memory_only:
            results = []
            for k, v in list(self._memory_store.items())[:limit]:
                results.append({
                    "key": k,
                    "value": v,
                    "memory_type": "memory_only",
                    "importance": 1.0,
                })
            return results

        conditions = []
        params = []

        if text:
            conditions.append("(key LIKE ? OR value LIKE ?)")
            params.extend([f"%{text}%", f"%{text}%"])

        if tags:
            for tag in tags:
                conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type.value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor = self._conn.execute(
            f"""
            SELECT * FROM memories
            WHERE {where_clause}
            ORDER BY importance DESC, accessed_at DESC
            LIMIT ?
            """,
            params + [limit]
        )

        results = []
        for row in cursor.fetchall():
            item = dict(row)
            item["tags"] = json.loads(item["tags"])
            item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else {}
            results.append(item)

        return results

    def get_recent(self, limit: int = 10) -> List[Dict]:
        """获取最近记忆"""
        if self._use_memory_only:
            return [{"key": k, "value": v} for k, v in list(self._memory_store.items())[:limit]]

        cursor = self._conn.execute(
            "SELECT * FROM memories ORDER BY accessed_at DESC LIMIT ?",
            (limit,)
        )

        results = []
        for row in cursor.fetchall():
            item = dict(row)
            item["tags"] = json.loads(item["tags"])
            item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else {}
            results.append(item)

        return results

    def add_relation(self, from_key: str, to_key: str, relation_type: str, strength: float = 1.0):
        """添加记忆关联"""
        self._conn.execute(
            """
            INSERT INTO memory_relations (from_key, to_key, relation_type, strength, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (from_key, to_key, relation_type, strength, time.time())
        )
        self._conn.commit()

    def get_related(self, key: str, relation_type: str = None, limit: int = 10) -> List[Dict]:
        """获取关联记忆"""
        conditions = ["(from_key = ? OR to_key = ?)"]
        params = [key, key]

        if relation_type:
            conditions.append("relation_type = ?")
            params.append(relation_type)

        where_clause = " AND ".join(conditions)

        cursor = self._conn.execute(
            f"""
            SELECT * FROM memory_relations
            WHERE {where_clause}
            ORDER BY strength DESC
            LIMIT ?
            """,
            params + [limit]
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        """获取统计"""
        cursor = self._conn.execute(
            "SELECT COUNT(*) as total, AVG(importance) as avg_importance FROM memories"
        )
        row = cursor.fetchone()

        return {
            "type": "long_term",
            "db_path": str(self.db_path),
            "total_memories": row["total"] or 0,
            "avg_importance": row["avg_importance"] or 0,
        }


class WorkingMemory:
    """
    工作记忆

    当前对话上下文
    """

    def __init__(self, max_messages: int = 50):
        self.max_messages = max_messages
        self._messages: List[Dict] = []
        self._variables: Dict[str, Any] = {}

    def add_message(self, role: str, content: str, metadata: Dict = None):
        """添加消息"""
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        self._messages.append(message)

        # 限制大小
        while len(self._messages) > self.max_messages:
            self._messages.pop(0)

    def get_messages(self, limit: int = None) -> List[Dict]:
        """获取消息"""
        if limit:
            return self._messages[-limit:]
        return self._messages.copy()

    def set_variable(self, key: str, value: Any):
        """设置变量"""
        self._variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取变量"""
        return self._variables.get(key, default)

    def clear(self):
        """清空工作记忆"""
        self._messages.clear()
        self._variables.clear()

    def get_context(self, max_tokens: int = 8000) -> str:
        """获取上下文文本"""
        lines = []

        for msg in self._messages:
            role = msg["role"]
            content = msg["content"]
            lines.append(f"{role}: {content}")

        context = "\n".join(lines)

        # 简单截断
        if len(context) > max_tokens * 4:  # 假设4字符=1 token
            context = context[-max_tokens * 4:]

        return context


class MemoryManager:
    """
    记忆管理器

    整合所有记忆类型
    """

    def __init__(
        self,
        short_term_max: int = 100,
        long_term_db: str = "~/.zueshammer/memory.db",
    ):
        self.short_term = ShortTermMemory(max_items=short_term_max)
        self.long_term = LongTermMemory(db_path=long_term_db)
        self.working = WorkingMemory()

    def remember(self, key: str, value: Any, **kwargs):
        """记住"""
        # 同时存入短期和长期
        self.short_term.set(key, value, **kwargs)
        self.long_term.set(key, value, **kwargs)

    def recall(self, key: str) -> Optional[Any]:
        """回忆"""
        # 优先从短期记忆获取
        value = self.short_term.get(key)

        if value is None:
            # 从长期记忆获取并回填短期
            value = self.long_term.get(key)
            if value is not None:
                self.short_term.set(key, value)

        return value

    def forget(self, key: str):
        """遗忘"""
        self.short_term.delete(key)
        self.long_term.delete(key)

    def search(self, query: MemoryQuery) -> List[Dict]:
        """搜索记忆"""
        # 短期记忆搜索
        short_results = []
        if not query.memory_type or query.memory_type == MemoryType.SHORT_TERM:
            if query.text:
                results = self.short_term.search(query.text)
                short_results = [{"key": k, "value": v, "type": "short_term"} for k, v in results]

        # 长期记忆搜索
        long_results = []
        if not query.memory_type or query.memory_type == MemoryType.LONG_TERM:
            long_results = self.long_term.search(
                text=query.text,
                tags=query.tags,
                limit=query.limit,
            )
            for r in long_results:
                r["type"] = "long_term"

        # 合并结果
        all_results = short_results + long_results

        # 按相关性排序 (简化版)
        all_results.sort(key=lambda x: x.get("importance", 1), reverse=True)

        return all_results[:query.limit]

    def get_conversation_context(self) -> str:
        """获取对话上下文"""
        return self.working.get_context()

    def get_all_stats(self) -> Dict:
        """获取所有统计"""
        return {
            "short_term": self.short_term.get_stats(),
            "long_term": self.long_term.get_stats(),
        }


# 别名 - 提供统一的导入接口
MemorySystem = MemoryManager
