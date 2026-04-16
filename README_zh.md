# ZuesHammer - 宙斯之锤

<div align="center">

![版本](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-green.svg)
![许可证](https://img.shields.io/badge/License-MIT-yellow.svg)

**🤖 具备本地大脑和语音交互的智能AI助手**

*本地思考，自由对话，永不忘记。*

</div>

---

## ZuesHammer 与众不同之处？

不同于普通的 AI 助手，ZuesHammer 融合了**三项突破性技术**：

| 特性 | 功能 |
|---------|-------------|
| 🧠 **本地大脑** | 意图识别 + 模式匹配，自动学习新技能 |
| 🎙️ **语音优先** | 本地 Whisper STT + Edge TTS，真正免手操作 |
| 🧬 **三层记忆** | 短期(LRU缓存) → 长期(SQLite) → 工作记忆 |

---

## 支持的模型

### 🌏 通过 [chinawhapi.com](https://chinawhapi.com) 接入中国大模型

使用单一 API Key 统一接入所有主流中国大模型：

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

## 核心特性

### 🧠 本地大脑 - 先思考，再调用LLM

让 ZuesHammer 与众不同的核心创新：

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

**优势:**
- **提速80%** - 模式匹配的技能直接执行，无需等待LLM
- **成本更低** - 仅在必要时调用昂贵的LLM
- **自我进化** - 从每个任务中学习，越用越聪明
- **隐私保护** - 简单模式处理在本地完成，不上传云端

### 🎙️ 语音交互 - 真正的免手操作

完整的本地语音处理管道：

| 组件 | 技术 | 优势 |
|-----------|-----------|---------|
| 语音识别 | **Whisper**（本地） | 支持离线，不上传数据 |
| 语音合成 | **Edge TTS** | 自然流畅，免费使用 |
| 唤醒词 | 自定义检测器 | "嘿，助手" 唤醒 |
| 语言检测 | 多语言支持 | 自动识别中英文 |

```bash
# 语音模式示例
python3 -m src.main --mode voice
# 说："帮我读取 /tmp/test.txt"
# 或者："搜索 Python 教程"
```

### 🧬 三层记忆系统

融合 ClaudeCode、Hermes、OpenClaw 最佳实践：

| 层级 | 存储 | 用途 | 持续时间 |
|-------|---------|---------|----------|
| **短期记忆** | LRU缓存（内存） | 热点数据，即时访问 | ~1小时 |
| **长期记忆** | SQLite | 持久化知识 | 永久 |
| **工作记忆** | 活跃上下文 | 当前任务状态 | 会话期间 |

---

## 快速开始

```bash
# 克隆
git clone https://github.com/pengrambo3-tech/zueshammer.git
cd zueshammer

# 安装
python3 install.py

# 配置 - 选择你喜欢的API供应商
```

### 方式一：中国大模型（推荐 - 通过 chinawhapi.com）

```bash
# 一个API Key调用所有中国大模型: DeepSeek, 通义千问, 智谱, 月之暗面, 文心, 豆包, MiniMax
# 从 https://chinawhapi.com/console 获取密钥
echo "CHINAWHAPI_KEY=你的密钥" >> ~/.zueshammer/.env
echo "API_PROVIDER=chinawhapi" >> ~/.zueshammer/.env
echo "MODEL=deepseek-chat" >> ~/.zueshammer/.env
```

### 方式二：使用你自己的API（任意OpenAI兼容接口）

```bash
# 可以是 ChinaWhapi 或任何其他 OpenAI 兼容接口
echo "OPENAI_API_KEY=你的密钥" >> ~/.zueshammer/.env
echo "API_PROVIDER=openai" >> ~/.zueshammer/.env
echo "API_BASE=https://api.chinawhapi.com/v1" >> ~/.zueshammer/.env
echo "MODEL=deepseek-chat" >> ~/.zueshammer/.env
```

### 方式三：Anthropic Claude

```bash
echo "ANTHROPIC_API_KEY=sk-ant-xxx" >> ~/.zueshammer/.env
echo "API_PROVIDER=anthropic" >> ~/.zueshammer/.env
echo "MODEL=claude-3-5-sonnet-20241022" >> ~/.zueshammer/.env
```

### 方式四：OpenAI

```bash
echo "OPENAI_API_KEY=sk-xxx" >> ~/.zueshammer/.env
echo "API_PROVIDER=openai" >> ~/.zueshammer/.env
echo "MODEL=gpt-4o" >> ~/.zueshammer/.env
```

### 运行

```bash
python3 -m src.main --mode cli   # 命令行
python3 -m src.main --mode web   # 网页界面
python3 -m src.main --mode voice # 语音模式（推荐！）
```

---

## API配置

### chinawhapi.com（中国大模型）

```bash
# 从 https://chinawhapi.com/console 获取
CHINAWHAPI_KEY=你的统一密钥
API_PROVIDER=chinawhapi
MODEL=deepseek-chat  # 可选: qwen-plus, glm-4, moonshot-v1-32k 等
```

### Anthropic

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

---

## 高级：OpenClaw风格多模型配置

对于高级用户，ZuesHammer支持OpenClaw风格的多模型路由和自动故障转移。

### 多Provider配置

复制 `config/example_config.yaml` 到 `~/.zueshammer/config.yaml`:

```yaml
models:
  default_provider: claude

  providers:
    claude:
      api_key: ${ANTHROPIC_API_KEY}
      model: claude-3-5-sonnet-20241022
      priority: 1

    china:
      api_base: https://api.chinawhapi.com/v1
      api_key: ${CHINAWHAPI_KEY}
      model: deepseek-chat
      priority: 3

  # 关键词自动路由
  routing_rules:
    - keywords: [code, debug, 编程]
      provider: claude
      model: claude-opus-4-5

    - keywords: [search, 搜索]
      provider: china
      model: deepseek-chat

  # 故障转移链
  fallback:
    - provider: claude
      model: claude-3-5-haiku-20241022
```

### 路由特性

| 特性 | 说明 |
|---------|-------------|
| **关键词路由** | 根据查询关键词自动选择模型 |
| **任务类型路由** | 代码 → Claude, 搜索 → DeepSeek |
| **故障转移** | 限流时自动切换 |
| **多Provider** | 同时使用多个API |

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    ZuesHammer                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  本地大脑   │  │  语音系统   │  │  记忆系统   │   │
│  │             │  │             │  │             │   │
│  │ 意图识别   │  │ Whisper STT │  │ 短期记忆   │   │
│  │ 技能匹配   │  │ Edge TTS    │  │ 长期记忆   │   │
│  │ 自动学习   │  │ 唤醒词检测   │  │ 工作记忆   │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │             │
│  ┌──────┴────────────────┴────────────────┴──────┐   │
│  │              核心引擎                          │   │
│  │  权限管理 • 事件总线 • 任务管道               │   │
│  └───────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  LLM供应商: ChinaWhapi • Anthropic • OpenAI • 本地模型  │
└─────────────────────────────────────────────────────────┘
```

---

## 安全

| 级别 | 说明 |
|-------|-------------|
| `safe` | 所有操作需确认 |
| `semi_open` | 安全操作自动执行，危险操作警告 |
| `full_open` | 无限制（野兽模式） |

内置保护：
- 凭证泄露检测
- 恶意软件模式扫描
- 异常操作断路器
- 配置防篡改

---

## 开发

```bash
# 运行测试
pytest tests/

# 代码格式化
black src/
ruff check src/
```

---

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

---

<div align="center">

**用 ❤️ 为 AI 社区打造**

*[本地思考，自由对话，永不忘记。]*

</div>
