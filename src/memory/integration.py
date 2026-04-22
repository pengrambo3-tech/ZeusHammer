"""
ZeusHammer 记忆集成模块

集成 OpenClaw 和 Hermes 记忆系统

使用方法:
```python
from src.memory.integration import MemoryIntegration

# 创建集成实例
integration = MemoryIntegration()

# 同步记忆
stats = integration.sync_all()
print(f"同步了 {stats['synced']} 条记忆")

# 搜索记忆
memories = integration.search("AI 代理")
for m in memories:
    print(f"[{m.source}] {m.content[:100]}")

# 获取统计
stats = integration.get_stats()
print(f"OpenClaw: {stats['openclaw_count']} 条")
print(f"Hermes: {stats['hermes_count']} 条")
```
"""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .memory_sync import MemorySync, MemoryBridge, SyncedMemory
from .unified import UnifiedMemory

logger = logging.getLogger(__name__)


class MemoryIntegration:
    """
    记忆集成

    统一访问 ZeusHammer、OpenClaw、Hermes 的记忆
    """

    def __init__(
        self,
        zeushammer_db: str = "~/.zeushammer/memory.db",
        auto_sync: bool = True,
    ):
        """
        初始化记忆集成

        Args:
            zeushammer_db: ZeusHammer 记忆数据库路径
            auto_sync: 是否自动同步
        """
        # ZeusHammer 记忆
        self.zeushammer_memory = UnifiedMemory(long_db=zeushammer_db)
        
        # 记忆桥接
        self.bridge = MemoryBridge()
        
        # 自动同步
        if auto_sync:
            logger.info("正在自动同步记忆...")
            self.sync_all()

    def sync_all(self) -> Dict[str, int]:
        """
        同步所有记忆源

        Returns:
            同步统计信息
        """
        stats = self.bridge.sync_now()
        
        # 同步到 ZeusHammer 记忆
        synced_memories = self.bridge.get_memories()
        for memory in synced_memories:
            # 保存到 ZeusHammer 记忆系统
            self.zeushammer_memory.save(
                f"synced_{memory.id}",
                {
                    "source": memory.source,
                    "content": memory.content,
                    "category": memory.category,
                    "tags": memory.tags,
                }
            )
        
        logger.info(f"同步完成：{stats.get('synced', 0)} 条记忆")
        
        return stats

    def search(self, query: str, sources: Optional[List[str]] = None) -> List[SyncedMemory]:
        """
        搜索记忆

        Args:
            query: 搜索关键词
            sources: 限定来源列表 [None/OpenClaw/Hermes]

        Returns:
            匹配的记忆列表
        """
        if sources:
            results = []
            for source in sources:
                results.extend(self.bridge.search(query))
            return results
        else:
            return self.bridge.search(query)

    def get_all_memories(self, source: Optional[str] = None) -> List[SyncedMemory]:
        """
        获取所有记忆

        Args:
            source: 限定来源（None/OpenClaw/Hermes）

        Returns:
            记忆列表
        """
        return self.bridge.get_memories(source)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        stats = self.bridge.get_stats()
        
        # 添加 ZeusHammer 记忆统计
        stats["zeushammer"] = {
            "short_term_count": len(self.zeushammer_memory._short),
            "database": str(self.zeushammer_memory._long_db),
        }
        
        return stats

    def export_all(self, output_path: str, format: str = "json"):
        """
        导出所有记忆

        Args:
            output_path: 输出文件路径
            format: 导出格式（json/markdown）
        """
        self.bridge.sync.export_memories(output_path, format)
        logger.info(f"已导出记忆到 {output_path}")


class MemoryQuery:
    """
    记忆查询引擎

    提供高级查询功能
    """

    def __init__(self, integration: MemoryIntegration):
        self.integration = integration

    def by_source(self, source: str) -> List[SyncedMemory]:
        """按来源查询"""
        return self.integration.get_all_memories(source)

    def by_category(self, category: str) -> List[SyncedMemory]:
        """按类别查询"""
        all_memories = self.integration.get_all_memories()
        return [m for m in all_memories if m.category == category]

    def by_tags(self, tags: List[str]) -> List[SyncedMemory]:
        """按标签查询"""
        all_memories = self.integration.get_all_memories()
        return [m for m in all_memories if any(tag in m.tags for tag in tags)]

    def by_date_range(
        self,
        start: float,
        end: float,
    ) -> List[SyncedMemory]:
        """按日期范围查询"""
        all_memories = self.integration.get_all_memories()
        return [
            m for m in all_memories
            if start <= m.created_at <= end
        ]

    def recent(self, days: int = 7) -> List[SyncedMemory]:
        """查询最近 N 天的记忆"""
        import time
        end = time.time()
        start = end - (days * 86400)
        return self.by_date_range(start, end)

    def top_tags(self, limit: int = 10) -> Dict[str, int]:
        """获取热门标签"""
        all_memories = self.integration.get_all_memories()
        tag_counts = {}
        
        for memory in all_memories:
            for tag in memory.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # 排序
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        
        return dict(sorted_tags[:limit])


# ========== 便捷函数 ==========

def quick_sync() -> Dict[str, int]:
    """快速同步所有记忆"""
    integration = MemoryIntegration()
    return integration.sync_all()


def quick_search(query: str) -> List[SyncedMemory]:
    """快速搜索记忆"""
    integration = MemoryIntegration()
    return integration.search(query)


def quick_stats() -> Dict[str, Any]:
    """快速获取统计"""
    integration = MemoryIntegration(auto_sync=False)
    return integration.get_stats()
