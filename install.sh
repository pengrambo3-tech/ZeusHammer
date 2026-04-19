#!/bin/bash
# ZeusHammer Quick Installer
# Usage: curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh | bash

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
if [ -d "ZeusHammer" ]; then
    echo "ZeusHammer directory exists, updating..."
    cd ZeusHammer && git pull origin master
else
    git clone https://github.com/pengrambo3-tech/ZeusHammer.git
    cd ZeusHammer
fi

echo -e "${CYAN}[2/5] Installing dependencies...${NC}"
pip3 install -q -r requirements.txt 2>/dev/null || {
    echo "Installing dependencies manually..."
    pip3 install httpx pyyaml aiofiles python-dotenv openai anthropic edge-tts pyaudio faster-whisper silero-vad fastapi uvicorn starlette websockets jinja2 playwright qrcode pillow cryptography pydub
}

# macOS specific
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v portaudio &> /dev/null; then
        echo -e "${YELLOW}[3/5] Installing portaudio (macOS)...${NC}"
        brew install portaudio 2>/dev/null || true
    else
        echo -e "${CYAN}[3/5] portaudio already installed${NC}"
    fi
fi

echo -e "${CYAN}[4/5] Creating config directory...${NC}"
mkdir -p ~/.zeushammer
cat > ~/.zeushammer/.env << 'EOF'
# ZeusHammer Configuration
# Get your API key from https://chinawhapi.com

# Option 1: ChinaWhapi (recommended for Chinese users)
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
python3 -c "import sys; sys.path.insert(0, 'src'); from main import main; print('Installation OK')" 2>/dev/null || echo "Note: Run manually to configure API key"

echo ""
echo -e "${GREEN}=============================================="
echo "  Installation Complete!"
echo "==============================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.zeushammer/.env and add your API key"
echo "  2. Run: cd ZeusHammer && python3 -m src.main --mode cli"
echo ""
echo "Quick config (ChinaWhapi):"
echo "  echo 'OPENAI_API_KEY=your_key' >> ~/.zeushammer/.env"
echo "  echo 'API_BASE=https://api.chinawhapi.com/v1' >> ~/.zeushammer/.env"
echo "  echo 'MODEL=deepseek-chat' >> ~/.zeushammer/.env"
echo ""
echo -e "For more info: ${CYAN}https://github.com/pengrambo3-tech/ZeusHammer${NC}"
echo ""
