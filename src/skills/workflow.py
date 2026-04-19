"""
ZeusHammer Workflow Skills System

Fuses Hermes' workflow skills + OpenClaw's skill invocation.

Features:
1. YAML-based skill definitions with frontmatter
2. Multi-step workflow execution
3. Conditional branching
4. Error handling and retry
5. Skill parameters and validation
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class SkillStatus(Enum):
    """Skill execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SkillParameter:
    """Skill parameter definition"""
    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = False
    default: Any = None
    enum: List[Any] = None
    pattern: str = None


@dataclass
class SkillStep:
    """A single step in a skill workflow"""
    id: str
    action: str  # tool, condition, loop, function
    params: Dict[str, Any] = field(default_factory=dict)
    next_on_success: str = "next"  # next, end, or step_id
    next_on_failure: str = "fail"  # fail, retry, or step_id
    retry_count: int = 0
    retry_delay: float = 1.0


@dataclass
class Skill:
    """Skill definition"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)

    # Execution parameters
    parameters: List[SkillParameter] = field(default_factory=list)
    steps: List[SkillStep] = field(default_factory=list)

    # Metadata
    platforms: List[str] = field(default_factory=lambda: ["all"])
    requirements: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    # Progressive disclosure
    short_description: str = ""
    steps_preview: List[str] = field(default_factory=list)


@dataclass
class SkillExecution:
    """Skill execution context"""
    skill: Skill
    params: Dict[str, Any]
    status: SkillStatus = SkillStatus.PENDING
    current_step: int = 0
    results: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


class SkillEngine:
    """
    Skill execution engine.

    Features:
    1. Load skills from YAML/SKILL.md files
    2. Validate parameters
    3. Execute multi-step workflows
    4. Handle branching and loops
    5. Error recovery and retry
    """

    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir or "~/.zueshammer/skills").expanduser()
        self._skills: Dict[str, Skill] = {}
        self._executors: Dict[str, Callable] = {}  # action -> function
        self._running: List[SkillExecution] = []

        # Register built-in actions
        self._register_builtin_actions()

    def _register_builtin_actions(self):
        """Register built-in action executors"""
        self._executors["tool"] = self._execute_tool
        self._executors["condition"] = self._execute_condition
        self._executors["loop"] = self._execute_loop
        self._executors["assign"] = self._execute_assign
        self._executors["log"] = self._execute_log
        self._executors["wait"] = self._execute_wait
        self._executors["function"] = self._execute_custom_function

    async def load_skills(self, paths: List[str] = None) -> int:
        """
        Load skills from files or directories.

        Returns number of skills loaded.
        """
        if paths is None:
            paths = [str(self.skills_dir)]

        loaded = 0

        for path_str in paths:
            path = Path(path_str)

            if path.is_file():
                if skill := self._load_skill_file(path):
                    self._skills[skill.name] = skill
                    loaded += 1

            elif path.is_dir():
                # Find all SKILL.md files
                for skill_file in path.rglob("SKILL.md"):
                    if skill := self._load_skill_file(skill_file):
                        self._skills[skill.name] = skill
                        loaded += 1

                # Also check YAML files
                for yaml_file in path.rglob("*.yaml"):
                    if skill := self._load_skill_yaml(yaml_file):
                        self._skills[skill.name] = skill
                        loaded += 1

        logger.info(f"Loaded {loaded} skills")
        return loaded

    def _load_skill_file(self, path: Path) -> Optional[Skill]:
        """Load skill from SKILL.md file with YAML frontmatter"""
        try:
            content = path.read_text(encoding="utf-8")

            # Parse YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1])

                    return Skill(
                        name=frontmatter.get("name", path.stem),
                        description=frontmatter.get("description", ""),
                        version=frontmatter.get("version", "1.0.0"),
                        author=frontmatter.get("author", ""),
                        tags=frontmatter.get("tags", []),
                        parameters=[SkillParameter(**p) for p in frontmatter.get("parameters", [])],
                        steps=[SkillStep(**s) for s in frontmatter.get("steps", [])],
                        platforms=frontmatter.get("platforms", ["all"]),
                        requirements=frontmatter.get("requirements", []),
                        examples=frontmatter.get("examples", []),
                        short_description=frontmatter.get("short_description", ""),
                        steps_preview=frontmatter.get("steps_preview", []),
                    )

            # No frontmatter, use filename as name
            return Skill(
                name=path.stem,
                description=content[:200],
            )

        except Exception as e:
            logger.error(f"Failed to load skill {path}: {e}")
            return None

    def _load_skill_yaml(self, path: Path) -> Optional[Skill]:
        """Load skill from YAML file"""
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)

            return Skill(
                name=data.get("name", path.stem),
                description=data.get("description", ""),
                version=data.get("version", "1.0.0"),
                parameters=[SkillParameter(**p) for p in data.get("parameters", [])],
                steps=[SkillStep(**s) for s in data.get("steps", [])],
            )

        except Exception as e:
            logger.error(f"Failed to load skill {path}: {e}")
            return None

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get skill by name"""
        return self._skills.get(name)

    def list_skills(self, tag: str = None) -> List[Skill]:
        """List all skills, optionally filtered by tag"""
        skills = list(self._skills.values())

        if tag:
            skills = [s for s in skills if tag in s.tags]

        return skills

    def search_skills(self, query: str) -> List[Skill]:
        """Search skills by name or description"""
        query = query.lower()
        results = []

        for skill in self._skills.values():
            if (query in skill.name.lower() or
                query in skill.description.lower() or
                any(query in tag.lower() for tag in skill.tags)):
                results.append(skill)

        return results

    def validate_params(self, skill: Skill, params: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate skill parameters.

        Returns: (is_valid, error_messages)
        """
        errors = []

        for param in skill.parameters:
            value = params.get(param.name)

            # Check required
            if param.required and value is None:
                errors.append(f"Missing required parameter: {param.name}")
                continue

            if value is None:
                continue

            # Type check
            expected_type = param.type
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"{param.name} must be string")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"{param.name} must be number")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"{param.name} must be boolean")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"{param.name} must be array")

            # Pattern check
            if param.pattern and isinstance(value, str):
                if not re.match(param.pattern, value):
                    errors.append(f"{param.name} doesn't match pattern: {param.pattern}")

            # Enum check
            if param.enum and value not in param.enum:
                errors.append(f"{param.name} must be one of: {param.enum}")

        return len(errors) == 0, errors

    async def execute(self, skill_name: str, params: Dict[str, Any] = None) -> SkillExecution:
        """
        Execute a skill.

        Args:
            skill_name: Name of skill to execute
            params: Parameters for skill execution

        Returns:
            SkillExecution with results
        """
        skill = self.get_skill(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")

        params = params or {}

        # Validate parameters
        valid, errors = self.validate_params(skill, params)
        if not valid:
            execution = SkillExecution(skill=skill, params=params, status=SkillStatus.FAILED)
            execution.errors = errors
            return execution

        # Create execution context
        execution = SkillExecution(skill=skill, params=params)
        self._running.append(execution)

        try:
            execution.status = SkillStatus.RUNNING
            await self._execute_steps(execution)

            if not execution.errors:
                execution.status = SkillStatus.COMPLETED
            else:
                execution.status = SkillStatus.FAILED

        except Exception as e:
            execution.status = SkillStatus.FAILED
            execution.errors.append(str(e))

        finally:
            if execution in self._running:
                self._running.remove(execution)

        return execution

    async def _execute_steps(self, execution: SkillExecution):
        """Execute all steps in skill workflow"""
        skill = execution.skill

        while execution.current_step < len(skill.steps):
            step = skill.steps[execution.current_step]

            try:
                # Execute step
                result = await self._execute_step(step, execution)

                # Store result
                execution.results.append(result)
                execution.context[f"step_{step.id}"] = result

                # Determine next step
                if result.get("success", True):
                    next_step = step.next_on_success
                else:
                    next_step = step.next_on_failure

                if next_step == "next":
                    execution.current_step += 1
                elif next_step == "end":
                    break
                elif next_step == "fail":
                    execution.errors.append(f"Step {step.id} failed")
                    break
                else:
                    # Jump to specific step
                    step_index = next((i for i, s in enumerate(skill.steps) if s.id == next_step), -1)
                    if step_index >= 0:
                        execution.current_step = step_index
                    else:
                        execution.current_step += 1

            except Exception as e:
                execution.errors.append(f"Step {step.id} error: {e}")
                break

    async def _execute_step(self, step: SkillStep, execution: SkillExecution) -> Dict:
        """Execute a single step"""
        action = step.action
        params = self._substitute_params(step.params, execution)

        # Get action executor
        executor = self._executors.get(action)
        if not executor:
            return {"success": False, "error": f"Unknown action: {action}"}

        # Retry logic
        last_error = None
        for attempt in range(step.retry_count + 1):
            try:
                result = await executor(params, execution)
                if result.get("success", True):
                    return result

                last_error = result.get("error")

                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay * (attempt + 1))

            except Exception as e:
                last_error = str(e)
                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay * (attempt + 1))

        return {"success": False, "error": last_error or "Step failed"}

    def _substitute_params(self, params: Dict, execution: SkillExecution) -> Dict:
        """Substitute {{variable}} in params with context values"""
        result = {}

        for key, value in params.items():
            if isinstance(value, str):
                # Substitute variables
                for var_name, var_value in execution.context.items():
                    placeholder = f"{{{{{var_name}}}}}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(var_value))

                # Substitute params
                for param_name, param_value in execution.params.items():
                    placeholder = f"{{{{params.{param_name}}}}}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(param_value))

            elif isinstance(value, dict):
                result[key] = self._substitute_params(value, execution)
            elif isinstance(value, list):
                result[key] = [
                    self._substitute_params({k: v}, execution)[k]
                    if isinstance(v, (dict, str)) else v
                    for v in value
                ]
            else:
                result[key] = value

        return result

    # Built-in action executors

    async def _execute_tool(self, params: Dict, execution: SkillExecution) -> Dict:
        """Execute a tool"""
        from src.tools.advanced_executor import get_executor, ToolCall, ToolType

        tool_name = params.get("name")
        tool_params = params.get("params", {})

        executor = get_executor()
        tool = executor.get_tool(tool_name)

        if not tool:
            return {"success": False, "error": f"Tool not found: {tool_name}"}

        # Determine tool type
        tool_type_map = {
            "read": ToolType.READ,
            "write": ToolType.WRITE,
            "execute": ToolType.EXECUTE,
        }

        tool_call = ToolCall(
            id=f"skill_{execution.skill.name}_{tool_name}",
            name=tool_name,
            params=tool_params,
            tool_type=tool_type_map.get(tool_name, ToolType.READ),
        )

        result = await executor.execute(tool_call)

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }

    async def _execute_condition(self, params: Dict, execution: SkillExecution) -> Dict:
        """Evaluate a condition"""
        condition = params.get("if")
        then_value = params.get("then")
        else_value = params.get("else")

        # Simple condition evaluation
        # Supports: ==, !=, >, <, >=, <=, in, not in
        result = self._evaluate_condition(condition, execution)

        return {
            "success": True,
            "output": then_value if result else else_value,
            "condition_result": result,
        }

    def _evaluate_condition(self, condition: str, execution: SkillExecution) -> bool:
        """Evaluate a simple condition string"""
        # Very simplified - real implementation would need proper expression parser
        # Supports: variable comparisons

        for key, value in execution.context.items():
            if key in condition:
                condition = condition.replace(key, repr(value))

        try:
            # Security: only allow safe comparisons
            if re.match(r'^[\s\w\d.<>=!+\-"\'and or]+$', condition):
                return eval(condition)
        except Exception:
            pass

        return False

    async def _execute_loop(self, params: Dict, execution: SkillExecution) -> Dict:
        """Execute a loop"""
        items = params.get("items", [])
        max_iterations = params.get("max", 100)
        action = params.get("do")

        results = []
        for i, item in enumerate(items[:max_iterations]):
            execution.context["loop_item"] = item
            execution.context["loop_index"] = i

            if action:
                result = await self._execute_step(
                    SkillStep(id="loop", action="function", params=action),
                    execution
                )
                results.append(result)

        return {"success": True, "output": results, "iterations": len(results)}

    async def _execute_assign(self, params: Dict, execution: SkillExecution) -> Dict:
        """Assign value to variable"""
        var_name = params.get("var")
        value = params.get("value")

        execution.context[var_name] = value

        return {"success": True, "output": value}

    async def _execute_log(self, params: Dict, execution: SkillExecution) -> Dict:
        """Log message"""
        message = params.get("message", "")
        level = params.get("level", "info")

        log_func = getattr(logger, level, logger.info)
        log_func(f"[Skill: {execution.skill.name}] {message}")

        return {"success": True, "output": message}

    async def _execute_wait(self, params: Dict, execution: SkillExecution) -> Dict:
        """Wait for specified time"""
        seconds = params.get("seconds", 1)
        await asyncio.sleep(seconds)
        return {"success": True, "output": f"Waited {seconds}s"}

    async def _execute_custom_function(self, params: Dict, execution: SkillExecution) -> Dict:
        """Execute custom function"""
        func_name = params.get("name")
        func_args = params.get("args", [])

        # Get function from registry
        func = self._executors.get(f"func_{func_name}")
        if not func:
            return {"success": False, "error": f"Function not found: {func_name}"}

        result = await func(func_args, execution)
        return {"success": True, "output": result}

    def register_function(self, name: str, func: Callable):
        """Register custom function"""
        self._executors[f"func_{name}"] = func


# Global skill engine
_skill_engine: Optional[SkillEngine] = None


def get_skill_engine() -> SkillEngine:
    """Get global skill engine"""
    global _skill_engine
    if _skill_engine is None:
        _skill_engine = SkillEngine()
    return _skill_engine


# 别名 - 提供统一的导入接口
WorkflowEngine = SkillEngine
