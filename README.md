# ZuesHammer - Zeus Hammer

<div align="center">

![Version](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Super AI Agent - Claude + Hermes + OpenClaw**

Fusion of ClaudeCode tool orchestration, Hermes MCP protocol stack, OpenClaw security control

</div>

---

## Features

### Core Capabilities
- **Smart Conversation**: Support for Claude, OpenAI, and local models
- **Tool Execution**: Secure file operations, terminal commands, code execution
- **Memory System**: Three-tier architecture (short-term, long-term, working memory)
- **Skills System**: Extensible skill workflow engine

### Security Architecture
- **Permission Levels**: safe / semi_open / full_open
- **Danger Detection**: Real-time credential leakage, malware detection
- **Config Protection**: Tamper-proof sensitive configurations
- **Circuit Breaker**: Prevent abnormal operations

### Integration Capabilities
- **MCP Protocol**: Model Context Protocol server support
- **Browser Automation**: Playwright-driven web operations
- **Voice Interaction**: Wake word detection, voice synthesis
- **Multi-Platform**: Telegram, WeChat Work, and more

---

## Quick Start

### One-Click Installation

```bash
# Clone repository
git clone https://github.com/pengrambo3-tech/zueshammer.git
cd zueshammer

# One-click install
python3 install.py

# Or use pip
pip install -r requirements.txt
```

### Configuration

Edit `~/.zueshammer/.env`:

```bash
# API Key (required)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Permission Level
PERMISSION_LEVEL=semi_open
```

### Run

```bash
# CLI mode
python3 -m src.main --mode cli

# Web interface
python3 -m src.main --mode web

# Voice mode
python3 -m src.main --mode voice
```

---

## Installation Options

| Command | Description |
|---------|-------------|
| `python3 install.py` | Interactive installation |
| `python3 install.py --auto` | Auto install (default) |
| `python3 install.py --minimal` | Minimal install (core only) |
| `python3 install.py --update` | Update dependencies |

---

## Project Structure

```
ZuesHammer/
├── src/                    # Source code
│   ├── main.py             # Main entry
│   ├── zueshammer.py      # Core class
│   ├── brain/              # Local brain
│   ├── tools/              # Tool system
│   ├── memory/             # Memory system
│   ├── mcp/                # MCP protocol
│   ├── voice/              # Voice system
│   ├── browser/            # Browser automation
│   ├── security/           # Security module
│   ├── llm/                # LLM client
│   ├── core/               # Core system
│   ├── chat/               # Chat ports
│   ├── tui/                # Terminal UI
│   ├── skills/             # Skills system
│   ├── gateway/            # WebSocket gateway
│   ├── config/             # Config protection
│   └── utils/              # Utilities
│
├── tests/                  # Tests
├── docs/                   # Documentation
├── scripts/                # Scripts
├── config/                 # Default config
│
├── install.py              # Installation script
├── setup.py                # Package config
├── main.py                 # CLI shortcut
├── requirements.txt        # Dependencies
├── README.md               # English docs
├── README_zh.md            # Chinese docs
├── LICENSE                 # MIT License
└── CONTRIBUTING.md         # Contributing guide
```

---

## API Configuration

### Anthropic (Recommended)

```bash
ANTHROPIC_API_KEY=sk-ant-your-key
API_PROVIDER=anthropic
MODEL=claude-3-5-sonnet-20241022
```

### OpenAI

```bash
OPENAI_API_KEY=sk-your-key
API_PROVIDER=openai
MODEL=gpt-4o
```

### Local Models

```bash
API_PROVIDER=local
API_BASE=http://localhost:11434
MODEL=llama3
```

---

## Permission Levels

| Level | Description |
|-------|-------------|
| `safe` | All operations require confirmation |
| `semi_open` | Safe operations auto-execute, dangerous operations warn |
| `full_open` | Unrestricted (beast mode) |

---

## Development

### Run Tests

```bash
pytest
pytest tests/test_core.py
pytest --cov=src tests/
```

### Code Formatting

```bash
black src/
ruff check src/
```

---

## FAQ

### Q: "Module not found" error

```bash
pip install -r requirements.txt
```

### Q: Voice not working

```bash
# macOS
brew install portaudio

# Ubuntu/Debian
sudo apt install portaudio19-dev
```

### Q: Playwright error

```bash
python -m playwright install --with-deps
```

---

## Contributing

Issues and Pull Requests are welcome!

## License

MIT License - See [LICENSE](./LICENSE)

---

<div align="center">

**Made with ❤️ for the AI Community**

</div>
