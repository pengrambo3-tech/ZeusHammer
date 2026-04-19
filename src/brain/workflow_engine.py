"""
ZeusHammer Workflow Engine

工作流程引擎 - 整合本地大脑和所有模块

工作流程:
1. 接收用户指令
2. 本地大脑思考
3. 匹配技能 → 执行
4. 未匹配 → 调用大模型
5. 执行完成 → 学习新技能
6. 返回结果
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field

from .local_brain import (
    LocalBrain,
    Intent,
    Skill,
    WorkRecord,
    ThinkResult,
    IntentType,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    action: Callable
    on_success: str = ""  # 下一步名称
    on_failure: str = ""  # 失败时步骤
    max_retries: int = 3


@dataclass
class WorkflowResult:
    """工作流结果"""
    success: bool
    response: str
    skill_used: Optional[str] = None
    work_record_id: Optional[str] = None
    new_skill_learned: bool = False
    new_skill_name: str = ""
    steps_executed: List[str] = field(default_factory=list)
    duration_ms: float = 0


class WorkflowEngine:
    """
    工作流引擎

    核心流程:
    输入 → 意图理解 → 技能匹配 → 执行/大模型 → 学习 → 输出
    """

    def __init__(self, brain: LocalBrain):
        self.brain = brain

        # 执行统计
        self._stats = {
            "total_requests": 0,
            "skill_hits": 0,
            "llm_calls": 0,
            "skills_learned": 0,
        }

    async def process(self, user_input: str) -> WorkflowResult:
        """
        处理用户输入

        完整工作流:
        1. 本地大脑思考
        2. 匹配技能
        3. 执行或调用大模型
        4. 学习新技能
        5. 返回结果
        """
        start_time = time.time()
        self._stats["total_requests"] += 1

        steps = []

        try:
            # ===== 步骤1: 本地大脑思考 =====
            steps.append("think")
            think_result = self.brain.think(user_input)

            # ===== 步骤2: 技能匹配 =====
            steps.append("match")

            if think_result.matched_skill:
                # ===== 命中技能 =====
                self._stats["skill_hits"] += 1
                skill = think_result.matched_skill

                # 提取上下文
                intent = self.brain._understand_intent(user_input)
                context = self._extract_context(intent, user_input)

                # 执行技能
                steps.append("execute_skill")
                response = await self.brain.execute_skill(skill, context)

                duration_ms = (time.time() - start_time) * 1000

                return WorkflowResult(
                    success=True,
                    response=str(response),
                    skill_used=skill.name,
                    steps_executed=steps,
                    duration_ms=duration_ms,
                )

            else:
                # ===== 未命中，需要大模型 =====
                self._stats["llm_calls"] += 1

                # 执行大模型工作
                steps.append("llm_work")
                work_record = await self.brain.execute_work(user_input)

                # 检查是否学习到新技能
                new_skill = None
                for skill_id, skill in self.brain._skills.items():
                    if skill.learned_from == work_record.id:
                        new_skill = skill
                        self._stats["skills_learned"] += 1
                        break

                duration_ms = (time.time() - start_time) * 1000

                return WorkflowResult(
                    success=work_record.success,
                    response=work_record.output,
                    work_record_id=work_record.id,
                    new_skill_learned=new_skill is not None,
                    new_skill_name=new_skill.name if new_skill else "",
                    steps_executed=steps,
                    duration_ms=duration_ms,
                )

        except Exception as e:
            logger.error(f"Workflow error: {e}")
            duration_ms = (time.time() - start_time) * 1000

            return WorkflowResult(
                success=False,
                response=f"Error: {str(e)}",
                steps_executed=steps,
                duration_ms=duration_ms,
            )

    def _extract_context(self, intent: Intent, user_input: str) -> Dict[str, Any]:
        """提取执行上下文"""
        context = {
            "intent_type": intent.type.value,
            "language": intent.language,
        }

        # 添加实体
        context.update(intent.entities)

        # 提取参数
        if intent.type == IntentType.FILE_READ:
            paths = intent.entities.get("paths", [])
            if paths:
                context["path"] = paths[0]

        elif intent.type == IntentType.FILE_WRITE:
            paths = intent.entities.get("paths", [])
            if paths:
                context["path"] = paths[0]
            # 提取内容
            import re
            content_match = re.search(r'["\'](.*?)["\']', user_input)
            if content_match:
                context["content"] = content_match.group(1)

        elif intent.type == IntentType.COMMAND_EXEC:
            # 提取命令
            import re
            cmd_match = re.search(r'(?:命令|执行|run|execute)\s+(.*?)(?:\s|$)', user_input, re.I)
            if cmd_match:
                context["command"] = cmd_match.group(1).strip()

        return context

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            **self._stats,
            "brain": self.brain.get_stats(),
        }


class SkillMatcher:
    """
    技能匹配器

    提供更高级的技能匹配功能
    """

    def __init__(self, brain: LocalBrain):
        self.brain = brain

        # 相似度缓存
        self._similarity_cache: Dict[str, List[Tuple[Skill, float]]] = {}

    def find_similar_skills(
        self,
        user_input: str,
        limit: int = 5
    ) -> List[Tuple[Skill, float]]:
        """查找相似技能"""
        if user_input in self._similarity_cache:
            return self._similarity_cache[user_input]

        intent = self.brain._understand_intent(user_input)
        results = []

        for skill in self.brain._skills.values():
            score = self._calculate_similarity(user_input, intent, skill)
            if score > 0.3:
                results.append((skill, score))

        # 排序
        results.sort(key=lambda x: x[1], reverse=True)

        # 缓存
        self._similarity_cache[user_input] = results[:limit]

        return results[:limit]

    def _calculate_similarity(
        self,
        user_input: str,
        intent: Intent,
        skill: Skill
    ) -> float:
        """计算相似度"""
        score = 0.0
        user_lower = user_input.lower()

        # 意图类型匹配
        if skill.intent_type == intent.type:
            score += 0.3

        # 触发模式匹配
        for pattern in skill.trigger_patterns:
            pattern_lower = pattern.lower()

            # 包含匹配
            if pattern_lower in user_lower:
                score += 0.2

            # 词级别匹配
            pattern_words = set(pattern_lower.split())
            user_words = set(user_lower.split())
            overlap = len(pattern_words & user_words)
            if overlap > 0:
                score += 0.1 * overlap

        # 成功率
        if skill.usage_count > 0:
            score += (skill.success_count / skill.usage_count) * 0.2

        # 使用频率
        score += min(skill.usage_count / 100, 0.2)

        return min(score, 1.0)

    def suggest_skill_creation(self, user_input: str) -> bool:
        """建议创建技能"""
        # 检查是否没有匹配
        intent = self.brain._understand_intent(user_input)
        matched = self.brain._match_skill(intent, user_input)

        if matched:
            return False

        # 检查是否复杂任务
        word_count = len(user_input.split())
        if word_count > 5:
            return True

        return False


class SkillLearner:
    """
    技能学习器

    负责从工作历史中学习新技能
    """

    def __init__(self, brain: LocalBrain):
        self.brain = brain

        # 学习阈值
        self.min_work_duration = 2000  # 毫秒
        self.min_work_complexity = 2    # 动作数量

    async def learn_from_history(
        self,
        max_records: int = 100
    ):
        """从历史学习"""
        work_history = self.brain.get_work_history(max_records)

        for record in work_history:
            if not record.converted_to_skill:
                await self.brain._learn_from_work(record)

    def should_learn(self, work_record: WorkRecord) -> bool:
        """判断是否应该学习"""
        if not work_record.success:
            return False

        if work_record.converted_to_skill:
            return False

        # 检查复杂度
        if len(work_record.actions) < self.min_work_complexity:
            return False

        # 检查执行时间
        if work_record.duration_ms < self.min_work_duration:
            return False

        # 检查是否有类似技能
        existing = self.brain._match_skill(work_record.intent, work_record.input)
        if existing:
            return False

        return True

    async def create_skill_from_work(
        self,
        work_record: WorkRecord,
        name: str = None
    ) -> Skill:
        """从工作记录创建技能"""
        if not self.should_learn(work_record):
            raise ValueError("This work record should not be converted to skill")

        skill = Skill(
            id=f"learned_{work_record.id}",
            name=name or self._generate_name(work_record),
            description=f"自动学习: {work_record.input[:50]}...",
            trigger_patterns=self._extract_patterns(work_record.input),
            intent_type=work_record.intent.type,
            actions=work_record.actions,
            examples=[work_record.input],
            learned_from=work_record.id,
        )

        self.brain._skills[skill.id] = skill
        work_record.converted_to_skill = True

        logger.info(f"Created skill from work: {skill.name}")

        return skill

    def _generate_name(self, work_record: WorkRecord) -> str:
        """生成技能名称"""
        intent = work_record.intent.type.value
        return f"{intent}_{work_record.id[:8]}"

    def _extract_patterns(self, input_text: str) -> List[str]:
        """提取触发模式"""
        patterns = [input_text]

        # 关键词
        words = [w for w in input_text.split() if len(w) > 2]
        patterns.extend(words[:5])

        return patterns
