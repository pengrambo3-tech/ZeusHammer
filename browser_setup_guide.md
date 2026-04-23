# ZeusHammer 浏览器持久化登录配置指南

## 🎯 目标
解决每次自动化执行都需要重新登录的问题，实现一次登录、长期复用。

---

## ✅ 方案：使用 Chrome 用户数据目录

**原理：**
- 使用 `--user-data-dir` 参数指定 Chrome 用户数据目录
- 该目录保存所有 Cookie、LocalStorage、密码、扩展等
- 自动化时复用这个目录，就等于复用您的登录状态

**优势：**
- ✅ 免费（Playwright 开源）
- ✅ 无需安装新浏览器
- ✅ 支持所有网站（GitHub、小红书、微信公众号等）
- ✅ 一次登录，永久复用

---

## 📋 配置步骤

### 步骤 1：创建浏览器配置目录

```bash
mkdir -p /Users/imac/.zeushammer/browser-profile
```

### 步骤 2：首次手动登录（重要！）

**关闭所有 Chrome 窗口**，然后执行：

```bash
# 完全关闭 Chrome
pkill -f "Google Chrome"

# 使用专用配置启动 Chrome
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="/Users/imac/.zeushammer/browser-profile"
```

**然后：**
1. 在打开的 Chrome 中登录所有需要的网站：
   - GitHub
   - 小红书（https://creator.xiaohongshu.com）
   - 微信公众号（https://mp.weixin.qq.com）
   - 其他需要的网站

2. 保持登录状态，关闭 Chrome

### 步骤 3：修改 ZeusHammer 代码

**文件：** `src/browser/playwright_browser.py`

**修改 `initialize` 方法：**

```python
async def initialize(self) -> bool:
    """初始化浏览器"""
    try:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()

        # 启动参数
        launch_options = {
            "headless": self.config.headless,
        }

        if self.config.user_agent:
            launch_options["user_agent"] = self.config.user_agent

        if self.config.proxy:
            launch_options["proxy"] = {
                "server": self.config.proxy,
            }

        # 隐身模式
        if self.config.stealth:
            launch_options["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]

        # 启动浏览器
        self._browser = await playwright.chromium.launch(**launch_options)

        # ========== 新增：使用持久化上下文 ==========
        context_options = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            # 使用用户数据目录（关键！）
            "user_data_dir": "/Users/imac/.zeushammer/browser-profile",
        }

        # 如果有 storage_state 也保留
        if self.config.storage_state:
            context_options["storage_state"] = self.config.storage_state

        # 创建持久化上下文（替代 new_context）
        self._context = await playwright.chromium.launch_persistent_context(
            **context_options
        )

        # 获取或创建页面
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
        
        self._pages["main"] = self._page

        logger.info("Playwright browser initialized with persistent context")
        return True

    except ImportError:
        logger.error("Playwright not installed: pip install playwright")
        return False
    except Exception as e:
        logger.error(f"Browser init failed: {e}")
        return False
```

### 步骤 4：测试

```bash
cd ZeusHammer
python3 -m src.main --mode cli

>>> 打开小红书创作平台
>>> 截图
```

应该直接显示已登录状态，无需重新登录！

---

## 🔧 高级配置

### 多配置文件管理

可以为不同用途创建多个配置文件：

```bash
# 工作配置
mkdir -p /Users/imac/.zeushammer/browser-profile-work

# 测试配置
mkdir -p /Users/imac/.zeushammer/browser-profile-test
```

在代码中通过配置切换：

```python
# config.yaml
browser:
  user_data_dir: "/Users/imac/.zeushammer/browser-profile-work"
```

### 导出/导入登录状态

如果需要备份或迁移：

```bash
# 导出
cp -r /Users/imac/.zeushammer/browser-profile ~/backup/browser-profile-backup

# 导入
cp -r ~/backup/browser-profile-backup /Users/imac/.zeushammer/browser-profile
```

---

## ⚠️ 注意事项

1. **首次配置时必须手动登录**
   - 这是最关键的一步
   - 登录所有需要的网站后再关闭

2. **定期清理缓存**
   - 如果浏览器变慢，可以清理缓存但保留 Cookie
   - 删除 `/Users/imac/.zeushammer/browser-profile/Default/Cache`

3. **避免同时打开**
   - 不要让普通 Chrome 和自动化 Chrome 使用同一个用户数据目录
   - 可能导致数据冲突

4. **安全性**
   - 这个目录包含您的登录凭证
   - 不要分享给他人
   - 建议加密备份

---

## 🆘 故障排除

### 问题 1：仍然需要登录

**原因：** Cookie 未保存或已过期

**解决：**
```bash
# 1. 完全关闭 Chrome
pkill -f "Google Chrome"

# 2. 删除配置目录
rm -rf /Users/imac/.zeushammer/browser-profile

# 3. 重新执行步骤 2
```

### 问题 2：浏览器无法启动

**原因：** 用户数据目录权限问题

**解决：**
```bash
chmod -R 755 /Users/imac/.zeushammer/browser-profile
```

### 问题 3：网站检测到自动化

**解决：** 启用隐身模式
```python
config.stealth = True
```

---

## 📚 参考资料

- [Playwright Persistent Context](https://playwright.dev/docs/auth#reusing-authentication-state)
- [Chrome User Data Directory](https://chromium.googlesource.com/chromium/src/+/master/docs/user_data_dir.md)

---

**配置完成后，您的 ZeusHammer 就可以直接使用已登录的浏览器会话，无需每次都授权！**
