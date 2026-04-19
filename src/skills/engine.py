"""
ZeusHammer 技能引擎

原创设计的技能系统。

融合设计参考:
- Hermes的技能格式 (SKILL.md + YAML frontmatter)
- ClaudeCode的渐进式披露
- OpenClaw的技能组合

但架构和实现是原创的。

核心概念:
- Skill: 技能包，包含指令和元数据
- SkillFile: 技能文件，支持Markdown格式
- Engine: 技能引擎，负责加载和执行
"""

import asyncio
import logging
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    platform: str = ""  # macos, linux, windows
    hidden: bool = False


@dataclass
class Skill:
    """技能"""
    metadata: SkillMetadata
    content: str  # 完整内容
    file_path: Path
    linked_files: Dict[str, List[str]] = field(default_factory=dict)  # category -> files

    @property
    def name(self) -> str:
        return self.metadata.name


class SkillEngine:
    """
    技能引擎

    原创设计，统一管理所有技能。

    特点:
    - 渐进式加载 (按需加载内容)
    - 元数据索引 (快速搜索)
    - 平台过滤 (仅加载适用的技能)
    - 技能组合 (支持依赖)
    """

    def __init__(
        self,
        skills_dir: str = "~/.zueshammer/skills",
        auto_load: bool = True,
        event_bus=None
    ):
        self.skills_dir = Path(skills_dir).expanduser()
        self.auto_load = auto_load
        self.event_bus = event_bus

        # 技能索引
        self._skills: Dict[str, Skill] = {}
        self._by_category: Dict[str, List[str]] = {}
        self._by_tag: Dict[str, List[str]] = {}

        # 平台
        import platform
        self._platform = platform.system().lower()

    async def load_all(self):
        """加载所有技能"""
        logger.info(f"加载技能目录: {self.skills_dir}")

        if not self.skills_dir.exists():
            logger.warning(f"技能目录不存在: {self.skills_dir}")
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return

        # 递归扫描
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            try:
                skill = await self._load_skill(skill_file)
                if skill:
                    self._register_skill(skill)
            except Exception as e:
                logger.error(f"加载技能失败: {skill_file} - {e}")

        logger.info(f"已加载 {len(self._skills)} 个技能")

    async def _load_skill(self, skill_file: Path) -> Optional[Skill]:
        """加载单个技能"""
        try:
            content = skill_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"读取技能文件失败: {skill_file} - {e}")
            return None

        # 解析frontmatter
        metadata = self._parse_frontmatter(content)

        if not metadata.get("name"):
            # 使用文件名作为名称
            metadata["name"] = skill_file.parent.name

        # 检查平台兼容性
        if metadata.get("platform"):
            platforms = metadata["platform"]
            if isinstance(platforms, str):
                platforms = [platforms]
            if self._platform not in platforms:
                logger.debug(f"跳过不兼容平台的技能: {metadata['name']}")
                return None

        # 获取关联文件
        skill_dir = skill_file.parent
        linked_files = {}
        for subdir in ["references", "templates", "scripts", "assets"]:
            dir_path = skill_dir / subdir
            if dir_path.exists():
                files = [f.name for f in dir_path.iterdir() if f.is_file()]
                if files:
                    linked_files[subdir] = files

        # 获取分类
        category = self._get_category(skill_file)

        return Skill(
            metadata=SkillMetadata(
                name=metadata.get("name", skill_dir.name),
                description=metadata.get("description", ""),
                version=metadata.get("version", "1.0.0"),
                author=metadata.get("author", ""),
                category=category,
                tags=metadata.get("tags", []),
                requires=metadata.get("requires", []),
                platform=metadata.get("platform", ""),
                hidden=metadata.get("hidden", False)
            ),
            content=content,
            file_path=skill_file,
            linked_files=linked_files
        )

    def _parse_frontmatter(self, content: str) -> Dict:
        """解析YAML frontmatter"""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            return yaml.safe_load(parts[1]) or {}
        except Exception as e:
            logger.error(f"Frontmatter解析失败: {e}")
            return {}

    def _get_category(self, skill_file: Path) -> str:
        """获取技能分类"""
        try:
            rel = skill_file.parent.relative_to(self.skills_dir)
            parts = rel.parts
            if len(parts) > 1:
                return parts[0]
        except ValueError:
            pass
        return "general"

    def _register_skill(self, skill: Skill):
        """注册技能"""
        name = skill.name

        self._skills[name] = skill

        # 按分类索引
        cat = skill.metadata.category
        if cat not in self._by_category:
            self._by_category[cat] = []
        if name not in self._by_category[cat]:
            self._by_category[cat].append(name)

        # 按标签索引
        for tag in skill.metadata.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            if name not in self._by_tag[tag]:
                self._by_tag[tag].append(name)

        logger.debug(f"注册技能: {name} (分类: {cat})")

    async def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(name)

    async def view(self, name: str, file_path: str = None) -> Dict[str, Any]:
        """
        查看技能内容

        渐进式披露:
        1. 如果不传file_path，返回元数据 + 前几百字符
        2. 如果传file_path，返回指定文件内容
        """
        skill = self._skills.get(name)
        if not skill:
            return {"success": False, "error": f"技能不存在: {name}"}

        # 指定文件
        if file_path:
            return await self._load_linked_file(skill, file_path)

        # 返回元数据 + 内容摘要
        return {
            "success": True,
            "name": skill.name,
            "metadata": {
                "description": skill.metadata.description,
                "version": skill.metadata.version,
                "category": skill.metadata.category,
                "tags": skill.metadata.tags,
            },
            "content_preview": skill.content[:500],
            "linked_files": skill.linked_files,
            "has_full_content": len(skill.content) > 500
        }

    async def _load_linked_file(self, skill: Skill, file_path: str) -> Dict:
        """加载关联文件"""
        # 安全检查 - 防止路径遍历
        if ".." in file_path or file_path.startswith("/"):
            return {"success": False, "error": "无效的路径"}

        target = skill.file_path.parent / file_path

        if not target.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            content = target.read_text(encoding="utf-8")
            return {
                "success": True,
                "name": skill.name,
                "file": file_path,
                "content": content
            }
        except UnicodeDecodeError:
            return {"success": False, "error": "二进制文件"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_skills(
        self,
        category: str = None,
        tag: str = None,
        include_hidden: bool = False
    ) -> List[Dict]:
        """列出技能"""
        names = set()

        if category:
            names.update(self._by_category.get(category, []))
        if tag:
            names.update(self._by_tag.get(tag, []))
        if not category and not tag:
            names.update(self._skills.keys())

        result = []
        for name in names:
            skill = self._skills.get(name)
            if not skill:
                continue

            if skill.metadata.hidden and not include_hidden:
                continue

            result.append({
                "name": name,
                "description": skill.metadata.description,
                "category": skill.metadata.category,
                "tags": skill.metadata.tags
            })

        return result

    async def list_categories(self) -> List[str]:
        """列出所有分类"""
        return list(self._by_category.keys())

    async def search(self, query: str) -> List[Dict]:
        """搜索技能"""
        query_lower = query.lower()
        results = []

        for name, skill in self._skills.items():
            # 匹配名称
            if query_lower in name.lower():
                results.append({
                    "name": name,
                    "description": skill.metadata.description,
                    "match": "name"
                })
                continue

            # 匹配描述
            if query_lower in skill.metadata.description.lower():
                results.append({
                    "name": name,
                    "description": skill.metadata.description,
                    "match": "description"
                })
                continue

            # 匹配标签
            for tag in skill.metadata.tags:
                if query_lower in tag.lower():
                    results.append({
                        "name": name,
                        "description": skill.metadata.description,
                        "match": f"tag:{tag}"
                    })
                    break

        return results

    async def execute_skill(self, name: str, context: Dict = None) -> str:
        """
        执行技能

        返回技能内容供AI使用。
        实际执行由AI根据技能内容自行决定。
        """
        skill = self._skills.get(name)
        if not skill:
            return f"技能不存在: {name}"

        # 发布事件
        if self.event_bus:
            await self.event_bus.publish(type="skill.executed", data={
                "name": name,
                "category": skill.metadata.category
            })

        # 返回完整内容
        return skill.content

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "total": len(self._skills),
            "categories": len(self._by_category),
            "tags": len(self._by_tag),
            "hidden": sum(1 for s in self._skills.values() if s.metadata.hidden)
        }