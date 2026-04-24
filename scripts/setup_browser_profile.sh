#!/bin/bash
# ZeusHammer 浏览器配置文件初始化脚本
# 用途：创建浏览器配置目录，并启动 Chrome 进行首次登录

set -e

PROFILE_DIR="/Users/imac/.zeushammer/browser-profile"
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

echo "======================================"
echo "ZeusHammer 浏览器配置初始化"
echo "======================================"

# 检查 Chrome 是否存在
if [ ! -f "$CHROME_PATH" ]; then
    echo "❌ 错误：未找到 Google Chrome"
    echo "请安装 Chrome: https://www.google.com/chrome/"
    exit 1
fi

# 创建配置目录
echo "📁 创建配置目录：$PROFILE_DIR"
mkdir -p "$PROFILE_DIR"

# 检查是否已有配置
if [ -d "$PROFILE_DIR/Default" ]; then
    echo "⚠️  检测到已存在的配置文件"
    echo ""
    read -p "是否删除并重新配置？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  删除旧配置..."
        rm -rf "$PROFILE_DIR"
        mkdir -p "$PROFILE_DIR"
    else
        echo "✅ 保留现有配置，直接启动浏览器"
    fi
fi

# 关闭所有 Chrome 进程
echo "🔒 关闭所有 Chrome 进程..."
pkill -f "Google Chrome" 2>/dev/null || true
sleep 2

# 启动 Chrome（使用专用配置目录）
echo ""
echo "======================================"
echo "🚀 启动 Chrome 配置浏览器"
echo "======================================"
echo ""
echo "📋 请在打开的 Chrome 中登录以下网站："
echo "   1. GitHub: https://github.com"
echo "   2. 小红书：https://creator.xiaohongshu.com"
echo "   3. 微信公众号：https://mp.weixin.qq.com"
echo "   4. 其他需要的网站"
echo ""
echo "✅ 登录完成后，关闭 Chrome 窗口即可"
echo ""

# 启动 Chrome
"$CHROME_PATH" --user-data-dir="$PROFILE_DIR"

echo ""
echo "======================================"
echo "✅ 浏览器配置完成！"
echo "======================================"
echo ""
echo "下一步："
echo "1. 修改 config/browser_config.yaml"
echo "   设置：persistent_context: true"
echo "   设置：user_data_dir: $PROFILE_DIR"
echo ""
echo "2. 运行 ZeusHammer 测试："
echo "   python3 -m src.main --mode cli"
echo "   >>> 打开小红书创作平台"
echo ""
echo "现在应该可以直接访问已登录的网站，无需重新授权！"
echo ""
