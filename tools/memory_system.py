#!/usr/bin/env python3
"""
ZeusHammer - 三层记忆系统
融合Hermes记忆 + 创新压缩算法
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import pickle
import zlib
import hashlib

from hermes_logging import get_logger

logger = get_logger("memory_system")

class TripleMemory:
    """
    三层记忆架构:
    
    1. 短期记忆 (Episodic) - 会话级, 向量化, 快速检索
    2. 中期技能记忆 (Procedural) - 技能图谱, 可复用模式
    3. 长期知识记忆 (Semantic) - 压缩存储, 永久知识
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path.home() / ".zueshammer" / "memory.db")
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = None
        self.vector_store = None  # 简化: 使用SQLite FTS5
        self.compressor = MemoryCompressor()
        
        # 统计
        self.stats = {
            "episodes": 0,
            "skills": 0,
            "knowledge": 0,
            "compressed_ratio": 0.0
        }
        
    async def start(self):
        """启动记忆系统"""
        logger.info("启动三层记忆系统...")
        
        # 初始化SQLite
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        
        # 创建表
        await self._create_tables()
        
        # 加载统计
        await self._load_stats()
        
        logger.info(f"✅ 记忆系统已启动, 当前记忆数: {self.stats}")
        
    async def stop(self):
        """停止记忆系统"""
        if self.conn:
            self.conn.close()
        logger.info("记忆系统已停止")
        
    async def _create_tables(self):
        """创建记忆表"""
        # 短期记忆表 (原始记录)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                type TEXT,
                content TEXT,  -- JSON
                timestamp INTEGER,
                embedding BLOB  -- 简化: 存储关键词而不是向量
            )
        """)
        
        # 技能记忆表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS procedural (
                id TEXT PRIMARY KEY,
                name TEXT,
                pattern TEXT,  -- 技能模式
                steps TEXT,    -- JSON步骤
                parameters TEXT,
                success_rate REAL DEFAULT 0.0,
                usage_count INTEGER DEFAULT 0,
                created_at INTEGER,
                last_used INTEGER
            )
        """)
        
        # 长期知识表 (压缩后)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic (
                id TEXT PRIMARY KEY,
                concept TEXT,
                compressed_content BLOB,  -- 压缩后的二进制
                references TEXT,  -- 关联的episode IDs
                importance REAL DEFAULT 0.5,
                created_at INTEGER
            )
        """)
        
        # 创建索引
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic(session_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_procedural_name ON procedural(name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_semantic_concept ON semantic(concept)")
        
        self.conn.commit()
        
    async def _load_stats(self):
        """加载统计信息"""
        cur = self.conn.cursor()
        self.stats["episodes"] = cur.execute("SELECT COUNT(*) FROM episodic").fetchone()[0]
        self.stats["skills"] = cur.execute("SELECT COUNT(*) FROM procedural").fetchone()[0]
        self.stats["knowledge"] = cur.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
        
    def generate_id(self) -> str:
        """生成唯一ID"""
        return f"mem_{int(time.time())}_{hash(str(time.time())) % 10000}"
        
    async def record_episode(self, episode: Dict[str, Any]):
        """记录短期记忆"""
        episode_id = self.generate_id()
        timestamp = episode.get("timestamp", int(time.time()))
        
        self.conn.execute(
            "INSERT INTO episodic VALUES (?, ?, ?, ?, ?)",
            (
                episode_id,
                episode.get("session_id", "default"),
                episode.get("type", "unknown"),
                json.dumps(episode.get("content", {})),
                timestamp,
                None  # embedding (简化实现)
            )
        )
        self.conn.commit()
        
        self.stats["episodes"] += 1
        
        # 触发记忆压缩检查 (每100条)
        if self.stats["episodes"] % 100 == 0:
            asyncio.create_task(self.compress_old_memories())
            
        logger.debug(f"记录短期记忆: {episode_id}")
        return episode_id
        
    async def find_similar_episodes(self, query: str, limit: int = 5) -> List[Dict]:
        """查找相似短期记忆 (简化: 基于关键词)"""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM episodic ORDER BY timestamp DESC LIMIT ?",
            (limit * 2,)
        )
        rows = cur.fetchall()
        
        # 简化匹配 - 实际应该用向量相似度
        results = []
        for row in rows:
            content = json.loads(row["content"])
            results.append({
                "id": row["id"],
                "type": row["type"],
                "content": content,
                "timestamp": row["timestamp"],
                "score": 0.5  # 简化
            })
            
        return results[:limit]
        
    async def create_skill(self, skill_data: Dict[str, Any]) -> str:
        """创建技能 (中期记忆)"""
        skill_id = self.generate_id()
        
        self.conn.execute(
            """
            INSERT INTO procedural 
            (id, name, pattern, steps, parameters, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                skill_id,
                skill_data["name"],
                skill_data.get("pattern", ""),
                json.dumps(skill_data.get("steps", [])),
                json.dumps(skill_data.get("parameters", [])),
                int(time.time())
            )
        )
        self.conn.commit()
        
        self.stats["skills"] += 1
        logger.info(f"✅ 创建新技能: {skill_data['name']} ({skill_id})")
        return skill_id
        
    async def find_skill(self, name: str) -> Optional[Dict]:
        """查找技能"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM procedural WHERE name = ?", (name,))
        row = cur.fetchone()
        
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "pattern": row["pattern"],
                "steps": json.loads(row["steps"]),
                "parameters": json.loads(row["parameters"]),
                "success_rate": row["success_rate"],
                "usage_count": row["usage_count"]
            }
        return None
        
    async def compress_old_memories(self):
        """压缩旧记忆 (创新算法)"""
        logger.info("开始记忆压缩...")
        
        # 找出30天前的短期记忆
        cutoff = int(time.time()) - (30 * 24 * 3600)
        cur = self.conn.cursor()
        
        cur.execute(
            "SELECT id, content, timestamp FROM episodic WHERE timestamp < ?",
            (cutoff,)
        )
        old_episodes = cur.fetchall()
        
        compressed_count = 0
        for episode in old_episodes:
            content = json.loads(episode["content"])
            
            # 1. 提取关键信息 (模式识别)
            compressed = self.compressor.compress_episode(content)
            
            if compressed:
                # 2. 创建知识节点
                await self._create_knowledge_node(compressed, [episode["id"]])
                
                # 3. 删除原始记忆 (可选: 保留索引)
                # self.conn.execute("DELETE FROM episodic WHERE id = ?", (episode["id"],))
                compressed_count += 1
                
        if compressed_count > 0:
            logger.info(f"压缩了 {compressed_count} 条旧记忆")
            
    async def _create_knowledge_node(self, compressed: Dict, source_ids: List[str]):
        """创建知识节点 (长期记忆)"""
        knowledge_id = self.generate_id()
        
        # 序列化并压缩
        raw = json.dumps(compressed).encode()
        compressed_blob = zlib.compress(raw)
        
        self.conn.execute(
            """
            INSERT INTO semantic 
            (id, concept, compressed_content, references, importance, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                knowledge_id,
                compressed.get("concept", "unknown"),
                compressed_blob,
                json.dumps(source_ids),
                compressed.get("importance", 0.5),
                int(time.time())
            )
        )
        self.conn.commit()
        
        self.stats["knowledge"] += 1
        
    def get_size_info(self) -> Dict[str, Any]:
        """获取存储大小信息"""
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        return {
            "database_size_mb": db_size / 1024 / 1024,
            "episodes": self.stats["episodes"],
            "skills": self.stats["skills"],
            "knowledge": self.stats["knowledge"],
            "compressed_ratio": self.stats["compressed_ratio"]
        }
        
    async def search_memory(self, query: str, memory_type: str = "all") -> List[Dict]:
        """搜索记忆"""
        results = []
        
        if memory_type in ["all", "episodic"]:
            results.extend(await self._search_episodic(query))
            
        if memory_type in ["all", "procedural"]:
            results.extend(await self._search_procedural(query))
            
        if memory_type in ["all", "semantic"]:
            results.extend(await self._search_semantic(query))
            
        # 按相关性排序
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:10]
        
    async def _search_episodic(self, query: str) -> List[Dict]:
        """搜索短期记忆"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM episodic ORDER BY timestamp DESC LIMIT 100")
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            content = json.loads(row["content"])
            # 简单关键词匹配
            score = self._simple_score(query, content)
            if score > 0:
                results.append({
                    "type": "episodic",
                    "id": row["id"],
                    "content": content,
                    "timestamp": row["timestamp"],
                    "score": score
                })
        return results
        
    async def _search_procedural(self, query: str) -> List[Dict]:
        """搜索技能"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM procedural")
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            score = self._simple_score(query, {"name": row["name"], "pattern": row["pattern"]})
            if score > 0:
                results.append({
                    "type": "procedural",
                    "id": row["id"],
                    "name": row["name"],
                    "steps": json.loads(row["steps"]),
                    "success_rate": row["success_rate"],
                    "score": score
                })
        return results
        
    async def _search_semantic(self, query: str) -> List[Dict]:
        """搜索知识"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM semantic")
        rows = cur.fetchall()
        
        results = []
        for row in rows:
            score = self._simple_score(query, {"concept": row["concept"]})
            if score > 0:
                # 解压知识
                decompressed = zlib.decompress(row["compressed_content"])
                content = json.loads(decompressed)
                results.append({
                    "type": "semantic",
                    "id": row["id"],
                    "concept": row["concept"],
                    "content": content,
                    "importance": row["importance"],
                    "score": score
                })
        return results
        
    def _simple_score(self, query: str, data: Dict) -> float:
        """简单的关键词匹配评分"""
        query_lower = query.lower()
        text = json.dumps(data, ensure_ascii=False).lower()
        
        if query_lower in text:
            return 0.8
        return 0.0


class MemoryCompressor:
    """记忆压缩器 - 创新算法"""
    
    def compress_episode(self, episode: Dict) -> Optional[Dict]:
        """压缩单条记忆"""
        try:
            compressed = {
                "timestamp": episode.get("timestamp"),
                "summary": self._extract_keywords(episode),
                "entities": self._extract_entities(episode),
                "actions": self._extract_actions(episode),
                "importance": self._calculate_importance(episode)
            }
            return compressed
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return None
            
    def _extract_keywords(self, episode: Dict) -> List[str]:
        """提取关键词"""
        # 简化: 返回关键字段名
        return list(episode.keys())
        
    def _extract_entities(self, episode: Dict) -> List[str]:
        """提取实体 (文件名、路径、URL等)"""
        entities = []
        content = episode.get("content", {})
        
        def scan(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if any(keyword in k.lower() for keyword in ["file", "path", "url", "name"]):
                        entities.append(str(v))
                    scan(v)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)
                    
        scan(content)
        return list(set(entities))
        
    def _extract_actions(self, episode: Dict) -> List[str]:
        """提取动作"""
        return episode.get("actions", [])
        
    def _calculate_importance(self, episode: Dict) -> float:
        """计算重要性 (0-1)"""
        # 基于: 类型、时长、是否错误、频率
        importance = 0.5  # 默认
        
        if episode.get("type") == "error":
            importance += 0.3  # 错误更重要
        if episode.get("duration", 0) > 60:
            importance += 0.2  # 长任务更重要
            
        return min(1.0, importance)


# 全局实例
_memory_instance = None

def get_memory() -> TripleMemory:
    """获取记忆系统单例"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = TripleMemory()
    return _memory_instance
