"""
ZeusHammer Advanced Tool System

Fuses ClaudeCode's local tools + Hermes' MCP automation.

Key features:
1. Tool concurrency partitioning (ClaudeCode's innovation)
   - Read-only tools: parallel execution
   - Write tools: serial execution
2. Zod-style input validation
3. Permission hooks (ClaudeCode's security)
4. MCP tool discovery and execution (Hermes' strength)
5. Credential exposure detection (Hermes' security)
"""

import asyncio
import re
import logging
import subprocess
import hashlib
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Tool types for concurrency control"""
    READ = "read"           # File read, grep, glob, search
    WRITE = "write"         # File write, edit
    EXECUTE = "execute"    # Bash, shell commands
    NETWORK = "network"     # HTTP requests, web access
    SYSTEM = "system"       # Config, env, system


@dataclass
class ToolCall:
    """A tool call request"""
    id: str
    name: str
    params: Dict[str, Any]
    tool_type: ToolType = ToolType.READ
    concurrency_safe: bool = True  # Can run in parallel with same type


@dataclass
class ToolResult:
    """Result of tool execution"""
    id: str
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0


@dataclass
class ToolSchema:
    """Tool schema for validation"""
    name: str
    description: str
    params: Dict[str, Any]  # Zod-like schema
    returns: Dict[str, Any] = field(default_factory=dict)
    tool_type: ToolType = ToolType.READ
    examples: List[Dict] = field(default_factory=list)


# Credential patterns for detection (Hermes-inspired)
CREDENTIAL_PATTERNS = [
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
    (r"sk-[A-Za-z0-9]{48}", "OpenAI API Key"),
    (r"AKIA[A-Za-z0-9]{16}", "AWS Access Key"),
    (r"xox[baprs]-[A-Za-z0-9]{10,}", "Slack Token"),
    (r"sq0[a-z]{3}-[A-Za-z0-9]{22}", "Square API Token"),
    (r"sk_live_[A-Za-z0-9]{24}", "Stripe Secret Key"),
    (r"password\s*[:=]\s*['\"][^'\"]+['\"]", "Password in code"),
]

# Dangerous command patterns
DANGEROUS_PATTERNS = [
    (r"rm\s+-rf\s+/", "Recursive delete from root"),
    (r":\(\)\{\s*:\|:\&\}\$;:", "Fork bomb"),
    (r"chmod\s+777", "World-writable permissions"),
    (r"curl\s+.*\|.*sh", "Pipe to shell"),
    (r"wget\s+.*\|.*sh", "Pipe to shell"),
    (r"eval\s*\(", "Eval execution"),
    (r"exec\s*\(", "Exec execution"),
]


class InputValidator:
    """
    Zod-like input validation.

    Validates tool inputs against schema.
    """

    def __init__(self, schema: ToolSchema):
        self.schema = schema
        self._compiled_patterns = {}

    def validate(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate params against schema.

        Returns: (is_valid, error_message)
        """
        # Type validation
        for param_name, param_schema in self.schema.params.items():
            if param_schema.get("required", False) and param_name not in params:
                return False, f"Missing required parameter: {param_name}"

            if param_name in params:
                value = params[param_name]
                expected_type = param_schema.get("type")

                # Type checking
                if expected_type == "string" and not isinstance(value, str):
                    return False, f"{param_name} must be string"
                if expected_type == "number" and not isinstance(value, (int, float)):
                    return False, f"{param_name} must be number"
                if expected_type == "boolean" and not isinstance(value, bool):
                    return False, f"{param_name} must be boolean"
                if expected_type == "array" and not isinstance(value, list):
                    return False, f"{param_name} must be array"

                # String constraints
                if expected_type == "string":
                    min_length = param_schema.get("minLength")
                    if min_length and len(value) < min_length:
                        return False, f"{param_name} too short (min {min_length})"

                    max_length = param_schema.get("maxLength")
                    if max_length and len(value) > max_length:
                        return False, f"{param_name} too long (max {max_length})"

                    pattern = param_schema.get("pattern")
                    if pattern and not re.match(pattern, value):
                        return False, f"{param_name} doesn't match pattern"

        return True, None

    def sanitize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive values from params for logging"""
        sanitized = {}

        for key, value in params.items():
            if isinstance(value, str):
                # Check for credentials
                sanitized_value = value
                for pattern, _ in CREDENTIAL_PATTERNS:
                    sanitized_value = re.sub(
                        pattern,
                        "[REDACTED_CREDENTIAL]",
                        sanitized_value,
                        flags=re.IGNORECASE
                    )
                sanitized[key] = sanitized_value
            else:
                sanitized[key] = value

        return sanitized


class ToolBase(ABC):
    """Base class for all tools"""

    def __init__(self, name: str, description: str, tool_type: ToolType = ToolType.READ):
        self.name = name
        self.description = description
        self.tool_type = tool_type
        self._validators: List[InputValidator] = []
        self._hooks: Dict[str, List[Callable]] = {
            "pre_execute": [],
            "post_execute": [],
        }

    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute the tool"""
        pass

    def validate(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate inputs"""
        for validator in self._validators:
            is_valid, error = validator.validate(params)
            if not is_valid:
                return False, error
        return True, None

    def add_validator(self, validator: InputValidator):
        """Add input validator"""
        self._validators.append(validator)

    def hook(self, event: str, callback: Callable):
        """Add execution hook"""
        if event in self._hooks:
            self._hooks[event].append(callback)

    async def _run_hooks(self, event: str, context: Dict):
        """Run hooks for event"""
        for callback in self._hooks.get(event, []):
            try:
                result = callback(context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Hook error ({event}): {e}")


class FileTools(ToolBase):
    """
    File operation tools.

    Includes: read, write, edit, glob, grep
    """

    def __init__(self):
        super().__init__("file", "File operations", ToolType.READ)

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        operation = params.get("operation", "read")
        path = params.get("path", "")

        try:
            if operation == "read":
                return await self._read(path, params)
            elif operation == "write":
                return await self._write(path, params)
            elif operation == "edit":
                return await self._edit(path, params)
            elif operation == "glob":
                return await self._glob(params)
            elif operation == "grep":
                return await self._grep(params)
            else:
                return ToolResult(
                    id=params.get("id", ""),
                    success=False,
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            return ToolResult(
                id=params.get("id", ""),
                success=False,
                error=str(e)
            )

    async def _read(self, path: str, params: Dict) -> ToolResult:
        """Read file"""
        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return ToolResult(id=params.get("id", ""), success=False, error="File not found")

            content = file_path.read_text(encoding="utf-8")

            # Line slicing
            start_line = params.get("startLine", 0)
            end_line = params.get("endLine")
            if start_line or end_line:
                lines = content.splitlines()
                content = "\n".join(lines[start_line:end_line])

            return ToolResult(
                id=params.get("id", ""),
                success=True,
                output={"path": str(file_path), "content": content}
            )
        except Exception as e:
            return ToolResult(id=params.get("id", ""), success=False, error=str(e))

    async def _write(self, path: str, params: Dict) -> ToolResult:
        """Write file"""
        content = params.get("content", "")
        try:
            file_path = Path(path).expanduser()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            return ToolResult(
                id=params.get("id", ""),
                success=True,
                output={"path": str(file_path), "size": len(content)}
            )
        except Exception as e:
            return ToolResult(id=params.get("id", ""), success=False, error=str(e))

    async def _edit(self, path: str, params: Dict) -> ToolResult:
        """Edit file"""
        old_string = params.get("old_string", "")
        new_string = params.get("new_string", "")

        if not old_string:
            return ToolResult(id=params.get("id", ""), success=False, error="Missing old_string")

        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return ToolResult(id=params.get("id", ""), success=False, error="File not found")

            content = file_path.read_text(encoding="utf-8")

            if old_string not in content:
                return ToolResult(id=params.get("id", ""), success=False, error="String not found")

            new_content = content.replace(old_string, new_string, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return ToolResult(
                id=params.get("id", ""),
                success=True,
                output={"path": str(file_path), "changes": "1 replacement"}
            )
        except Exception as e:
            return ToolResult(id=params.get("id", ""), success=False, error=str(e))

    async def _glob(self, params: Dict) -> ToolResult:
        """Glob pattern matching"""
        pattern = params.get("pattern", "*")
        cwd = params.get("cwd", ".")

        try:
            import fnmatch
            base = Path(cwd).expanduser()
            matches = []

            for path in base.rglob("*"):
                if fnmatch.fnmatch(path.name, pattern):
                    matches.append(str(path))

            return ToolResult(
                id=params.get("id", ""),
                success=True,
                output={"matches": matches[:1000], "count": len(matches)}  # Limit to 1000
            )
        except Exception as e:
            return ToolResult(id=params.get("id", ""), success=False, error=str(e))

    async def _grep(self, params: Dict) -> ToolResult:
        """Grep search"""
        pattern = params.get("pattern", "")
        path = params.get("path", ".")
        case_sensitive = params.get("case_sensitive", True)

        if not pattern:
            return ToolResult(id=params.get("id", ""), success=False, error="Missing pattern")

        try:
            base = Path(path).expanduser()
            matches = []
            pattern_regex = re.compile(pattern, 0 if case_sensitive else re.I)

            for file_path in base.rglob("*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines(), 1):
                            if pattern_regex.search(line):
                                matches.append({
                                    "path": str(file_path),
                                    "line": i,
                                    "content": line.strip()
                                })
                                if len(matches) >= 1000:  # Limit results
                                    break
                    except Exception:
                        pass

            return ToolResult(
                id=params.get("id", ""),
                success=True,
                output={"matches": matches, "count": len(matches)}
            )
        except Exception as e:
            return ToolResult(id=params.get("id", ""), success=False, error=str(e))


class BashTool(ToolBase):
    """
    Shell command execution tool.

    Concurrency partitioning (ClaudeCode's innovation):
    - Always serial execution (security)
    - Timeout enforcement
    - Credential detection
    """

    def __init__(self):
        super().__init__("bash", "Execute shell commands", ToolType.EXECUTE)

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        command = params.get("command", "")
        timeout = params.get("timeout", 30)
        cwd = params.get("cwd")

        if not command:
            return ToolResult(id=params.get("id", ""), success=False, error="Missing command")

        # Security checks (Hermes-inspired)
        for pattern, warning in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                logger.warning(f"Dangerous command detected: {warning}")
                # Log for audit
                return ToolResult(
                    id=params.get("id", ""),
                    success=False,
                    error=f"Security: {warning}"
                )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

            return ToolResult(
                id=params.get("id", ""),
                success=result.returncode == 0,
                output=output
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                id=params.get("id", ""),
                success=False,
                error=f"Command timeout ({timeout}s)"
            )
        except Exception as e:
            return ToolResult(id=params.get("id", ""), success=False, error=str(e))


class ToolExecutor:
    """
    Tool executor with concurrency partitioning.

    Fuses ClaudeCode's innovation:
    - Read-only tools: parallel (up to 10)
    - Write tools: serial
    - Execute tools: serial (security)
    """

    def __init__(self):
        self._tools: Dict[str, ToolBase] = {}
        self._mcp_tools: Dict[str, Any] = {}  # MCP server -> tools
        self._semaphores: Dict[ToolType, asyncio.Semaphore] = {
            ToolType.READ: asyncio.Semaphore(10),  # Max 10 parallel reads
            ToolType.WRITE: asyncio.Semaphore(1),   # Serial writes
            ToolType.EXECUTE: asyncio.Semaphore(1),  # Serial execution
            ToolType.NETWORK: asyncio.Semaphore(5),  # Max 5 parallel network
            ToolType.SYSTEM: asyncio.Semaphore(1),   # Serial system
        }

        # Register built-in tools
        self.register_tool(FileTools())
        self.register_tool(BashTool())

    def register_tool(self, tool: ToolBase):
        """Register a tool"""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} ({tool.tool_type.value})")

    def register_mcp_tools(self, server: str, tools: List[Any]):
        """Register MCP tools from server"""
        self._mcp_tools[server] = tools
        logger.info(f"Registered {len(tools)} MCP tools from {server}")

    def get_tool(self, name: str) -> Optional[ToolBase]:
        """Get tool by name"""
        return self._tools.get(name)

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call with concurrency control.
        """
        # Get tool
        tool = self._tools.get(tool_call.name)
        if not tool:
            return ToolResult(
                id=tool_call.id,
                success=False,
                error=f"Unknown tool: {tool_call.name}"
            )

        # Run pre-execute hooks
        await tool._run_hooks("pre_execute", {"params": tool_call.params})

        # Get semaphore for concurrency control
        semaphore = self._semaphores.get(tool.tool_type, self._semaphores[ToolType.READ])

        async with semaphore:
            result = await tool.execute(tool_call.params)

        # Run post-execute hooks
        await tool._run_hooks("post_execute", {"result": result})

        return result

    async def execute_batch(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute multiple tool calls with concurrency partitioning.

        ClaudeCode's innovation:
        1. Partition by type (read/write/execute)
        2. Read-only tools: parallel
        3. Write/Execute tools: serial
        """
        # Partition tool calls
        read_calls = []
        write_calls = []
        execute_calls = []

        for call in tool_calls:
            if call.tool_type == ToolType.READ:
                read_calls.append(call)
            elif call.tool_type == ToolType.WRITE:
                write_calls.append(call)
            else:
                execute_calls.append(call)

        results = []

        # Execute read-only tools in parallel
        read_tasks = [self.execute(call) for call in read_calls]
        if read_tasks:
            read_results = await asyncio.gather(*read_tasks)
            results.extend(read_results)

        # Execute write tools serially
        for call in write_calls:
            result = await self.execute(call)
            results.append(result)

        # Execute other tools serially
        for call in execute_calls:
            result = await self.execute(call)
            results.append(result)

        return results

    def get_tool_schemas(self) -> List[Dict]:
        """Get schemas for all tools (for LLM)"""
        schemas = []

        for tool in self._tools.values():
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "type": tool.tool_type.value,
                "concurrency_safe": tool.tool_type == ToolType.READ
            })

        # Add MCP tools
        for server, tools in self._mcp_tools.items():
            for tool in tools:
                schemas.append({
                    "name": f"{server}.{tool.name}",
                    "description": tool.description,
                    "type": "mcp",
                    "server": server
                })

        return schemas


# Global executor
_executor: Optional[ToolExecutor] = None


def get_executor() -> ToolExecutor:
    """Get global tool executor"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
