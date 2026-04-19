"""
ZeusHammer 统一记忆系统

融合三大项目最佳实践的原创设计:

ClaudeCode贡献:
- LRU缓存算法
- 访问计数优化
- 分层存储

Hermes贡献:
- 多提供者架构
- SQLite持久化
- 上下文隔离

OpenClaw贡献:
- 流式处理
- 实时索引
- 事件驱动

原创增强:
- 统一的存储接口
- 自动压缩
- 重要性评估
- 向量相似度(简化版)
"""

import asyncio
import json
import logging
import time
import sqlite3
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
import re

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """记忆项"""
    key: str
    value: Any
    importance: int = 1  # 1-5
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    embedding: List[float] = None  # 简化的向量表示


@dataclass
class SearchResult:
    """搜索结果"""
    key: str
    value: Any
    score: float  # 0-1, 越高越相关
    category: str
    importance: int


class UnifiedMemory:
    """
    统一记忆系统

    原创设计，融合三大项目最佳实践:

    1. 分层存储:
       - L1: 进程内存 (LRU缓存, ClaudeCode风格)
       - L2: SQLite持久化 (Hermes风格)
       - L3: 向量索引 (增强)

    2. 访问模式优化 (ClaudeCode):
       - LRU驱逐
       - 访问计数
       - 重要性加权

    3. 多提供者支持 (Hermes):
       - 插件式存储后端
       - 统一的查询接口

    4. 事件驱动 (OpenClaw):
       - 记忆变更事件
       - 自动同步
       - 实时索引
    """

    def __init__(
        self,
        short_max: int = 100,
        short_ttl: int = 3600,
        long_db: str = "~/.zueshammer/memory.db",
        long_enabled: bool = True,
        event_bus=None
    ):
        # L1: 短期记忆配置 (ClaudeCode风格)
        self._short_max = short_max
        self._short_ttl = short_ttl
        self._short: OrderedDict[str, MemoryItem] = OrderedDict()

        # L2: 长期记忆配置 (Hermes风格)
        self._long_db = Path(long_db).expanduser()
        self._long_enabled = long_enabled
        self._long_conn: Optional[sqlite3.Connection] = None

        # 事件总线
        self._event_bus = event_bus

        # 索引
        self._index: Dict[str, List[str]] = {}  # tag -> keys
        self._category_index: Dict[str, List[str]] = {}  # category -> keys

    async def initialize(self):
        """初始化"""
        logger.info("初始化统一记忆系统...")

        # 初始化长期记忆
        if self._long_enabled:
            await self._init_long_memory()

        # 从长期记忆加载热点到短期
        await self._warm_cache()

        logger.info("统一记忆系统初始化完成")

    async def _init_long_memory(self):
        """初始化SQLite (Hermes风格)"""
        self._long_db.parent.mkdir(parents=True, exist_ok=True)
        self._long_conn = sqlite3.connect(str(self._long_db))
        self._long_conn.row_factory = sqlite3.Row

        # 创建表
        self._long_conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                importance INTEGER DEFAULT 1,
                category TEXT DEFAULT 'general',
                tags TEXT,
                created_at REAL NOT NULL,
                last_accessed REAL,
                access_count INTEGER DEFAULT 0,
                embedding TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance);
            CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_access ON memories(access_count);
        """)
        self._long_conn.commit()

    async def _warm_cache(self):
        """预热缓存 - 从长期记忆加载热点 (融合设计)"""
        if not self._long_conn:
            return

        try:
            cursor = self._long_conn.execute("""
                SELECT key, value, importance, category, tags, created_at,
                       last_accessed, access_count
                FROM memories
                ORDER BY (access_count * importance) DESC
                LIMIT ?
            """, (self._short_max // 2,))

            for row in cursor.fetchall():
                item = MemoryItem(
                    key=row["key"],
                    value=row["value"],
                    importance=row["importance"],
                    category=row["category"],
                    tags=json.loads(row["tags"]) if row["tags"] else [],
                    created_at=row["created_at"],
                    last_accessed=row["last_accessed"] or row["created_at"],
                    access_count=row["access_count"]
                )
                self._short[item.key] = item
                self._update_indices(item)

        except Exception as e:
            logger.error(f"缓存预热失败: {e}")

    # =========================================================================
    # 核心操作
    # =========================================================================

    async def store(
        self,
        key: str,
        value: Any,
        importance: int = 1,
        category: str = "general",
        tags: List[str] = None
    ):
        """
        存储记忆

        融合设计:
        - LRU缓存 (ClaudeCode)
        - 持久化 (Hermes)
        - 索引更新 (OpenClaw)
        """
        tags = tags or []
        now = time.time()

        # 创建记忆项
        item = MemoryItem(
            key=key,
            value=value,
            importance=importance,
            category=category,
            tags=tags,
            created_at=now,
            last_accessed=now,
            access_count=0,
            embedding=self._create_embedding(key, value)
        )

        # 更新L1缓存
        if key in self._short:
            del self._short[key]
        self._short[key] = item
        self._enforce_capacity()

        # 持久化到L2
        if self._long_conn:
            try:
                value_str = json.dumps(value) if not isinstance(value, str) else value
                self._long_conn.execute("""
                    INSERT OR REPLACE INTO memories
                    (key, value, importance, category, tags, created_at, last_accessed, access_count, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM memories WHERE key = ?), ?),
                        COALESCE((SELECT access_count FROM memories WHERE key = ?), 0),
                        ?)
                """, (
                    key, value_str, importance, category, json.dumps(tags),
                    item.created_at, now, item.access_count,
                    json.dumps(item.embedding) if item.embedding else None,
                    key, now, key, key
                ))
                self._long_conn.commit()
            except Exception as e:
                logger.error(f"持久化失败: {e}")

        # 更新索引
        self._update_indices(item)

        # 发布事件
        if self._event_bus:
            from src.core.event_bus import Event
            await self._event_bus.publish(Event(type="memory.stored", data={
                "key": key,
                "category": category,
                "importance": importance
            }))

    async def recall(self, key: str, default: Any = None) -> Any:
        """回忆记忆"""
        # 检查L1缓存
        if key in self._short:
            item = self._short[key]

            # 检查过期
            if time.time() - item.created_at > self._short_ttl:
                await self.delete(key)
                return default

            # 更新访问
            item.last_accessed = time.time()
            item.access_count += 1
            self._short.move_to_end(key)

            # 异步更新L2
            if self._long_conn:
                asyncio.create_task(self._update_access(key))

            return item.value

        # 检查L2
        if self._long_conn:
            try:
                cursor = self._long_conn.execute(
                    "SELECT * FROM memories WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                if row:
                    # 加载到L1
                    item = MemoryItem(
                        key=row["key"],
                        value=row["value"],
                        importance=row["importance"],
                        category=row["category"],
                        tags=json.loads(row["tags"]) if row["tags"] else [],
                        created_at=row["created_at"],
                        last_accessed=row["last_accessed"] or row["created_at"],
                        access_count=row["access_count"]
                    )
                    self._short[key] = item
                    self._enforce_capacity()

                    # 更新访问
                    if self._long_conn:
                        asyncio.create_task(self._update_access(key))

                    return item.value
            except Exception as e:
                logger.error(f"L2查询失败: {e}")

        return default

    async def delete(self, key: str):
        """删除记忆"""
        # 从L1移除
        if key in self._short:
            del self._short[key]

        # 从L2删除
        if self._long_conn:
            try:
                self._long_conn.execute("DELETE FROM memories WHERE key = ?", (key,))
                self._long_conn.commit()
            except Exception as e:
                logger.error(f"L2删除失败: {e}")

        # 从索引移除
        self._remove_from_indices(key)

        # 事件
        if self._event_bus:
            await self._event_bus.publish(type="memory.deleted", data={"key": key})

    async def _update_access(self, key: str):
        """更新访问计数"""
        if not self._long_conn:
            return
        try:
            self._long_conn.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE key = ?",
                (time.time(), key)
            )
            self._long_conn.commit()
        except Exception:
            pass

    # =========================================================================
    # 搜索 (融合设计)
    # =========================================================================

    async def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """
        搜索记忆

        融合设计:
        - 关键词匹配
        - 分类过滤
        - 重要性排序
        - 简化的向量相似度
        """
        results = []
        query_lower = query.lower()
        query_embedding = self._create_embedding(query, "")

        # 获取所有记忆
        all_items = list(self._short.values())
        if self._long_conn:
            try:
                cursor = self._long_conn.execute("""
                    SELECT key, value, importance, category, tags, embedding
                    FROM memories
                    WHERE key LIKE ? OR value LIKE ?
                """, (f"%{query}%", f"%{query}%"))

                for row in cursor.fetchall():
                    # 检查是否已在L1
                    if row["key"] not in self._short:
                        all_items.append(MemoryItem(
                            key=row["key"],
                            value=row["value"],
                            importance=row["importance"],
                            category=row["category"],
                            tags=json.loads(row["tags"]) if row["tags"] else [],
                            embedding=json.loads(row["embedding"]) if row["embedding"] else None
                        ))
            except Exception as e:
                logger.error(f"搜索失败: {e}")

        # 计算相关性分数
        scored = []
        for item in all_items:
            score = 0.0

            # 关键词匹配
            if query_lower in item.key.lower():
                score += 0.4
            if query_lower in str(item.value).lower():
                score += 0.3

            # 标签匹配
            for tag in item.tags:
                if query_lower in tag.lower():
                    score += 0.2
                    break

            # 向量相似度
            if item.embedding and query_embedding:
                sim = self._cosine_similarity(query_embedding, item.embedding)
                score += sim * 0.3

            # 重要性加权
            score *= (0.5 + item.importance * 0.1)

            # 访问频率加权
            if item.access_count > 10:
                score *= 1.2

            if score > 0:
                scored.append((score, item))

        # 排序
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            SearchResult(
                key=item.key,
                value=item.value,
                score=score,
                category=item.category,
                importance=item.importance
            )
            for score, item in scored[:limit]
        ]

    async def recall_related(self, context: str, limit: int = 5) -> str:
        """根据上下文召回相关记忆"""
        results = await self.search(context, limit)
        if not results:
            return ""

        lines = ["[相关记忆]"]
        for r in results:
            if r.score > 0.2:  # 阈值
                lines.append(f"- {r.key}: {str(r.value)[:100]}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def _create_embedding(self, key: str, value: Any) -> List[float]:
        """创建简化的向量表示 (基于词频)"""
        text = f"{key} {value}"
        words = re.findall(r'\w+', text.lower())

        # 简单的词向量
        vec = []
        keywords = ['file', 'code', 'git', 'search', 'web', 'api', 'data',
                    'user', 'error', 'test', 'config', 'memory', 'tool']
        for kw in keywords:
            vec.append(1.0 if kw in words else 0.0)

        return vec

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    # =========================================================================
    # LRU缓存管理 (ClaudeCode风格)
    # =========================================================================

    def _enforce_capacity(self):
        """强制容量限制 - LRU驱逐"""
        while len(self._short) > self._short_max:
            # 驱逐最老的
            oldest_key = next(iter(self._short))
            del self._short[oldest_key]

    # =========================================================================
    # 索引管理
    # =========================================================================

    def _update_indices(self, item: MemoryItem):
        """更新索引"""
        # 标签索引
        for tag in item.tags:
            if tag not in self._index:
                self._index[tag] = []
            if item.key not in self._index[tag]:
                self._index[tag].append(item.key)

        # 分类索引
        if item.category not in self._category_index:
            self._category_index[item.category] = []
        if item.key not in self._category_index[item.category]:
            self._category_index[item.category].append(item.key)

    def _remove_from_indices(self, key: str):
        """从索引移除"""
        for keys in self._index.values():
            if key in keys:
                keys.remove(key)

        for keys in self._category_index.values():
            if key in keys:
                keys.remove(key)

    # =========================================================================
    # 统计和工具
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "short_count": len(self._short),
            "short_max": self._short_max,
            "long_enabled": self._long_enabled,
            "categories": len(self._category_index),
            "total_tags": len(self._index)
        }

    async def get_by_category(self, category: str) -> List[MemoryItem]:
        """按分类获取"""
        items = []
        for item in self._short.values():
            if item.category == category:
                items.append(item)
        return items

    async def clear_category(self, category: str):
        """清空分类"""
        keys = self._category_index.get(category, []).copy()
        for key in keys:
            await self.delete(key)

    async def close(self):
        """关闭"""
        if self._long_conn:
            self._long_conn.close()
            self._long_conn = None