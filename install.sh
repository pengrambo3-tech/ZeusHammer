#!/bin/bash
# ZeusHammer One-Line Installer
# Usage: curl -sSL https://git.io/zeushammer | bash

set -e

echo "=============================================="
echo "  ZeusHammer Installer v2.0.0"
echo "=============================================="
echo ""

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python3 not found. Please install Python 3.10+ first.${NC}"
    exit 1
fi

echo -e "${CYAN}[1/4] Cloning repository...${NC}"
if [ -d "ZeusHammer" ]; then
    echo "ZeusHammer directory already exists, using existing..."
else
    git clone https://github.com/pengrambo3-tech/ZeusHammer.git
fi
cd ZeusHammer

echo -e "${CYAN}[2/4] Installing dependencies...${NC}"
pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt 2>/dev/null || {
    echo "Installing core packages..."
    pip3 install httpx pyyaml openai anthropic edge-tts pyaudio >/dev/null 2>&1
}

echo -e "${CYAN}[3/4] Creating config directory...${NC}"
mkdir -p ~/.zueshammer
cat > ~/.zueshammer/.env << 'EOF'
# ZeusHammer Configuration
# Add your API key below

# Option 1: ChinaWhapi (recommended for Chinese users)
# OPENAI_API_KEY=your_chinawhapi_key
# API_BASE=https://api.chinawhapi.com/v1
# MODEL=deepseek-chat

# Option 2: Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-xxx

# Option 3: OpenAI
# OPENAI_API_KEY=sk-xxx
# MODEL=gpt-4o
EOF

echo -e "${CYAN}[4/4] Verifying installation...${NC}"
python3 -c "import sys; sys.path.insert(0, '.'); from src.core.config import Config; print('Config OK')" 2>/dev/null || echo "Note: Some modules may require additional setup"

echo ""
echo -e "${GREEN}=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Edit ~/.zueshammer/.env and add your API key"
echo "  2. Run: cd zueshammer && python3 -m src.main --mode cli"
echo ""
echo "Quick config for ChinaWhapi:"
echo "  echo 'OPENAI_API_KEY=your_key' >> ~/.zueshammer/.env"
echo "  echo 'API_BASE=https://api.chinawhapi.com/v1' >> ~/.zueshammer/.env"
echo "  echo 'MODEL=deepseek-chat' >> ~/.zueshammer/.env"
echo ""
echo -e "For more info: ${CYAN}https://github.com/pengrambo3-tech/ZeusHammer${NC}"
echo ""