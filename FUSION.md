# ZuesHammer Fusion Modules

ZuesHammer 真正融合了三个顶级开源项目的核心代码：

## 融合来源

| 项目 | 来源 | 核心贡献 |
|------|------|----------|
| **ClaudeCode** | `/Users/imac/Desktop/src` | 工具执行引擎、并发分区、OTel遥测 |
| **Hermes** | `NousResearch/hermes-agent` | 记忆系统、工具管理、安全机制 |
| **OpenClaw** | `openclaw/openclaw` | 多渠道接入、Canvas、技能管理 |

---

## ClaudeCode 核心融合

来源：`/Users/imac/Desktop/src/`

### 1. 工具执行引擎 (ClaudeCode Tools Engine)
**融合文件**: `src/fusion/claude_code/tools_engine.py`

核心功能：
- `partitionToolCalls()` - 并发分区算法
- `isConcurrencySafe()` - 并发安全判断
- `runToolCalls()` - 工具调用执行
- `ToolResult` - 统一工具结果格式

```python
class ToolCallPartition:
    """ClaudeCode 并发分区算法"""
    def partition_by_dependency(self, tool_calls):
        # 分析工具调用依赖关系
        # 返回可并行执行的组
```

### 2. OTel 遥测日志 (OpenTelemetry Telemetry)
**融合文件**: `src/fusion/claude_code/telemetry.py`

核心功能：
- 结构化日志记录
- 工具调用追踪
- 性能指标收集

### 3. 核心模式 (Core Schemas)
**融合文件**: `src/fusion/claude_code/schemas.py`

核心功能：
- 工具调用参数验证
- 结果格式标准化
- 错误类型定义

---

## Hermes 核心融合

来源：`/Users/imac/Desktop/智能体/hermes-source/`

### 1. 记忆系统 (Memory System)
**融合文件**: `src/fusion/hermes/memory.py`

核心功能：
- `MemoryManager` - 统一记忆管理
- `SessionMemory` - 会话记忆（FTS5搜索）
- `Summarizer` - LLM摘要生成
- 跨会话记忆召回

```python
class HermesMemoryManager:
    """Hermes 记忆系统核心"""
    def __init__(self, db_path, llm_client):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(db_path)
        self.vector = VectorMemory()
```

### 2. 工具管理 (Tool Management)
**融合文件**: `src/fusion/hermes/tools.py`

核心功能：
- `ToolRegistry` - 工具注册表
- `ToolSet` - 工具集管理
- `ToolPermissions` - 工具权限控制
- MCP 工具网关

### 3. 安全机制 (Security)
**融合文件**: `src/fusion/hermes/security.py`

核心功能：
- `OSVScanner` - 恶意软件检测
- `CredentialGuard` - 凭证泄露检测
- `DangerFlagDetector` - 危险标志检测
- `CircuitBreaker` - 断路器模式

### 4. 技能系统 (Skills System)
**融合文件**: `src/fusion/hermes/skills.py`

核心功能：
- 技能自动创建和改进
- `agentskills.io` 标准兼容
- 技能版本管理
- 技能同步

### 5. MCP 协议栈 (MCP Protocol)
**融合文件**: `src/fusion/hermes/mcp.py`

核心功能：
- 完整 MCP 协议实现
- 多服务器管理
- OAuth 认证
- 结构化内容支持

---

## OpenClaw 核心融合

来源：`/Users/imac/Desktop/智能体/openclaw-source/`

### 1. 多渠道接入 (Multi-Channel Gateway)
**融合文件**: `src/fusion/openclaw/channels.py`

核心功能：
- `ChannelGateway` - 渠道网关
- `TelegramAdapter` - Telegram 适配器
- `DiscordAdapter` - Discord 适配器
- `WhatsAppAdapter` - WhatsApp 适配器
- `SlackAdapter` - Slack 适配器

```python
class ChannelGateway:
    """OpenClaw 多渠道接入"""
    async def handle_message(self, channel, message):
        # 统一处理来自不同渠道的消息
```

### 2. Canvas 系统 (Live Canvas)
**融合文件**: `src/fusion/openclaw/canvas.py`

核心功能：
- 实时 Canvas 渲染
- 用户交互处理
- Canvas 命令执行

### 3. 技能管理 (Skills Management)
**融合文件**: `src/fusion/openclaw/skills.py`

核心功能：
- `SkillHub` - 技能中心
- `SkillRegistry` - 技能注册
- `SkillExecutor` - 技能执行器
- 技能市场集成

### 4. 配置系统 (Configuration)
**融合文件**: `src/fusion/openclaw/config.py`

核心功能：
- 受保护路径配置
- `ConfigProtection` - 配置防篡改
- 多环境支持

---

## 融合架构

```
┌─────────────────────────────────────────────────────────────┐
│                     ZuesHammer                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              融合核心层 (Fusion Core)                │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ClaudeCode   │ │  Hermes     │ │ OpenClaw    │   │   │
│  │  │Tools Engine │ │  Memory     │ │  Channels   │   │   │
│  │  │             │ │  Security   │ │  Canvas     │   │   │
│  │  │ Partition   │ │  Skills     │ │  Skills     │   │   │
│  │  │ Telemetry   │ │  MCP        │ │  Config     │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              本地大脑 (Local Brain)                   │   │
│  │  意图理解 → 技能匹配 → 大模型工作 → 技能学习         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              语音系统 (Voice System)                   │   │
│  │  唤醒词检测 → STT → 语言理解 → TTS                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              三层记忆 (Three-Tier Memory)            │   │
│  │  短期(LRU) → 长期(SQLite) → 工作记忆                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 使用方式

```python
# 使用 ClaudeCode 工具执行引擎
from src.fusion.claude_code.tools_engine import ToolExecutor
executor = ToolExecutor()
results = await executor.run_tools(tool_calls)

# 使用 Hermes 记忆系统
from src.fusion.hermes.memory import HermesMemoryManager
memory = HermesMemoryManager(db_path, llm_client)
memory.remember("key", value)
memory.recall("key")

# 使用 OpenClaw 渠道
from src.fusion.openclaw.channels import ChannelGateway
gateway = ChannelGateway()
await gateway.start()
```

---

## 许可证

各融合模块遵循原始项目的许可证：
- ClaudeCode: Anthropic 许可证
- Hermes: MIT 许可证
- OpenClaw: MIT 许可证

ZuesHammer 项目整体采用 MIT 许可证。
