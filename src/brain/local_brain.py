"""
ZeusHammer Local Brain System

本地大脑 - 智能决策和学习的核心

工作流程:
1. 用户下达指令
2. 本地大脑接收指令
3. 进行记忆技能匹配
4. 匹配成功 → 直接执行技能
5. 匹配失败 → 调用大模型工作
6. 工作完成 → 将记忆转化为技能
7. 下次遇到相同问题 → 使用已学习的技能
"""

import asyncio
import logging
import time
import hashlib
import json
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_EDIT = "file_edit"
    FILE_DELETE = "file_delete"
    COMMAND_EXEC = "command_exec"
    WEB_SEARCH = "web_search"
    WEB_BROWSE = "web_browse"
    CODE = "code"
    QUESTION = "question"
    TASK = "task"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """用户意图"""
    type: IntentType
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_input: str = ""
    language: str = "zh"


@dataclass
class Skill:
    """技能定义"""
    id: str
    name: str
    description: str
    trigger_patterns: List[str]  # 触发模式
    intent_type: IntentType
    actions: List[Dict]  # 执行动作
    examples: List[str]  # 示例
    usage_count: int = 0
    success_count: int = 0
    last_used: float = 0
    created_at: float = field(default_factory=time.time)
    learned_from: str = ""  # 从哪个工作学习来的


@dataclass
class WorkRecord:
    """工作记录"""
    id: str
    input: str
    output: str
    intent: Intent
    actions: List[Dict]
    success: bool
    duration_ms: float
    created_at: float = field(default_factory=time.time)
    converted_to_skill: bool = False


@dataclass
class ThinkResult:
    """思考结果"""
    matched_skill: Optional[Skill] = None
    needs_llm: bool = True
    work_record: Optional[WorkRecord] = None
    response: str = ""
    actions: List[Dict] = field(default_factory=list)


