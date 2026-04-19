#!/bin/bash
# ZeusHammer Quick Installer v2.1.0
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh -o /tmp/install.sh && bash /tmp/install.sh

set -e

echo "=============================================="
echo "  ZeusHammer Installer v2.1.0"
echo "=============================================="
echo ""

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Recommended Python version
RECOMMENDED_PYTHON="3.12"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10

# =====================
# Python Version Check & Fix
# =====================
check_python_version() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python3 not found.${NC}"
        echo "Please install Python $RECOMMENDED_PYTHON from: https://www.python.org/downloads/"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

    echo -e "${CYAN}Detected Python: $(python3 --version)${NC}"

    # Check if version is too new (3.14+)
    if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 14 ]; then
        echo -e "${YELLOW}Warning: Python $PYTHON_VERSION detected.${NC}"
        echo "Some packages may not be compatible with Python $PYTHON_VERSION yet."
        echo ""
        echo "Attempting to install Python $RECOMMENDED_PYTHON..."

        if command -v brew &> /dev/null; then
            brew install python@${RECOMMENDED_PYTHON} 2>/dev/null
            if command -v python3.${RECOMMENDED_PYTHON} &> /dev/null; then
                echo -e "${GREEN}Python $RECOMMENDED_PYTHON installed successfully!${NC}"
                echo "Setting up virtual environment with Python $RECOMMENDED_PYTHON..."
                python3.${RECOMMENDED_PYTHON} -m venv "$HOME/.zeushammer-venv"
                echo -e "${GREEN}Virtual environment created at: $HOME/.zeushammer-venv${NC}"
                USE_VENV=1
            fi
        else
            echo -e "${RED}Homebrew not found. Please install Python $RECOMMENDED_PYTHON manually:${NC}"
            echo "  1. Download from https://www.python.org/downloads/"
            echo "  2. Or install Homebrew first: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
    fi

    # Check if version is too old
    if [ "$PYTHON_MAJOR" -lt "$MIN_PYTHON_MAJOR" ] || \
       ([ "$PYTHON_MAJOR" -eq "$MIN_PYTHON_MAJOR" ] && [ "$PYTHON_MINOR" -lt "$MIN_PYTHON_MINOR" ]); then
        echo -e "${RED}Error: Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ required, but found $PYTHON_VERSION${NC}"
        exit 1
    fi
}

# =====================
# Smart Package Installer
# =====================
smart_install() {
    local package="$1"
    local fallback_pkg="$2"  # Optional fallback package

    echo -n "  Installing $package... "

    # Try main package first
    if pip3 install --quiet "$package" 2>/tmp/pip-error-${package}.log; then
        echo -e "${GREEN}OK${NC}"
        return 0
    fi

    # Analyze error
    ERROR_LOG=$(cat /tmp/pip-error-${package}.log 2>/dev/null)

    # Check for compilation errors (C/Cython)
    if echo "$ERROR_LOG" | grep -qi "cython\|compil\|error:"; then
        echo -e "${YELLOW}COMPILATION ERROR${NC}"

        # Try with specific versions known to work
        echo "  Trying with compatible version..."

        # Try wheel-only install (no compilation)
        if pip3 install --only-binary=:all: --quiet "$package" 2>/dev/null; then
            echo -e "  ${GREEN}Installed pre-built binary!${NC}"
            return 0
        fi

        # Try older compatible version
        case "$package" in
            "pydub")
                # Try older pydub without PyAV dependency
                echo "  Trying pydub with alternative audio backend..."
                pip3 install --quiet "pydub<0.25.0" 2>/dev/null && return 0
                ;;
            "faster-whisper")
                # Try standard openai-whisper as fallback
                if [ -n "$fallback_pkg" ]; then
                    echo "  Installing fallback: $fallback_pkg"
                    pip3 install --quiet "$fallback_pkg" 2>/dev/null && return 0
                fi
                ;;
            "pyaudio")
                # Try pyaudio with pre-built
                pip3 install --quiet --only-binary=pyaudio "pyaudio" 2>/dev/null && return 0
                ;;
        esac
    fi

    # Check for system dependency issues (portaudio, ffmpeg, etc.)
    if echo "$ERROR_LOG" | grep -qi "portaudio\|ffmpeg\| portaudio\|libasound"; then
        echo -e "${YELLOW}MISSING SYSTEM DEPENDENCY${NC}"

        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                echo "  Installing portaudio via Homebrew..."
                brew install portaudio 2>/dev/null && pip3 install --quiet "$package" 2>/dev/null && return 0
            fi
        elif command -v apt-get &> /dev/null; then
            echo "  Installing portaudio via apt..."
            sudo apt-get install -y portaudio19-dev 2>/dev/null && pip3 install --quiet "$package" 2>/dev/null && return 0
        fi
    fi

    # Check for externally-managed-environment error
    if echo "$ERROR_LOG" | grep -qi "externally-managed"; then
        echo -e "${YELLOW}FIXING externally-managed-environment...${NC}"

        # Try with --break-system-packages
        if pip3 install --break-system-packages --quiet "$package" 2>/dev/null; then
            echo -e "  ${GREEN}Fixed with --break-system-packages${NC}"
            return 0
        fi

        # Try user install
        if pip3 install --user --quiet "$package" 2>/dev/null; then
            echo -e "  ${GREEN}Fixed with --user install${NC}"
            return 0
        fi
    fi

    # If we have a fallback and main package failed completely
    if [ -n "$fallback_pkg" ]; then
        echo -e "${YELLOW}FAILED - Trying fallback: $fallback_pkg${NC}"
        if pip3 install --quiet "$fallback_pkg" 2>/dev/null; then
            echo -e "  ${GREEN}Fallback installed successfully!${NC}"
            return 0
        fi
    fi

    echo -e "${RED}FAILED${NC}"
    echo "  Error details:"
    head -5 /tmp/pip-error-${package}.log 2>/dev/null | sed 's/^/    /'
    return 1
}

