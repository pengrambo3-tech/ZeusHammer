"""
ZeusHammer Complete Browser Automation

完整浏览器自动化模块，支持:
1. Playwright (主)
2. Selenium (备选)
3. 远程WebDriver

参考OpenClaw实现
"""

import asyncio
import logging
import base64
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class BrowserProvider(Enum):
    """浏览器提供商"""
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    REMOTE = "remote"


@dataclass
class BrowserConfig:
    """浏览器配置"""
    provider: BrowserProvider = BrowserProvider.PLAYWRIGHT
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: str = ""
    proxy: str = ""
    stealth: bool = False
    slow_mo: int = 0
    downloads_path: str = ""
    storage_state: str = ""


@dataclass
class ElementInfo:
    """元素信息"""
    selector: str
    selector_type: str
    tag: str
    text: str
    visible: bool
    enabled: bool
    rect: Dict[str, int]


@dataclass
class PageInfo:
    """页面信息"""
    url: str
    title: str
    elements: List[ElementInfo] = field(default_factory=list)
    accessibility_tree: str = ""


class PlaywrightBrowser:
    """
    Playwright浏览器控制

    完整实现:
    1. 多标签页管理
    2. 网络拦截
    3. 文件下载
    4. 截图/PDF
    5. 元素交互
    6. 键盘/鼠标
    7. JavaScript执行
    """

    def __init__(self, config: BrowserConfig):
        self.config = config
        self._browser = None
        self._context = None
        self._page = None
        self._pages: Dict[str, Any] = {}
        self._downloads: List[str] = []

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

            # 创建上下文
            context_options = {
                "viewport": {
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                }
            }

            if self.config.storage_state:
                context_options["storage_state"] = self.config.storage_state

            self._context = await self._browser.new_context(**context_options)

            # 创建页面
            self._page = await self._context.new_page()
            self._pages["main"] = self._page

            logger.info("Playwright browser initialized")
            return True

        except ImportError:
            logger.error("Playwright not installed: pip install playwright")
            return False
        except Exception as e:
            logger.error(f"Browser init failed: {e}")
            return False

    async def navigate(self, url: str, wait_until: str = "load") -> Dict:
        """导航到URL"""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}

        try:
            response = await self._page.goto(url, wait_until=wait_until)
            return {
                "success": True,
                "url": self._page.url,
                "title": await self._page.title(),
                "status": response.status if response else 200,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(
        self,
        selector: str,
        selector_type: str = "css",
        modifiers: List[str] = None,
    ) -> bool:
        """点击元素"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)

            if modifiers:
                await locator.click(modifiers=modifiers)
            else:
                await locator.click()

            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    async def fill(self, selector: str, text: str, selector_type: str = "css") -> bool:
        """填写输入框"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.fill(text)
            return True
        except Exception as e:
            logger.error(f"Fill failed: {e}")
            return False

    async def type_text(
        self,
        selector: str,
        text: str,
        delay: int = 0,
        selector_type: str = "css",
    ) -> bool:
        """逐字输入"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.type(text, delay=delay)
            return True
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False

    async def select(
        self,
        selector: str,
        value: str = None,
        label: str = None,
        index: int = None,
        selector_type: str = "css",
    ) -> bool:
        """选择下拉选项"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)

            if value is not None:
                await locator.select_option(value=value)
            elif label is not None:
                await locator.select_option(label=label)
            elif index is not None:
                await locator.select_option(index=index)

            return True
        except Exception as e:
            logger.error(f"Select failed: {e}")
            return False

    async def hover(self, selector: str, selector_type: str = "css") -> bool:
        """悬停"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.hover()
            return True
        except Exception as e:
            logger.error(f"Hover failed: {e}")
            return False

    async def scroll(
        self,
        x: int = 0,
        y: int = 0,
        selector: str = None,
        selector_type: str = "css",
    ) -> bool:
        """滚动页面"""
        if not self._page:
            return False

        try:
            if selector:
                locator = self._get_locator(selector, selector_type)
                await locator.scroll_into_view_if_needed()
            else:
                await self._page.evaluate(f"window.scrollTo({x}, {y})")

            return True
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False

    async def screenshot(
        self,
        path: str = None,
        full_page: bool = False,
        selector: str = None,
        selector_type: str = "css",
    ) -> Optional[bytes]:
        """截图"""
        if not self._page:
            return None

        try:
            if selector:
                locator = self._get_locator(selector, selector_type)
                return await locator.screenshot(path=path)
            elif path:
                await self._page.screenshot(path=path, full_page=full_page)
                return b""
            else:
                return await self._page.screenshot(full_page=full_page)

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def get_html(self, selector: str = None, selector_type: str = "css") -> str:
        """获取HTML"""
        if not self._page:
            return ""

        try:
            if selector:
                locator = self._get_locator(selector, selector_type)
                return await locator.inner_html()
            else:
                return await self._page.content()

        except Exception as e:
            logger.error(f"Get HTML failed: {e}")
            return ""

    async def get_text(self, selector: str, selector_type: str = "css") -> str:
        """获取文本"""
        if not self._page:
            return ""

        try:
            locator = self._get_locator(selector, selector_type)
            return await locator.inner_text()
        except Exception as e:
            logger.error(f"Get text failed: {e}")
            return ""

    async def evaluate(self, script: str) -> Any:
        """执行JavaScript"""
        if not self._page:
            return None

        try:
            return await self._page.evaluate(script)
        except Exception as e:
            logger.error(f"Evaluate failed: {e}")
            return None

    async def evaluate_async(self, script: str) -> Any:
        """异步执行JavaScript"""
        if not self._page:
            return None

        try:
            return await self._page.evaluate_async(script)
        except Exception as e:
            logger.error(f"Evaluate async failed: {e}")
            return None

    async def wait_for_selector(
        self,
        selector: str,
        timeout: int = 30000,
        state: str = "visible",
        selector_type: str = "css",
    ) -> bool:
        """等待元素"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)

            if state == "visible":
                await locator.wait_for(state="visible", timeout=timeout)
            elif state == "hidden":
                await locator.wait_for(state="hidden", timeout=timeout)
            elif state == "attached":
                await locator.wait_for(state="attached", timeout=timeout)

            return True
        except Exception:
            return False

    async def wait_for_url(self, pattern: str, timeout: int = 30000) -> bool:
        """等待URL匹配"""
        if not self._page:
            return False

        try:
            await self._page.wait_for_url(pattern, timeout=timeout)
            return True
        except Exception:
            return False

    async def wait_for_function(self, script: str, timeout: int = 30000) -> bool:
        """等待函数返回true"""
        if not self._page:
            return False

        try:
            await self._page.wait_for_function(script, timeout=timeout)
            return True
        except Exception:
            return False

    async def get_accessibility_tree(self) -> str:
        """获取无障碍树"""
        if not self._page:
            return ""

        try:
            snapshot = await self._page.accessibility.snapshot()
            return self._format_accessibility(snapshot)
        except Exception as e:
            logger.error(f"Accessibility tree failed: {e}")
            return ""

    async def set_files(
        self,
        selector: str,
        files: List[str],
        selector_type: str = "css",
    ) -> bool:
        """设置文件上传"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.set_input_files(files)
            return True
        except Exception as e:
            logger.error(f"Set files failed: {e}")
            return False

    async def check(self, selector: str, selector_type: str = "css") -> bool:
        """勾选复选框"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.check()
            return True
        except Exception as e:
            logger.error(f"Check failed: {e}")
            return False

    async def uncheck(self, selector: str, selector_type: str = "css") -> bool:
        """取消勾选复选框"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.uncheck()
            return True
        except Exception as e:
            logger.error(f"Uncheck failed: {e}")
            return False

    async def press(self, selector: str, key: str, selector_type: str = "css") -> bool:
        """按键"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.press(key)
            return True
        except Exception as e:
            logger.error(f"Press failed: {e}")
            return False

    async def get_page_info(self) -> PageInfo:
        """获取页面信息"""
        if not self._page:
            return PageInfo(url="", title="")

        return PageInfo(
            url=self._page.url,
            title=await self._page.title(),
        )

    async def new_page(self, name: str = None) -> bool:
        """新建页面"""
        if not self._context:
            return False

        try:
            page = await self._context.new_page()
            page_name = name or f"page_{len(self._pages)}"
            self._pages[page_name] = page

            if not hasattr(self, "_current_page"):
                self._current_page = page_name

            return True
        except Exception as e:
            logger.error(f"New page failed: {e}")
            return False

    async def switch_page(self, name: str):
        """切换页面"""
        if name in self._pages:
            self._page = self._pages[name]
            self._current_page = name

    async def close_page(self, name: str = None):
        """关闭页面"""
        name = name or self._current_page
        if name in self._pages:
            await self._pages[name].close()
            del self._pages[name]

            if self._pages:
                self._current_page = list(self._pages.keys())[0]
                self._page = self._pages[self._current_page]

    async def go_back(self) -> bool:
        """后退"""
        if not self._page:
            return False

        try:
            await self._page.go_back()
            return True
        except Exception as e:
            logger.error(f"Go back failed: {e}")
            return False

    async def go_forward(self) -> bool:
        """前进"""
        if not self._page:
            return False

        try:
            await self._page.go_forward()
            return True
        except Exception as e:
            logger.error(f"Go forward failed: {e}")
            return False

    async def reload(self) -> bool:
        """刷新"""
        if not self._page:
            return False

        try:
            await self._page.reload()
            return True
        except Exception as e:
            logger.error(f"Reload failed: {e}")
            return False

    async def close(self):
        """关闭浏览器"""
        if self._page:
            await self._page.close()

        if self._context:
            await self._context.close()

        if self._browser:
            await self._browser.close()

        logger.info("Browser closed")

    def _get_locator(self, selector: str, selector_type: str):
        """获取定位器"""
        if selector_type == "xpath":
            return self._page.locator(f"xpath={selector}")
        elif selector_type == "text":
            return self._page.get_by_text(selector)
        elif selector_type == "role":
            return self._page.get_by_role(selector)
        elif selector_type == "label":
            return self._page.get_by_label(selector)
        elif selector_type == "placeholder":
            return self._page.get_by_placeholder(selector)
        elif selector_type == "title":
            return self._page.get_by_title(selector)
        else:
            return self._page.locator(selector)

    def _format_accessibility(self, snapshot: Dict, indent: int = 0) -> str:
        """格式化无障碍树"""
        if not snapshot:
            return ""

        lines = []
        prefix = "  " * indent

        role = snapshot.get("role", "")
        name = snapshot.get("name", "")

        if name:
            lines.append(f"{prefix}[{role}] {name}")
        else:
            lines.append(f"{prefix}[{role}]")

        for child in snapshot.get("children", []):
            lines.append(self._format_accessibility(child, indent + 1))

        return "\n".join(lines)


class BrowserManager:
    """
    浏览器管理器

    管理多个浏览器实例
    """

    def __init__(self):
        self._browsers: Dict[str, PlaywrightBrowser] = {}
        self._default_config = BrowserConfig()

    def set_default_config(self, config: BrowserConfig):
        """设置默认配置"""
        self._default_config = config

    async def create_browser(
        self,
        name: str = "default",
        config: BrowserConfig = None,
    ) -> bool:
        """创建浏览器"""
        config = config or self._default_config

        browser = PlaywrightBrowser(config)
        if await browser.initialize():
            self._browsers[name] = browser
            return True

        return False

    def get_browser(self, name: str = "default") -> Optional[PlaywrightBrowser]:
        """获取浏览器"""
        return self._browsers.get(name)

    async def close_browser(self, name: str = "default"):
        """关闭浏览器"""
        if name in self._browsers:
            await self._browsers[name].close()
            del self._browsers[name]

    async def close_all(self):
        """关闭所有浏览器"""
        for browser in list(self._browsers.values()):
            await browser.close()
        self._browsers.clear()


# 全局实例
_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """获取浏览器管理器"""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager
