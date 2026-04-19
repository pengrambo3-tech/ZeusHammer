# ZeusHammer - The Ultimate AI Agent

<div align="center">

![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**The Super AI Agent Built from Three Open Source Giants**

*Think Locally. Speak Freely. Remember Everything.*

[![Star](https://img.shields.io/github/stars/pengrambo3-tech/zueshammer?style=social)](https://github.com/pengrambo3-tech/ZeusHammer)
[![Fork](https://img.shields.io/github/forks/pengrambo3-tech/zueshammer?style=social)](https://github.com/pengrambo3-tech/ZeusHammer)

</div>

---

## Fusion of Three Open Source Projects

ZeusHammer is a **true fusion** of three top-tier open source AI agent projects, combining their best features into one unified super agent:

| Project | Core Contribution | License |
|---------|------------------|---------|
| **[ClaudeCode](https://github.com/anthropics/claude-code)** | Tool execution engine, concurrent partitioning, OTel telemetry | Anthropic |
| **[Hermes](https://github.com/NousResearch/hermes-agent)** | Memory system, security, tools, MCP protocol | MIT |
| **[OpenClaw](https://github.com/openclaw/openclaw)** | Multi-channel gateway, Canvas, skills management | MIT |

### What Each Project Brings

#### ClaudeCode Core
- `partitionToolCalls()` - Concurrent partitioning algorithm
- `isConcurrencySafe()` - Concurrency safety checks
- `ToolResult` - Unified tool result format
- OTel structured logging and tracing

#### Hermes Core
- **Memory System**: Short-term + Long-term + Vector memory with FTS5 search
- **Security**: OSV malware scanner, credential guard, circuit breaker
- **Tools**: Tool registry, MCP protocol stack, skill auto-improvement
- **Skills**: Agent-curated skill creation and management

#### OpenClaw Core
- **Multi-Channel**: Telegram, Discord, Slack, WhatsApp gateway
- **Canvas**: Live Canvas rendering system
- **Skills**: SkillHub with marketplace integration
- **Config**: Protected paths and tamper-proof configuration

---

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/zueshammer/master/install.sh | bash
```

Or manual install:

```bash
git clone https://github.com/pengrambo3-tech/ZeusHammer.git
cd zueshammer
pip install -r requirements.txt
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ZeusHammer                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    Fusion Core                              │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │ │
│  │  │ClaudeCode  │ │  Hermes     │ │     OpenClaw        │  │ │
│  │  │────────────│ │────────────│ │────────────────────│  │ │
│  │  │Tool Engine │ │  Memory    │ │  Channel Gateway   │  │ │
│  │  │Partition   │ │  Security  │ │  Canvas System     │  │ │
│  │  │Telemetry   │ │  MCP       │ │  Skills Hub        │  │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    Local Brain                             │ │
│  │  Intent Recognition → Skill Match → LLM Work → Learn     │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    Voice System                            │ │
│  │  Wake Word "Zues/宙斯" → STT → Language → TTS          │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                Three-Tier Memory                           │ │
│  │  Short-term (LRU) → Long-term (SQLite) → Working        │ │
│  └───────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  LLM Providers: ChinaWhapi • Anthropic • OpenAI • Local      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Fusion Engine - Best of Three Worlds

The fusion brings together the most powerful features from each project:

| Feature | From | Description |
|---------|------|-------------|
| **Tool Partition** | ClaudeCode | Concurrent tool execution with dependency analysis |
| **Circuit Breaker** | Hermes | Fail-fast pattern for stable operation |
| **Multi-Channel** | OpenClaw | Connect via Telegram, Discord, Slack, etc. |
| **OSV Scanner** | Hermes | Detect malware patterns in code |
| **Credential Guard** | Hermes | Prevent credential leakage |
| **Memory System** | Hermes | Persistent cross-session memory |
| **Skill Learning** | Hermes | Auto-create skills from experience |
| **Canvas** | OpenClaw | Live interactive canvas |
| **OTel Telemetry** | ClaudeCode | Structured logging and tracing |

### Local Brain - Think Before Asking LLM

```python
# ZeusHammer's Local Brain workflow:
1. User gives instruction
2. Local Brain receives instruction
3. Pattern matching against skill library
4. Match found → Execute skill directly (NO LLM needed!)
5. No match → Call LLM for solution
6. Work complete → Learn new skill
7. Next time → Use learned skill (instant, no LLM)
```

### Voice Interaction - True Hands-Free

| Component | Technology | Benefit |
|-----------|-----------|---------|
| Speech-to-Text | **Whisper** (local) | Offline capable, no data sent |
| Text-to-Speech | **Edge TTS** | Natural, free voices |
| Wake Word | Custom detector | "Zues" or "宙斯" activation |
| Language Detection | Auto-detection | Auto-switch Chinese/English |
| Smart Responses | Context-aware | Reply based on model/memory status |

---

## Supported Models

### China LLM via [chinawhapi.com](https://chinawhapi.com)

| Provider | Models | Features |
|----------|--------|----------|
| **DeepSeek** | V3, Coder | Best value, coding focused |
| **Qwen** (Alibaba) | Turbo, Plus, Max | Long context support |
| **GLM** (Zhipu) | GLM-4, GLM-4V | Vision support |
| **Moonshot** | 8K, 32K, 128K | Ultra long context |
| **ERNIE** (Baidu) | Bot 4.0, Bot Long | Enterprise grade |
| **Doubao** (ByteDance) | Pro, Lite | Fast, cost effective |
| **MiniMax** | ABAB6 Chat/GSPT | Conversational AI |

### International Models

| Provider | Models |
|----------|--------|
| **Anthropic** | Claude 3.5 Sonnet, Opus, Haiku |
| **OpenAI** | GPT-4o, GPT-4 Turbo, GPT-3.5 |
| **Local** | Ollama, LM Studio, vLLM |

---

## Quick Start

### Configure API

```bash
# Option 1: ChinaWhapi (recommended for Chinese users)
echo "OPENAI_API_KEY=your_key" >> ~/.zueshammer/.env
echo "API_BASE=https://api.chinawhapi.com/v1" >> ~/.zueshammer/.env
echo "MODEL=deepseek-chat" >> ~/.zueshammer/.env

# Option 2: Anthropic Claude
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> ~/.zueshammer/.env
echo "MODEL=claude-3-5-sonnet-20241022" >> ~/.zueshammer/.env

# Option 3: OpenAI
echo "OPENAI_API_KEY=sk-xxx" >> ~/.zueshammer/.env
echo "MODEL=gpt-4o" >> ~/.zueshammer/.env
```

### Run

```bash
python3 -m src.main --mode cli   # CLI mode
python3 -m src.main --mode web   # Web UI
python3 -m src.main --mode voice # Voice (recommended!)
```

---

## Security

| Level | Description |
|-------|-------------|
| `safe` | All operations require confirmation |
| `semi_open` | Safe operations auto-execute, dangerous operations warn |
| `full_open` | Unrestricted (beast mode) |

Built-in protections (from Hermes):
- OSV malware pattern scanning
- Credential leakage detection
- Circuit breaker for abnormal operations
- Protected paths from OpenClaw
- Config tamper protection

---

## Development

```bash
# Run tests
pytest tests/

# Code format
black src/
ruff check src/
```

---

## Project Structure

```
ZeusHammer/
├── src/
│   ├── fusion/              # Three project fusion
│   │   ├── claude_code/     # ClaudeCode core
│   │   │   └── tools_engine.py
│   │   ├── hermes/          # Hermes core
│   │   │   └── security.py
│   │   └── openclaw/        # OpenClaw core
│   │       └── channels.py
│   ├── brain/               # Local brain
│   ├── voice/               # Voice system
│   ├── memory/              # Memory system
│   └── tools/               # Tools
├── FUSION.md                # Fusion documentation
├── README.md
└── README_zh.md
```

---

## Contributing

Issues and Pull Requests welcome!

## License

MIT License

---

<div align="center">

**Built with ❤️ by fusing ClaudeCode + Hermes + OpenClaw**

*[Think Locally. Speak Freely. Remember Everything.]*

</div>
