"""
ZeusHammer 技能学习器

灵感来自 Rambo 的自我进化能力

核心功能:
1. 从工作记录自动提取技能
2. 优化触发模式
3. 技能评估和淘汰
4. 技能组合优化
"""

import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import json

from .local_brain import Skill, IntentType, WorkRecord

logger = logging.getLogger(__name__)


@dataclass
class SkillQuality:
    """技能质量评估"""
    skill_id: str
    success_rate: float  # 成功率
    avg_duration_ms: float  # 平均耗时
    usage_count: int  # 使用次数
    last_used: float  # 最后使用时间
    complexity: int  # 复杂度 1-5
    score: float  # 综合评分 0-100


@dataclass
class ExtractedSkill:
    """提取的技能"""
    name: str
    description: str
    trigger_patterns: List[str]
    intent_type: IntentType
    actions: List[Dict]
    examples: List[str]
    confidence: float  # 置信度 0-1


class SkillLearner:
    """
    技能学习器

    从工作记录中自动学习和优化技能
    """

    def __init__(self, skills_dir: Optional[str] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else None
        
        # 技能质量追踪
        self._quality_stats: Dict[str, SkillQuality] = {}
        
        # 学习历史
        self._learning_history: List[Dict] = []
        
        # 模式提取器
        self._pattern_extractor = PatternExtractor()
        
        # 技能优化器
        self._optimizer = SkillOptimizer()

    def learn_from_work(self, work: WorkRecord) -> Optional[Skill]:
        """
        从工作记录学习技能

        Args:
            work: 工作记录

        Returns:
            学习到的技能，如果无法学习则返回 None
        """
        logger.info(f"从工作记录学习技能：{work.id}")

        # 1. 检查是否已经转换为技能
        if work.converted_to_skill:
            logger.debug(f"工作 {work.id} 已经转换为技能")
            return None

        # 2. 检查工作是否成功
        if not work.success:
            logger.debug(f"工作 {work.id} 失败，不学习")
            return None

        # 3. 提取触发模式
        patterns = self._pattern_extractor.extract(work.input)
        if not patterns:
            logger.warning(f"无法从输入提取模式：{work.input}")
            return None

        # 4. 创建技能
        skill = self._create_skill(work, patterns)
        if skill:
            logger.info(f"成功学习技能：{skill.name}")
            work.converted_to_skill = True
            self._learning_history.append({
                "work_id": work.id,
                "skill_id": skill.id,
                "timestamp": time.time(),
            })

        return skill

    def _create_skill(self, work: WorkRecord, patterns: List[str]) -> Skill:
        """创建工作技能"""
        # 生成技能 ID
        skill_id = f"learned_{work.id}"
        
        # 生成技能名称
        name = self._generate_skill_name(work.input)
        
        # 生成描述
        description = f"从工作 {work.id} 学习的技能：{work.input[:50]}..."
        
        # 创建技能
        skill = Skill(
            id=skill_id,
            name=name,
            description=description,
            trigger_patterns=patterns,
            intent_type=work.intent.type,
            actions=work.actions,
            examples=[work.input],
            learned_from=work.id,
        )
        
        return skill

    def _generate_skill_name(self, input_text: str) -> str:
        """生成技能名称"""
        # 简单实现：取输入的前 20 个字符
        return f"Skill_{input_text[:20].replace(' ', '_')}"

    def evaluate_skill(self, skill: Skill, work: WorkRecord):
        """评估技能质量"""
        skill_id = skill.id
        
        if skill_id not in self._quality_stats:
            self._quality_stats[skill_id] = SkillQuality(
                skill_id=skill_id,
                success_rate=1.0 if work.success else 0.0,
                avg_duration_ms=work.duration_ms,
                usage_count=1,
                last_used=work.created_at,
                complexity=self._calculate_complexity(skill),
                score=50.0,
            )
        else:
            stats = self._quality_stats[skill_id]
            # 更新成功率
            total = stats.usage_count + 1
            success = (stats.success_rate * stats.usage_count) + (1 if work.success else 0)
            stats.success_rate = success / total
            # 更新平均耗时
            stats.avg_duration_ms = (
                (stats.avg_duration_ms * stats.usage_count + work.duration_ms) / total
            )
            stats.usage_count = total
            stats.last_used = work.created_at
            # 重新计算评分
            stats.score = self._calculate_score(stats)

    def _calculate_complexity(self, skill: Skill) -> int:
        """计算技能复杂度 (1-5)"""
        # 基于动作数量
        num_actions = len(skill.actions)
        if num_actions == 1:
            return 1
        elif num_actions <= 3:
            return 2
        elif num_actions <= 5:
            return 3
        elif num_actions <= 10:
            return 4
        else:
            return 5

    def _calculate_score(self, quality: SkillQuality) -> float:
        """
        计算技能综合评分

        评分因素:
        - 成功率 (40%)
        - 速度 (30%)
        - 使用频率 (20%)
        - 复杂度 (10%)
        """
        # 成功率得分 (0-40)
        success_score = quality.success_rate * 40
        
        # 速度得分 (0-30) - 越快得分越高
        # 假设 100ms 以内是优秀，1000ms 以上是差
        speed_score = max(0, 30 - (quality.avg_duration_ms / 1000) * 30)
        
        # 使用频率得分 (0-20) - 越常用得分越高
        usage_score = min(20, quality.usage_count * 2)
        
        # 复杂度得分 (0-10) - 越简单得分越高
        complexity_score = (6 - quality.complexity) * 2
        
        total = success_score + speed_score + usage_score + complexity_score
        return total

    def get_low_quality_skills(self, threshold: float = 30.0) -> List[str]:
        """获取低质量技能 ID 列表"""
        low_quality = []
        for skill_id, quality in self._quality_stats.items():
            if quality.score < threshold:
                low_quality.append(skill_id)
        return low_quality

    def should_retire_skill(self, skill: Skill, days_inactive: int = 30) -> bool:
        """判断是否应该淘汰某个技能"""
        if skill.id not in self._quality_stats:
            return False
        
        quality = self._quality_stats[skill.id]
        
        # 评分太低
        if quality.score < 20:
            return True
        
        # 长时间未使用
        inactive_days = (time.time() - quality.last_used) / 86400
        if inactive_days > days_inactive:
            return True
        
        return False

    def optimize_skill_patterns(self, skill: Skill) -> List[str]:
        """优化技能的触发模式"""
        return self._optimizer.optimize_patterns(skill)

    def save_skills(self, output_path: str):
        """保存技能到文件"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        skills_data = []
        for skill_id, quality in self._quality_stats.items():
            skills_data.append({
                "skill_id": skill_id,
                "quality": {
                    "success_rate": quality.success_rate,
                    "avg_duration_ms": quality.avg_duration_ms,
                    "usage_count": quality.usage_count,
                    "score": quality.score,
                }
            })
        
        with open(output, "w", encoding="utf-8") as f:
            json.dump(skills_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"已保存 {len(skills_data)} 个技能质量数据到 {output}")


class PatternExtractor:
    """模式提取器"""

    def extract(self, text: str) -> List[str]:
        """从文本提取触发模式"""
        patterns = []
        
        # 1. 提取关键词
        keywords = self._extract_keywords(text)
        patterns.extend(keywords)
        
        # 2. 提取动词 + 名词结构
        verb_noun = self._extract_verb_noun(text)
        patterns.extend(verb_noun)
        
        # 3. 提取正则模式
        regex_patterns = self._extract_regex_patterns(text)
        patterns.extend(regex_patterns)
        
        return patterns

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单实现：分词并返回前 5 个
        words = text.split()
        return words[:5]

    def _extract_verb_noun(self, text: str) -> List[str]:
        """提取动词 + 名词结构"""
        # TODO: 实现更复杂的 NLP 分析
        return []

    def _extract_regex_patterns(self, text: str) -> List[str]:
        """提取正则模式"""
        # TODO: 实现正则模式提取
        return []


class SkillOptimizer:
    """技能优化器"""

    def optimize_patterns(self, skill: Skill) -> List[str]:
        """优化触发模式"""
        optimized = []
        
        # 1. 去重
        unique_patterns = list(set(skill.trigger_patterns))
        
        # 2. 泛化
        generalized = self._generalize_patterns(unique_patterns)
        optimized.extend(generalized)
        
        # 3. 添加变体
        variants = self._add_variants(unique_patterns)
        optimized.extend(variants)
        
        return optimized

    def _generalize_patterns(self, patterns: List[str]) -> List[str]:
        """泛化模式"""
        # TODO: 实现模式泛化
        return patterns

    def _add_variants(self, patterns: List[str]) -> List[str]:
        """添加变体"""
        # TODO: 实现变体生成
        return patterns