# =====================
# Main Installation Flow
# =====================
main() {
    check_python_version

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
    echo ""

    # Core packages (must succeed)
    CORE_PACKAGES=(
        "httpx"
        "pyyaml"
        "aiofiles"
        "python-dotenv"
        "openai"
        "anthropic"
        "edge-tts"
        "fastapi"
        "uvicorn[standard]"
        "starlette"
        "websockets"
        "jinja2"
        "qrcode"
        "pillow"
    )

    FAILED_CORE=0
    for pkg in "${CORE_PACKAGES[@]}"; do
        if ! smart_install "$pkg"; then
            FAILED_CORE=1
        fi
    done

    echo ""
    echo -e "${CYAN}[3/5] Installing optional packages with fallbacks...${NC}"
    echo ""

    # Optional packages (with fallbacks)
    OPTIONAL_PACKAGES=(
        "pyaudio::"
        "faster-whisper::openai-whisper"
        "silero-vad::"
        "cryptography::"
        "playwright::"
    )

    for entry in "${OPTIONAL_PACKAGES[@]}"; do
        IFS='::' read -r pkg fallback <<< "$entry"
        smart_install "$pkg" "$fallback" || true
    done

    # Platform-specific
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo ""
        echo -e "${CYAN}[4/5] macOS audio setup...${NC}"
        if ! python3 -c "import pyaudio" 2>/dev/null; then
            echo "  Installing portaudio..."
            brew install portaudio 2>/dev/null || true
            pip3 install --quiet pyaudio 2>/dev/null || echo "  Note: pyaudio may need manual installation"
        fi
    fi

    echo ""
    echo -e "${CYAN}[5/5] Creating config directory...${NC}"
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

    # Verification
    echo ""
    echo -e "${CYAN}Verifying installation...${NC}"

    VERIFY_FAILED=""
    for pkg in httpx yaml openai anthropic fastapi; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            VERIFY_FAILED="$VERIFY_FAILED $pkg"
        fi
    done

    if [ -z "$VERIFY_FAILED" ]; then
        echo -e "${GREEN}All core dependencies installed successfully!${NC}"
    else
        echo -e "${YELLOW}Warning: Some dependencies failed verification:$VERIFY_FAILED${NC}"
        echo "Please review the error logs above."
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

    # Exit with error if core packages failed
    if [ $FAILED_CORE -eq 1 ]; then
        echo -e "${RED}Warning: Some core packages failed to install.${NC}"
        echo "The program may not work correctly."
        exit 1
    fi
}

main "$@"
