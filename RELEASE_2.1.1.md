# ZeusHammer v2.1.1 紧急修复发布

**发布日期:** 2026-04-23  
**修复类型:** 紧急 Bug 修复

---

## 🐛 修复的问题

### Issue #4 - WSL2 意图识别错误

**问题描述:**
用户输入"查询微软今天的股价"时，系统错误匹配到"读取文件"技能，而不是执行网页搜索。

**根本原因:**
意图识别逻辑中，"查询"一词没有被识别为 WEB_SEARCH 意图触发词。

**修复方案:**
- 添加"查询"、"股价"、"股票"、"价格"、"行情"等触发词到 WEB_SEARCH 意图
- 优化意图匹配优先级，金融/股票查询优先于文件读取

### Issue #3 - Mac M1 Pro 安装问题

**问题描述:**
- install.sh 第 113 行括号不匹配（bash 语法错误）
- macOS 直接二进制下载 404
- Python 3.10+ 检测失败

**状态:**
- 当前版本语法检查已通过
- 如仍有问题，请提供完整错误日志

---

## 📝 文档更新

1. **README.md**
   - 标记 Homebrew 安装为 "Coming Soon"
   - 添加 WebUI 使用说明
   - 添加快速开始指南
   - 添加示例用法

2. **新增功能说明**
   - CLI 模式：`zeushammer --mode cli`
   - Web UI 模式：`zeushammer --mode web`（推荐）
   - 语音模式：`zeushammer --mode voice`

---

## 🔄 如何更新

**如果您已安装 ZeusHammer:**
```bash
cd ZeusHammer
git pull origin master
```

**全新安装:**
```bash
curl -sSL https://raw.githubusercontent.com/pengrambo3-tech/ZeusHammer/master/install.sh | bash
```

---

## 📧 联系我们

如遇到问题，请：
1. 在 GitHub 提交 Issue: https://github.com/pengrambo3-tech/ZeusHammer/issues
2. 附上完整错误日志
3. 说明您的操作系统和 Python 版本

---

**感谢以下用户的反馈:**
- @minne100 (Issue #4)
- @quantumthoughter (Issue #3)
- @OLShopping (Issue #2)
