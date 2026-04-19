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

# Check if pipx is available, if not suggest installing it
if command -v pipx &> /dev/null; then
    echo "Using pipx for installation..."
    pipx install -e .
    echo -e "${GREEN}pipx installation successful!${NC}"
else
    echo "pipx not found. Installing with pip..."
    if pip3 install --help 2>/dev/null | grep -q "break-system-packages"; then
        # macOS Sonoma or newer with protected Python
        echo "Using --break-system-packages flag for macOS protection..."
        pip3 install --break-system-packages -q -r requirements.txt
    else
        pip3 install -q -r requirements.txt
    fi
fi

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
python3 -c "import sys; sys.path.insert(0, 'src'); from main import main; print('ZeusHammer ready!')" 2>/dev/null || echo "Note: Configure API key to complete setup"

echo ""
echo -e "${GREEN}=============================================="
echo "  Installation Complete!"
echo "==============================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit ~/.zeushammer/.env and add your API key"
echo "  2. Run: cd ZeusHammer && python3 -m src.main --mode cli"
echo ""
echo "Example config (ChinaWhapi):"
echo '  echo "OPENAI_API_KEY=your_key" >> ~/.zeushammer/.env'
echo '  echo "API_BASE=https://api.chinawhapi.com/v1" >> ~/.zeushammer/.env'
echo '  echo "MODEL=deepseek-chat" >> ~/.zeushammer/.env'
echo ""
echo -e "For more info: ${CYAN}https://github.com/pengrambo3-tech/ZeusHammer${NC}"
echo ""
