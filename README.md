# ZuesHammer - Zeus Hammer

<div align="center">

![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**🤖 The Intelligent AI Agent with Local Brain & Voice**

*Think Locally. Speak Freely. Remember Everything.*

</div>

---

## What Makes ZuesHammer Different?

Unlike typical AI agents, ZuesHammer combines **three breakthrough technologies**:

| Feature | What It Does |
|---------|-------------|
| 🧠 **Local Brain** | Intent recognition & pattern matching that learns new skills automatically |
| 🎙️ **Voice-First** | Local Whisper STT + Edge TTS for true hands-free operation |
| 🧬 **Three-Tier Memory** | Short-term (LRU cache) → Long-term (SQLite) → Working memory |

---

## Key Features

### 🧠 Local Brain - Think Before Asking LLM

The core innovation that sets ZuesHammer apart:

```python
# ZuesHammer's Local Brain workflow:
# 1. User gives instruction
# 2. Local Brain receives instruction  
# 3. Pattern matching against skill library
# 4. Match found → Execute skill directly (NO LLM needed!)
# 5. No match → Call LLM for solution
# 6. Work complete → Learn new skill
# 7. Next time → Use learned skill (instant, no LLM)
```

**Benefits:**
- **80% faster** for common tasks (pattern-matched skills run instantly)
- **Cost efficient** - Only calls expensive LLM when needed
- **Self-improving** - Learns from every task, gets smarter over time
- **Privacy-first** - Simple patterns never leave your machine

### 🎙️ Voice Interaction - Real Hands-Free

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

### 🧬 Three-Tier Memory System

Inspired by ClaudeCode, Hermes, and OpenClaw best practices:

| Layer | Storage | Purpose | Duration |
|-------|---------|---------|----------|
| **Short-term** | LRU Cache (RAM) | Hot data, instant access | ~1 hour |
| **Long-term** | SQLite | Persistent knowledge | Forever |
| **Working** | Active context | Current task state | Session |

Features:
- LRU eviction with importance weighting
- Vector similarity search (simplified)
- Automatic importance scoring
- Event-driven updates

---

## Quick Start

```bash
# Clone
git clone https://github.com/pengrambo3-tech/zueshammer.git
cd zueshammer

# Install
python3 install.py

# Configure
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> ~/.zueshammer/.env
echo "PERMISSION_LEVEL=semi_open" >> ~/.zueshammer/.env

# Run
python3 -m src.main --mode cli   # CLI
python3 -m src.main --mode web   # Web UI
python3 -m src.main --mode voice # Voice (recommended!)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ZuesHammer                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ Local Brain │  │Voice System│  │Memory System│     │
│  │             │  │             │  │             │     │
│  │ Intent Recog│  │Whisper STT  │  │ Short-term  │     │
│  │ Skill Match │  │ Edge TTS    │  │ Long-term   │     │
│  │ Auto Learn  │  │ Wake Word   │  │ Working     │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│  ┌──────┴────────────────┴────────────────┴──────┐     │
│  │              Core Engine                       │     │
│  │  Permission • Event Bus • Pipeline            │     │
│  └───────────────────────────────────────────────┘     │
├─────────────────────────────────────────────────────────┤
│  Tools: Claude Core • MCP Protocol • Browser • Skills    │
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
