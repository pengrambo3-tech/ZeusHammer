#!/bin/bash
# ZeusHammer Quick Installer
# Usage: 
#   curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh -o /tmp/install.sh && bash /tmp/install.sh

set -e

echo "=============================================="
echo "  ZeusHammer Installer v2.0.0"
echo "=============================================="
echo ""

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python3 not found. Please install Python 3.10+ first.${NC}"
    echo "Download: https://www.python.org/downloads/"
    exit 1
fi

echo -e "${CYAN}[1/5] Cloning repository...${NC}"

cd "$HOME" || exit 1

if [ -d "$HOME/ZeusHammer" ]; then
    echo "ZeusHammer directory exists, updating..."
    cd "$HOME/ZeusHammer"
    git pull origin master
else
    git clone https://github.com/pengrambo3-tech/ZeusHammer.git
    cd "$HOME/ZeusHammer"
fi

ZEUSHAMMER_DIR="$PWD"
echo "Working in: $ZEUSHAMMER_DIR"

echo -e "${CYAN}[2/5] Installing dependencies...${NC}"

# Core dependencies
DEPS="httpx pyyaml aiofiles python-dotenv openai anthropic edge-tts pyaudio faster-whisper silero-vad fastapi uvicorn starlette websockets jinja2 playwright qrcode pillow cryptography pydub"

if pip3 install --help 2>/dev/null | grep -q "break-system-packages"; then
    echo "Using --break-system-packages flag for macOS..."
    pip3 install --break-system-packages -q $DEPS
else
    pip3 install -q $DEPS
fi

echo -e "${GREEN}Dependencies installed!${NC}"

# macOS specific: install portaudio
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${CYAN}[3/5] Installing portaudio (macOS audio)...${NC}"
    brew install portaudio 2>/dev/null || true
else
    echo -e "${CYAN}[3/5] Skipping platform-specific step${NC}"
fi

echo -e "${CYAN}[4/5] Creating config directory...${NC}"
mkdir -p ~/.zeushammer
cat > ~/.zeushammer/.env << 'EOF'
# ZeusHammer Configuration
# Get your API key from https://chinawhapi.com

# Option 1: ChinaWhapi (recommended)
# OPENAI_API_KEY=your_chinawhapi_key
# API_BASE=https://api.chinawhapi.com/v1
# MODEL=deepseek-chat

# Option 2: Direct OpenAI
# OPENAI_API_KEY=sk-xxx
# MODEL=gpt-4o

# Option 3: Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-xxx
# MODEL=claude-3-5-sonnet-20241022
EOF

echo -e "${CYAN}[5/5] Verifying installation...${NC}"
if python3 -c "import httpx, yaml, openai, anthropic, fastapi" 2>/dev/null; then
    echo -e "${GREEN}Dependencies OK!${NC}"
else
    echo "Warning: Some dependencies may not be installed correctly"
fi

echo ""
echo -e "${GREEN}=============================================="
echo "  Installation Complete!"
echo "==============================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.zeushammer/.env and add your API key"
echo "  2. Run: cd $ZEUSHAMMER_DIR && python3 -m src.main --mode cli"
echo ""
echo -e "For more info: ${CYAN}https://github.com/pengrambo3-tech/ZeusHammer${NC}"
echo ""