class LocalBrain:
    """
    本地大脑

    核心功能:
    1. 意图理解
    2. 技能匹配
    3. 工作执行
    4. 技能学习
    """

    def __init__(self, memory_manager=None, llm_client=None):
        self.memory = memory_manager
        self.llm = llm_client

        # 技能库
        self._skills: Dict[str, Skill] = {}

        # 工作历史
        self._work_history: List[WorkRecord] = []

        # 内置技能
        self._register_builtin_skills()

        # 回调
        self._skill_executor: Optional[Callable] = None
        self._llm_executor: Optional[Callable] = None

    def set_executors(
        self,
        skill_executor: Callable,
        llm_executor: Callable = None
    ):
        """设置执行器"""
        self._skill_executor = skill_executor
        self._llm_executor = llm_executor

    def _register_builtin_skills(self):
        """注册内置技能"""

        # 文件读取技能
        self._skills["builtin_read"] = Skill(
            id="builtin_read",
            name="读取文件",
            description="读取指定路径的文件内容",
            trigger_patterns=[
                "读取文件", "打开文件", "查看文件", "cat",
                "read file", "show content", "open",
            ],
            intent_type=IntentType.FILE_READ,
            actions=[
                {"tool": "read", "params": {"path": "{path}"}}
            ],
            examples=["读取 /etc/passwd", "open file /tmp/test.txt"],
        )

        # 文件写入技能
        self._skills["builtin_write"] = Skill(
            id="builtin_write",
            name="写入文件",
            description="创建或覆盖文件内容",
            trigger_patterns=[
                "写入文件", "创建文件", "写文件",
                "write file", "create file", "save",
            ],
            intent_type=IntentType.FILE_WRITE,
            actions=[
                {"tool": "write", "params": {"path": "{path}", "content": "{content}"}}
            ],
            examples=["创建文件 /tmp/test.txt", "write hello to file"],
        )

        # 命令执行技能
        self._skills["builtin_bash"] = Skill(
            id="builtin_bash",
            name="执行命令",
            description="执行shell命令",
            trigger_patterns=[
                "执行命令", "运行命令", "终端",
                "run command", "execute", "bash", "shell",
            ],
            intent_type=IntentType.COMMAND_EXEC,
            actions=[
                {"tool": "bash", "params": {"command": "{command}"}}
            ],
            examples=["执行 ls -la", "run ls command"],
        )

        # 网页搜索技能
        self._skills["builtin_search"] = Skill(
            id="builtin_search",
            name="网页搜索",
            description="搜索互联网获取信息",
            trigger_patterns=[
                "搜索", "查找", "google",
                "search", "google", "find on web",
            ],
            intent_type=IntentType.WEB_SEARCH,
            actions=[
                {"tool": "http_request", "params": {"url": "{url}", "method": "GET"}}
            ],
            examples=["搜索 Python 教程", "search for React docs"],
        )

    def think(self, user_input: str) -> ThinkResult:
        """
        本地大脑思考

        1. 理解意图
        2. 匹配技能
        3. 返回结果
        """
        # 1. 理解意图
        intent = self._understand_intent(user_input)

        # 2. 尝试匹配技能
        matched_skill = self._match_skill(intent, user_input)

        if matched_skill:
            # 命中技能
            logger.info(f"Skill matched: {matched_skill.name}")
            return ThinkResult(
                matched_skill=matched_skill,
                needs_llm=False,
            )

        # 3. 没有匹配，需要大模型
        logger.info("No skill matched, needs LLM")
        return ThinkResult(
            matched_skill=None,
            needs_llm=True,
        )

    async def execute_work(
        self,
        user_input: str,
        intent: Intent = None
    ) -> WorkRecord:
        """
        执行工作

        1. 调用大模型获取工作方案
        2. 执行动作
        3. 记录工作
        4. 学习新技能
        """
        start_time = time.time()
        intent = intent or self._understand_intent(user_input)

        # 调用大模型
        if self._llm_executor:
            response = await self._llm_executor(user_input)
            actions = self._extract_actions(response)
        else:
            response = "No LLM configured"
            actions = []

        duration_ms = (time.time() - start_time) * 1000

        # 创建工作记录
        work_record = WorkRecord(
            id=self._generate_id(),
            input=user_input,
            output=response,
            intent=intent,
            actions=actions,
            success=len(actions) > 0,
            duration_ms=duration_ms,
        )

        # 记录工作
        self._work_history.append(work_record)

        # 尝试学习新技能
        await self._learn_from_work(work_record)

        return work_record

    async def execute_skill(
        self,
        skill: Skill,
        context: Dict[str, Any]
    ) -> str:
        """执行技能"""
        skill.usage_count += 1
        skill.last_used = time.time()

        results = []

        for action in skill.actions:
            tool = action.get("tool")
            params = action.get("params", {})

            # 替换变量
            params = self._substitute_params(params, context)

            # 执行
            if self._skill_executor:
                result = await self._skill_executor(tool, params)
                results.append(result)

        return "\n".join(str(r) for r in results)

    def _understand_intent(self, user_input: str) -> Intent:
        """理解用户意图"""
        text = user_input.lower()
        entities = {}

        # 文件路径检测
        import re
        paths = re.findall(r'/[\w/.-]+', user_input)
        if paths:
            entities["paths"] = paths

        # 代码检测
        if any(code in text for code in ["function", "def ", "class ", "import ", "const ", "let ", "var "]):
            entities["has_code"] = True

        # 确定意图类型（按优先级排序，避免误匹配）
        
        # 优先检查金融/股票查询（避免被误识别为文件读取）
        if any(p in text for p in ["股价", "股票", "价格", "行情", "市值", "涨跌", "股价查询", "股票查询"]):
            intent_type = IntentType.WEB_SEARCH
        elif any(p in text for p in ["搜索", "查找", "查询", "google", "search", "query", "问", "打听"]):
            intent_type = IntentType.WEB_SEARCH
        elif any(p in text for p in ["读", "打开", "查看", "cat", "read", "show", "open"]):
            intent_type = IntentType.FILE_READ
        elif any(p in text for p in ["写", "创建", "save", "write", "create"]):
            intent_type = IntentType.FILE_WRITE
        elif any(p in text for p in ["编辑", "修改", "edit", "change"]):
            intent_type = IntentType.FILE_EDIT
        elif any(p in text for p in ["删除", "remove", "delete", "rm"]):
            intent_type = IntentType.FILE_DELETE
        elif any(p in text for p in ["执行", "运行", "命令", "run", "bash", "shell", "exec"]):
            intent_type = IntentType.COMMAND_EXEC
        elif any(p in text for p in ["浏览", "打开网页", "browse", "navigate"]):
            intent_type = IntentType.WEB_BROWSE
        elif any(p in text for p in ["代码", "function", "def ", "class "]):
            intent_type = IntentType.CODE
        elif any(p in text for p in ["什么", "如何", "why", "how", "what", "?"]):
            intent_type = IntentType.QUESTION
        else:
            intent_type = IntentType.UNKNOWN

        # 计算置信度
        confidence = 0.5
        if entities.get("paths"):
            confidence += 0.2
        if entities.get("has_code"):
            confidence += 0.2

        # 检测语言
        language = "zh" if any('\u4e00' <= c <= '\u9fff' for c in user_input) else "en"

        return Intent(
            type=intent_type,
            confidence=min(confidence, 1.0),
            entities=entities,
            raw_input=user_input,
            language=language,
        )

    def _match_skill(
        self,
        intent: Intent,
        user_input: str
    ) -> Optional[Skill]:
        """匹配技能"""
        user_lower = user_input.lower()

        best_match = None
        best_score = 0.0

        for skill_id, skill in self._skills.items():
            score = 0.0

            # 1. 意图类型匹配
            if skill.intent_type == intent.type:
                score += 0.4

            # 2. 触发模式匹配
            for pattern in skill.trigger_patterns:
                pattern_lower = pattern.lower()
                if pattern_lower in user_lower:
                    score += 0.3
                elif pattern_lower.split()[0] if pattern_lower.split() else "" in user_lower:
                    score += 0.1

            # 3. 使用频率加成
            if skill.usage_count > 10:
                score += 0.1
            elif skill.usage_count > 0:
                score += 0.05 * min(skill.usage_count / 10, 1)

            # 4. 成功率加成
            if skill.usage_count > 0:
                success_rate = skill.success_count / skill.usage_count
                score += success_rate * 0.2

            if score > best_score and score >= 0.5:
                best_score = score
                best_match = skill

        return best_match

    async def _learn_from_work(self, work_record: WorkRecord):
        """从工作记录学习新技能"""
        if not work_record.success or work_record.converted_to_skill:
            return

        # 检查是否值得学习
        if work_record.duration_ms < 1000:  # 太简单不需要学习
            return

        # 检查是否已有类似技能
        existing = self._match_skill(work_record.intent, work_record.input)
        if existing:
            return  # 已有类似技能

        # 创建新技能
        skill = Skill(
            id=f"learned_{self._generate_id()}",
            name=self._extract_name(work_record.input),
            description=f"从工作学习: {work_record.input[:50]}...",
            trigger_patterns=self._extract_patterns(work_record.input),
            intent_type=work_record.intent.type,
            actions=work_record.actions,
            examples=[work_record.input],
            learned_from=work_record.id,
        )

        # 添加到技能库
        self._skills[skill.id] = skill
        work_record.converted_to_skill = True

        logger.info(f"Learned new skill: {skill.name}")

        # 持久化
        if self.memory:
            self.memory.remember(f"skill_{skill.id}", {
                "id": skill.id,
                "name": skill.name,
                "trigger_patterns": skill.trigger_patterns,
                "intent_type": skill.intent_type.value,
                "actions": skill.actions,
            })

    def _extract_name(self, input_text: str) -> str:
        """从输入提取技能名称"""
        # 简单实现：取前20个字符
        return input_text[:20].strip() + "..."

    def _extract_patterns(self, input_text: str) -> List[str]:
        """提取触发模式"""
        patterns = [input_text]

        # 提取关键词
        keywords = []
        for word in input_text.split():
            if len(word) > 2:
                keywords.append(word)

        patterns.extend(keywords[:3])

        return patterns

    def _extract_actions(self, response: Any) -> List[Dict]:
        """从响应提取动作"""
        # 简化实现
        if isinstance(response, dict) and "actions" in response:
            return response["actions"]
        return []

    def _substitute_params(
        self,
        params: Dict,
        context: Dict
    ) -> Dict:
        """替换参数变量"""
        result = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 替换 {variable}
                for var_name, var_value in context.items():
                    placeholder = "{" + var_name + "}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(var_value))
            result[key] = value
        return result

    def _generate_id(self) -> str:
        """生成ID"""
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]

    def get_skills(self) -> List[Skill]:
        """获取所有技能"""
        return list(self._skills.values())

    def get_work_history(self, limit: int = 50) -> List[WorkRecord]:
        """获取工作历史"""
        return self._work_history[-limit:]

    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "total_skills": len(self._skills),
            "builtin_skills": sum(1 for s in self._skills.values() if s.id.startswith("builtin")),
            "learned_skills": sum(1 for s in self._skills.values() if s.id.startswith("learned")),
            "total_work_records": len(self._work_history),
            "converted_to_skills": sum(1 for w in self._work_history if w.converted_to_skill),
        }
