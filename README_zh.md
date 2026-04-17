# ZuesHammer - 宙斯之锤

<div align="center">

![版本](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![许可证](https://img.shields.io/badge/License-MIT-yellow.svg)

**🚀 融合三大开源项目精华的超级AI智能体**

*本地思考，自由对话，永不忘记。*

</div>

---

## 真正的源码融合

ZuesHammer **真正融合**了三个顶级开源AI智能体项目的核心代码：

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

## 一键安装

```bash
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/zueshammer/master/install.sh | bash
```

或手动安装:

```bash
git clone https://github.com/pengrambo3-tech/zueshammer.git
cd zueshammer
pip install -r requirements.txt
```

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         ZuesHammer                                │
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
│  │  唤醒词「Zues/宙斯」→ STT → 语言理解 → TTS            │ │
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
# ZuesHammer 本地大脑工作流程:
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
| 唤醒词 | 自定义检测器 | "Zues" 或 "宙斯" 唤醒 |
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
echo "OPENAI_API_KEY=your_key" >> ~/.zueshammer/.env
echo "API_BASE=https://api.chinawhapi.com/v1" >> ~/.zueshammer/.env
echo "MODEL=deepseek-chat" >> ~/.zueshammer/.env

# 方式二：Anthropic Claude
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> ~/.zueshammer/.env
echo "MODEL=claude-3-5-sonnet-20241022" >> ~/.zueshammer/.env

# 方式三：OpenAI
echo "OPENAI_API_KEY=sk-xxx" >> ~/.zueshammer/.env
echo "MODEL=gpt-4o" >> ~/.zueshammer/.env
```

### 运行

```bash
python3 -m src.main --mode cli   # 命令行
python3 -m src.main --mode web   # 网页界面
python3 -m src.main --mode voice  # 语音模式（推荐！）
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
ZuesHammer/
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
