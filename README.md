# ZuesHammer - The Ultimate AI Agent

<div align="center">

![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**The AI Agent with Local Brain, Voice Interaction & Three-Tier Memory**

*Think Locally. Speak Freely. Remember Everything.*

[![Star](https://img.shields.io/github/stars/pengrambo3-tech/zueshammer?style=social)](https://github.com/pengrambo3-tech/zueshammer)
[![Fork](https://img.shields.io/github/forks/pengrambo3-tech/zueshammer?style=social)](https://github.com/pengrambo3-tech/zueshammer)

</div>

---

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/zueshammer/master/install.sh | bash
```

Or manual install:

```bash
git clone https://github.com/pengrambo3-tech/zueshammer.git
cd zueshammer
pip install -r requirements.txt
```

---

## What Makes ZuesHammer Different?

Unlike typical AI agents, ZuesHammer combines **three breakthrough technologies**:

| Feature | What It Does |
|---------|-------------|
| 🧠 **Local Brain** | Intent recognition & pattern matching that learns new skills automatically |
| 🎙️ **Voice-First** | Local Whisper STT + Edge TTS for true hands-free operation |
| 🧬 **Three-Tier Memory** | Short-term (LRU cache) → Long-term (SQLite) → Working memory |

---

## Supported Models

### China LLM via [chinawhapi.com](https://chinawhapi.com)

Unified API access to all major Chinese LLMs with **single key**:

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

## Key Features

### Local Brain - Think Before Asking LLM

The core innovation that sets ZuesHammer apart:

```
# ZuesHammer's Local Brain workflow:
1. User gives instruction
2. Local Brain receives instruction
3. Pattern matching against skill library
4. Match found → Execute skill directly (NO LLM needed!)
5. No match → Call LLM for solution
6. Work complete → Learn new skill
7. Next time → Use learned skill (instant, no LLM)
```

**Benefits:**
- **80% faster** for common tasks (pattern-matched skills run instantly)
- **Cost efficient** - Only calls expensive LLM when needed
- **Self-improving** - Learns from every task, gets smarter over time
- **Privacy-first** - Simple patterns never leave your machine

### Voice Interaction - Real Hands-Free

Complete voice pipeline running locally:

| Component | Technology | Benefit |
|-----------|-----------|---------|
| Speech-to-Text | **Whisper** (local) | Offline capable, no data sent |
| Text-to-Speech | **Edge TTS** | Natural, free voices |
| Wake Word | Custom detector | "Hey Agent" activation |
| Language Detection | Multi-language | Auto-detect Chinese/English |

```bash
# Voice mode examples
python3 -m src.main --mode voice
# Say: "帮我读取 /tmp/test.txt"
# Or: "search for Python tutorials"
```

### Three-Tier Memory System

Inspired by ClaudeCode, Hermes, and OpenClaw best practices:

| Layer | Storage | Purpose | Duration |
|-------|---------|---------|----------|
| **Short-term** | LRU Cache (RAM) | Hot data, instant access | ~1 hour |
| **Long-term** | SQLite | Persistent knowledge | Forever |
| **Working** | Active context | Current task state | Session |

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
echo "API_PROVIDER=anthropic" >> ~/.zueshammer/.env
echo "MODEL=claude-3-5-sonnet-20241022" >> ~/.zueshammer/.env

# Option 3: OpenAI
echo "OPENAI_API_KEY=sk-xxx" >> ~/.zueshammer/.env
echo "API_PROVIDER=openai" >> ~/.zueshammer/.env
echo "MODEL=gpt-4o" >> ~/.zueshammer/.env
```

### Run

```bash
python3 -m src.main --mode cli   # CLI mode
python3 -m src.main --mode web   # Web UI
python3 -m src.main --mode voice # Voice (recommended!)
```

---

## Advanced: OpenClaw-Style Multi-Model Configuration

For power users, ZuesHammer supports OpenClaw-style multi-model routing with automatic failover.

### Multi-Provider Configuration

Copy `config/example_config.yaml` to `~/.zueshammer/config.yaml`:

```yaml
models:
  default_provider: claude

  providers:
    claude:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-3-5-sonnet-20241022
      priority: 1

    china:
      api_base: https://api.chinawhapi.com/v1
      api_key: ${CHINAWHAPI_KEY}
      model: deepseek-chat
      priority: 3

  # Auto-routing by keywords
  routing_rules:
    - keywords: [code, debug, 编程]
      provider: claude
      model: claude-opus-4-5

    - keywords: [search, 搜索]
      provider: china
      model: deepseek-chat

  # Failover chain
  fallback:
    - provider: claude
      model: claude-3-5-haiku-20241022
```

### Routing Features

| Feature | Description |
|---------|-------------|
| **Keyword Routing** | Auto-select model based on query keywords |
| **Task Type Routing** | Code → Claude, Search → DeepSeek |
| **Failover** | Auto-switch when rate limited |
| **Multi-Provider** | Use multiple APIs simultaneously |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ZuesHammer                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Local Brain │  │Voice System│  │Memory System│   │
│  │             │  │             │  │             │   │
│  │ Intent Recog│  │Whisper STT  │  │ Short-term  │   │
│  │ Skill Match │  │ Edge TTS    │  │ Long-term   │   │
│  │ Auto Learn  │  │ Wake Word   │  │ Working     │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │             │
│  ┌──────┴────────────────┴────────────────┴──────┐   │
│  │              Core Engine                       │   │
│  │  Permission • Event Bus • Pipeline            │   │
│  └───────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  LLM Providers: ChinaWhapi • Anthropic • OpenAI • Local │
└─────────────────────────────────────────────────────────┘
```

---

## Security

| Level | Description |
|-------|-------------|
| `safe` | All operations require confirmation |
| `semi_open` | Safe operations auto-execute, dangerous operations warn |
| `full_open` | Unrestricted (beast mode) |

Built-in protections:
- Credential leakage detection
- Malware pattern scanning
- Circuit breaker for abnormal operations
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

## Contributing

Issues and Pull Requests welcome!

## License

MIT License

---

<div align="center">

**Built with ❤️ for the AI Community**

*[Think Locally. Speak Freely. Remember Everything.]*

</div>