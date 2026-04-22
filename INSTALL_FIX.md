# ZeusHammer 安装问题修复清单

## 🐛 发现的问题

### 1. Homebrew 安装命令不存在 ❌

**问题:**
- README 中写了 `brew install zeushammer`
- 但实际上没有创建 Homebrew formula
- 用户执行会报错

**解决方案:**

**方案 A: 创建 Homebrew Tap（推荐）**
```bash
# 创建 homebrew-zeushammer 仓库
# https://github.com/pengrambo3-tech/homebrew-zeushammer

# 创建 Formula/zeushammer.rb
class Zeushammer < Formula
  include Language::Python::Virtualenv

  desc "ZeusHammer - AI Super Agent with Local Brain"
  homepage "https://github.com/pengrambo3-tech/ZeusHammer"
  url "https://github.com/pengrambo3-tech/ZeusHammer/archive/v2.1.0.tar.gz"
  sha256 "xxx"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/zeushammer", "--version"
  end
end
```

**方案 B: 修改 README（临时方案）**
```markdown
# 修改前
brew install zeushammer

# 修改后
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh | bash
```

### 2. WebUI 控制面板入口不明显 ⚠️

**问题:**
- WebUI 代码已存在 (`src/ui/server.py`)
- 但没有在 README 中说明
- 用户不知道如何启动 Web 界面

**解决方案:**
```markdown
## Web UI

启动 Web 界面:

```bash
zeushammer --mode web
# 或
python3 -m src.ui.server
```

访问：http://localhost:8765

功能:
- 💬 文字对话
- 🎤 实时语音交互
- 📊 状态监控
- ⚙️ 配置管理
```

### 3. 缺少快速启动指南 ⚠️

**问题:**
- 安装后不知道第一步做什么
- 没有配置示例

**解决方案:**
```markdown
## 快速开始

### 1. 安装
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh | bash

### 2. 配置
# 编辑配置文件
nano ~/.zeushammer/.env

# 添加你的 API Key
OPENAI_API_KEY=sk-xxx
API_BASE=https://api.chinawhapi.com/v1
MODEL=deepseek-chat

### 3. 运行
# 命令行模式
zeushammer --mode cli

# Web 界面（推荐）
zeushammer --mode web

# 语音模式
zeushammer --mode voice
```

---

## 🎯 立即执行

### 高优先级（今天完成）

1. **修改 README 安装说明**
   - 删除 `brew install zeushammer`
   - 改为 curl 脚本安装

2. **添加 WebUI 使用说明**
   - 在 README 中添加 WebUI 章节
   - 说明如何启动和访问

3. **创建快速开始指南**
   - 添加配置示例
   - 添加运行示例

### 中优先级（明天完成）

4. **创建 Homebrew Tap**
   - 创建 homebrew-zeushammer 仓库
   - 创建 formula 文件
   - 测试安装

5. **完善 WebUI**
   - 检查功能是否完整
   - 添加截图
   - 添加文档

---

## 📝 执行计划

**今天（4/23）:**
- [ ] 修改 README.md
- [ ] 修改 README_zh.md
- [ ] 添加 WebUI 说明
- [ ] 添加快速开始指南

**明天（4/24）:**
- [ ] 创建 Homebrew Tap
- [ ] 测试 WebUI
- [ ] 添加截图
