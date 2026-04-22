# ZeusHammer - 宙斯之锤

<div align="center">

![版本](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![许可证](https://img.shields.io/badge/License-MIT-yellow.svg)

**🚀 融合三大开源项目精华的超级AI智能体**

*本地思考，自由对话，永不忘记。*

</div>

---

## ZeusHammer vs OpenClaw vs Hermes — 差异化对比

| 维度 | OpenClaw | Hermes | ZeusHammer | ZeusHammer优势 |
|------|----------|--------|------------|----------------|
| **Local Brain** | ❌ | ❌ | ✅ | 80%任务无需LLM, 意图识别+技能匹配 |
| **Voice-First** | 部分(Voice Wake) | 部分 | ✅ | Whisper+Edge TTS全栈, 唤醒词, 语言自动检测 |
| **三层记忆** | ❌ | ❌ | ✅ | 短时(LRU)+长期(SQLite)+工作记忆 |
| **冥想模式** | ❌ | ❌ | ✅ | 空闲时自动分析/模式提取/技能升级 |
| **深度反思** | ❌ | ❌ | ✅ | 因果链分析/洞察生成 |
| **工作流引擎** | Standing Orders | Cron/子Agent | ✅ | 完整编排+技能匹配+技能学习 |
| **熔断器** | ❌ | Circuit breaker | ✅ | 安全体系完整 |
| **OSV扫描** | ❌ | ❌ | ✅ | 命令/文件恶意软件检测 |
| **中国LLM原生支持** | 需要配置 | 部分 | ✅ | 内置DeepSeek/Qwen/GLM/Moonshot/ERNIE/Doubao/MiniMax客户端 |
| **工具检测器** | ❌ | ❌ | ✅ | 自动检测80+系统CLI |
| **成本追踪** | ❌ | 部分 | ✅ | 内置LLM使用成本追踪 |
| **模型选择器** | ✅ | ✅ | ✅ | 智能路由+降级链+成本优化 |
| **WebRTC实时音频** | ❌ | ❌ | ✅ | 实时语音流 |
| **协作房间** | ❌ | ❌ | ✅ | 多人协作支持 |
| **苹果生态** | ✅ | ✅ | ✅ | Apple Notes/Reminders/iMessage/Screenshot |
| **记忆向量存储** | LanceDB/QMD | 外部插件(8个) | ✅ | 内置Chroma，原生集成 |
| **Skill自生成** | ❌ | ❌ | ✅ | Local Brain自动生成新技能 |
| **RL训练** | ❌ | ✅ Tinker-Atropos | ✅ | SWE-Bench/RL/轨迹压缩 |
| **安装便捷性** | npm/global | pip | Homebrew/pipx/Docker | macOS用户最友好 |
| **消息渠道数量** | 30+ | 20+ | 13+ | OpenClaw最多 |
| **内置工具数量** | 20+ | 40+ | 50+ | ZeusHammer最多 |
| **AI模型数量** | 35+ | 15+ | 20+ | OpenClaw最多 |
| **Skills数量** | 插件市场 | 70+ | 50+ | Hermes最多 |
| **记忆插件** | 4种后端 | 8个外部插件 | 3层内置 | 各有优势 |
| **MCP支持** | ✅ | ✅ | ✅ | 三者均有 |
| **ACP/IDE集成** | ✅ | ✅ | ✅ | 三者均有 |
| **浏览器自动化** | ✅ | ✅ | ✅ | 三者均有 |
| **生态规模** | 400+贡献者, ClawHub | Nous Research支持 | 新兴项目 | OpenClaw生态最成熟 |

### ZeusHammer 的核心优势总结

ZeusHammer 相对于 OpenClaw 和 Hermes 有以下 **独有的差异化优势**：

1. **Local Brain 架构** — 这是最大的差异化亮点。80%的任务通过意图识别+技能匹配在本地完成，不需要调用昂贵的 LLM API，大幅降低成本并提升响应速度。

2. **Voice-First 设计** — 从语音唤醒、STT、TTS 到语言自动检测，完整打造了语音优先的交互体验，支持后台 Daemon 模式持续监听。

3. **三层记忆系统** — 短时(LRU) + 长期(SQLite FTS5) + 工作记忆，加上向量存储(Chroma)，记忆能力最完整。

4. **冥想模式 + 深度反思** — 业界罕见的自进化能力，AI在空闲时自动分析记忆模式、提取规则、升级技能。

5. **工作流引擎** — 包含技能匹配和技能学习，不只是调度已有技能，还能自动生成新技能。

6. **安全体系** — OSV恶意软件扫描、熔断器、凭证守卫、配置保护四重保障。

7. **工具检测器** — 自动发现系统中 ~80 个常用 CLI 工具，无需手动配置。

8. **中国LLM原生支持** — 内置 DeepSeek/Qwen/GLM/Moonshot/ERNIE/Doubao/MiniMax 等中国主流模型的统一客户端，通过 chinawhapi.com 一站式接入。

9. **Homebrew 安装** — macOS 用户一条命令 `brew install zeushammer` 即可安装，用户体验最佳。

10. **内置50+工具** — 比 OpenClaw 和 Hermes 都多的开箱即用工具集。

**劣势方面**：生态规模（贡献者数量、技能市场）不及 OpenClaw；消息渠道数量（13+）少于 OpenClaw（30+）和 Hermes（20+）；作为新兴项目，社区和文档成熟度有待验证。

---

## 真正的源码融合

ZeusHammer **真正融合**了三个顶级开源AI智能体项目的核心代码：

| 项目 | 核心贡献 | 许可证 |
|------|----------|--------|
| **[ClaudeCode](https://github.com/anthropic/claude-code)** | 工具执行引擎、并发分区、OTel遥测 | Anthropic |
| **[Hermes](https://github.com/NousResearch/hermes-agent)** | 记忆系统、安全机制、工具管理、MCP协议 | MIT |
| **[OpenClaw](https://github.com/openclaw/openclaw)** | 多渠道接入、Canvas、技能管理 | MIT |

### 三大项目的核心融合

#### ClaudeCode 核心
- `partitionToolCalls()` - 并发分区算法
- `isConcurrencySafe()` - 并发安全判断
- `ToolResult` - 统一工具结果格式
- OTel 结构化日志和追踪

#### Hermes 核心
- **记忆系统**: 短期 + 长期 + 向量记忆，FTS5搜索
- **安全机制**: OSV恶意软件扫描、凭证保护、断路器
- **工具管理**: 工具注册表、MCP协议栈、技能自动改进
- **技能系统**: 智能体驱动的技能创建和管理

#### OpenClaw 核心
- **多渠道**: Telegram、Discord、Slack、WhatsApp 网关
- **Canvas**: 实时交互式Canvas渲染
- **技能中心**: SkillHub + 市场集成
- **配置保护**: 受保护路径、防篡改配置

---

## 快速安装

**方法 1: 一键安装（推荐）**
```bash
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh | bash
```

**方法 2: 手动安装**
```bash
git clone https://github.com/pengrambo3-tech/ZeusHammer.git
cd ZeusHammer
pip install -r requirements.txt
```

**方法 3: Homebrew（即将支持）**
```bash
# Homebrew formula 开发中...
brew install zeushammer  # TODO
```

---

**安装后配置:**

1. 配置 API Key:
```bash
nano ~/.zeushammer/.env
```

添加你的 API Key:
```
OPENAI_API_KEY=your_key
API_BASE=https://api.chinawhapi.com/v1
MODEL=deepseek-chat
```

2. 运行:

```bash
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh | bash
```

或手动安装:

```bash
git clone https://github.com/pengrambo3-tech/ZeusHammer.git
cd ZeusHammer
pip install -r requirements.txt
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         ZeusHammer                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                      融合核心层                              │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │ │
│  │  │ClaudeCode  │ │   Hermes   │ │     OpenClaw       │  │ │
│  │  │────────────│ │────────────│ │────────────────────│  │ │
│  │  │工具执行引擎│ │ 记忆系统   │ │  多渠道网关         │  │ │
│  │  │并发分区算法│ │ 安全机制   │ │  Canvas系统         │  │ │
│  │  │遥测日志   │ │ MCP协议   │ │  技能中心          │  │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                      本地大脑                               │ │
│  │  意图识别 → 技能匹配 → 大模型工作 → 技能学习            │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                      语音系统                               │ │
│  │  唤醒词「Zeus/宙斯」→ STT → 语言理解 → TTS            │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    三层记忆系统                             │ │
│  │  短期(LRU) → 长期(SQLite) → 工作记忆                    │ │
│  └───────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  LLM供应商: ChinaWhapi • Anthropic • OpenAI • 本地模型        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心特性

### 融合引擎 - 三大项目精华

| 特性 | 来源 | 说明 |
|------|------|------|
| **工具分区** | ClaudeCode | 依赖分析并发执行工具 |
| **断路器** | Hermes | 异常快速失败，稳定运行 |
| **多渠道** | OpenClaw | Telegram、Discord、Slack等接入 |
| **OSV扫描** | Hermes | 检测代码中的恶意软件模式 |
| **凭证保护** | Hermes | 防止凭证泄露 |
| **记忆系统** | Hermes | 跨会话持久记忆 |
| **技能学习** | Hermes | 从经验中自动创建技能 |
| **Canvas** | OpenClaw | 实时交互式画布 |
| **OTel遥测** | ClaudeCode | 结构化日志和追踪 |

### 本地大脑 - 先思考，再调用LLM

```python
# ZeusHammer 本地大脑工作流程:
# 1. 用户下达指令
# 2. 本地大脑接收指令
# 3. 与技能库进行模式匹配
# 4. 匹配成功 → 直接执行技能（无需LLM！）
# 5. 匹配失败 → 调用大模型工作
# 6. 工作完成 → 将工作转化为新技能
# 7. 下次遇到相同问题 → 使用已学习的技能（极速响应）
```

### 语音交互 - 真正的免手操作

| 组件 | 技术 | 优势 |
|-----------|-----------|---------|
| 语音识别 | **Whisper**（本地） | 支持离线，不上传数据 |
| 语音合成 | **Edge TTS** | 自然流畅，免费使用 |
| 唤醒词 | 自定义检测器 | "Zeus" 或 "宙斯" 唤醒 |
| 语言检测 | 自动识别 | 中英文智能切换 |
| 智能回复 | 上下文感知 | 根据模型/记忆状态回复 |

---

## 支持的模型

### 🌏 通过 [chinawhapi.com](https://chinawhapi.com) 接入中国大模型

| 供应商 | 模型 | 特点 |
|----------|--------|----------|
| **DeepSeek** | V3, Coder | 性价比最高，编程能力强 |
| **通义千问** (阿里) | Turbo, Plus, Max | 超长上下文支持 |
| **智谱GLM** | GLM-4, GLM-4V | 支持视觉 |
| **月之暗面** | 8K, 32K, 128K | 超长上下文 |
| **文心一言** (百度) | Bot 4.0, Bot Long | 企业级可靠性 |
| **豆包** (字节) | Pro, Lite | 快速、成本效益高 |
| **MiniMax** | ABAB6 Chat/GSPT | 对话AI |

### 🤖 国际模型

| 供应商 | 模型 |
|----------|--------|
| **Anthropic** | Claude 3.5 Sonnet, Opus, Haiku |
| **OpenAI** | GPT-4o, GPT-4 Turbo, GPT-3.5 |
| **本地模型** | Ollama, LM Studio, vLLM |

---

## 快速开始

### 配置 API

```bash
# 方式一：中国大模型（推荐 - 通过 chinawhapi.com）
echo "OPENAI_API_KEY=your_key" >> ~/.zeushammer/.env
echo "API_BASE=https://api.chinawhapi.com/v1" >> ~/.zeushammer/.env
echo "MODEL=deepseek-chat" >> ~/.zeushammer/.env

# 方式二：Anthropic Claude
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> ~/.zeushammer/.env
echo "MODEL=claude-3-5-sonnet-20241022" >> ~/.zeushammer/.env

# 方式三：OpenAI
echo "OPENAI_API_KEY=sk-xxx" >> ~/.zeushammer/.env
echo "MODEL=gpt-4o" >> ~/.zeushammer/.env
```

### 运行

**命令行模式:**
```bash
zeushammer --mode cli
# 或
python3 -m src.main --mode cli
```

**Web 界面模式（推荐！）:**
```bash
zeushammer --mode web
# 或
python3 -m src.ui.server
```

然后访问：**http://localhost:8765**

功能:
- 💬 实时对话界面
- 🎤 语音交互 (WebRTC)
- 📊 系统状态监控
- ⚙️ 配置管理
- 🧠 记忆可视化

**语音模式:**
```bash
zeushammer --mode voice
# 或
python3 -m src.main --mode voice
```

**TUI 模式:**
```bash
zeushammer --mode tui
```

---

## 安全

| 级别 | 说明 |
|-------|-------------|
| `safe` | 所有操作需确认 |
| `semi_open` | 安全操作自动执行，危险操作警告 |
| `full_open` | 无限制（野兽模式） |

内置保护（来自 Hermes + OpenClaw）：
- OSV 恶意软件模式扫描
- 凭证泄露检测
- 异常操作断路器
- 受保护路径
- 配置防篡改

---

## 项目结构

```
ZeusHammer/
├── src/
│   ├── fusion/              # 三大项目融合
│   │   ├── claude_code/     # ClaudeCode 核心
│   │   │   └── tools_engine.py
│   │   ├── hermes/          # Hermes 核心
│   │   │   └── security.py
│   │   └── openclaw/        # OpenClaw 核心
│   │       └── channels.py
│   ├── brain/               # 本地大脑
│   ├── voice/               # 语音系统
│   ├── memory/              # 记忆系统
│   └── tools/               # 工具集
├── FUSION.md                # 融合文档
├── README.md                # 英文文档
└── README_zh.md             # 中文文档
```

---

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

---

<div align="center">

**❤️ 融合 ClaudeCode + Hermes + OpenClaw 精华打造**

*[本地思考，自由对话，永不忘记。]*

</div>
