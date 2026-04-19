"""
ZeusHammer 浏览器编排器 - 完整实现

真正实现Playwright浏览器控制。
"""

import asyncio
import logging
import base64
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright")


class BrowserProvider(Enum):
    """浏览器提供者"""
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    REMOTE = "remote"


@dataclass
class PageInfo:
    """页面信息"""
    url: str
    title: str
    viewport_size: Tuple[int, int]
    ready: bool = True


@dataclass
class Element:
    """页面元素"""
    selector: str
    selector_type: str
    tag: str
    text: str
    visible: bool
    enabled: bool
    rect: Dict[str, int]


class BrowserOrchestrator:
    """
    浏览器编排器 - 完整实现

    支持Playwright真正的浏览器控制。
    """

    def __init__(
        self,
        provider: str = "playwright",
        headless: bool = True,
        viewport: Tuple[int, int] = (1280, 720),
        slow_mo: int = 0,
    ):
        self.provider = BrowserProvider(provider)
        self.headless = headless
        self.viewport = viewport
        self.slow_mo = slow_mo

        # Playwright对象
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._initialized = False

        # 多页面管理
        self._pages: Dict[str, Page] = {}
        self._current_page_id = "main"

    async def initialize(self) -> bool:
        """初始化浏览器"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not available")
            return False

        try:
            logger.info(f"初始化浏览器 (provider: {self.provider.value})")

            self._playwright = await async_playwright().start()

            # 启动浏览器
            launch_options = {
                "headless": self.headless,
                "slow_mo": self.slow_mo,
            }

            if self.provider == BrowserProvider.PLAYWRIGHT:
                self._browser = await self._playwright.chromium.launch(**launch_options)
            elif self.provider == BrowserProvider.SELENIUM:
                # Selenium通过Remote连接
                self._browser = await self._playwright.chromium.launch(**launch_options)
            else:
                self._browser = await self._playwright.chromium.launch(**launch_options)

            # 创建上下文
            self._context = await self._browser.new_context(
                viewport={"width": self.viewport[0], "height": self.viewport[1]}
            )

            # 创建主页面
            self._page = await self._context.new_page()
            self._pages["main"] = self._page

            self._initialized = True
            logger.info("浏览器初始化完成")
            return True

        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            return False

    async def new_page(self, url: str = None) -> PageInfo:
        """新建页面"""
        if not self._initialized:
            await self.initialize()

        page_id = f"page_{len(self._pages)}"
        page = await self._context.new_page()
        self._pages[page_id] = page

        if url:
            await page.goto(url)

        self._page = page
        self._current_page_id = page_id

        return PageInfo(
            url=page.url,
            title=await page.title(),
            viewport_size=self.viewport
        )

    async def navigate(self, url: str, wait_until: str = "load") -> PageInfo:
        """导航到URL"""
        if not self._initialized:
            await self.initialize()

        if not self._page:
            await self.new_page(url)
        else:
            wait_map = {
                "load": "load",
                "domcontentloaded": "domcontentloaded",
                "networkidle": "networkidle",
            }
            await self._page.goto(url, wait_until=wait_map.get(wait_until, "load"))

        return PageInfo(
            url=self._page.url,
            title=await self._page.title(),
            viewport_size=self.viewport
        )

    async def screenshot(self, path: str = None, full_page: bool = False) -> bytes:
        """截图"""
        if not self._page:
            return b""

        try:
            if path:
                await self._page.screenshot(path=path, full_page=full_page)
                return b""
            else:
                return await self._page.screenshot(full_page=full_page)
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return b""

    async def find_element(
        self,
        selector: str,
        selector_type: str = "css"
    ) -> Optional[Element]:
        """查找单个元素"""
        if not self._page:
            return None

        try:
            locator = self._get_locator(selector, selector_type)

            # 检查元素是否存在
            count = await locator.count()
            if count == 0:
                return None

            first = locator.first

            # 获取元素信息
            tag = await first.evaluate("el => el.tagName")
            text = await first.inner_text()
            visible = await first.is_visible()
            enabled = await first.is_enabled()
            box = await first.bounding_box()

            return Element(
                selector=selector,
                selector_type=selector_type,
                tag=tag.lower(),
                text=text[:200],
                visible=visible,
                enabled=enabled,
                rect={"x": box.x, "y": box.y, "width": box.width, "height": box.height} if box else {}
            )

        except Exception as e:
            logger.debug(f"查找元素失败: {selector} - {e}")
            return None

    async def find_elements(
        self,
        selector: str,
        selector_type: str = "css"
    ) -> List[Element]:
        """查找多个元素"""
        if not self._page:
            return []

        try:
            locator = self._get_locator(selector, selector_type)
            count = await locator.count()

            elements = []
            for i in range(min(count, 100)):  # 最多100个
                el = locator.nth(i)
                try:
                    tag = await el.evaluate("el => el.tagName")
                    text = await el.inner_text()
                    visible = await el.is_visible()

                    elements.append(Element(
                        selector=selector,
                        selector_type=selector_type,
                        tag=tag.lower(),
                        text=text[:200],
                        visible=visible,
                        enabled=True,
                        rect={}
                    ))
                except Exception:
                    pass

            return elements

        except Exception as e:
            logger.debug(f"查找元素失败: {selector} - {e}")
            return []

    def _get_locator(self, selector: str, selector_type: str):
        """获取Playwright定位器"""
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

    async def click(
        self,
        selector: str,
        selector_type: str = "css",
        modifiers: List[str] = None,
        button: str = "left",
        click_count: int = 1,
    ):
        """点击元素"""
        if not self._page:
            return

        locator = self._get_locator(selector, selector_type)

        await locator.click(
            modifiers=modifiers or [],
            button=button,
            click_count=click_count,
            timeout=5000
        )

    async def fill(
        self,
        selector: str,
        text: str,
        selector_type: str = "css",
        delay: int = 0,
    ):
        """填写表单"""
        if not self._page:
            return

        locator = self._get_locator(selector, selector_type)

        if delay > 0:
            await locator.type(text, delay=delay)
        else:
            await locator.fill(text)

    async def type_text(
        self,
        selector: str,
        text: str,
        delay: int = 100,
        selector_type: str = "css",
    ):
        """逐字输入"""
        if not self._page:
            return

        locator = self._get_locator(selector, selector_type)
        await locator.type(text, delay=delay)

    async def select(
        self,
        selector: str,
        value: str = None,
        label: str = None,
        index: int = None,
        selector_type: str = "css",
    ):
        """选择下拉选项"""
        if not self._page:
            return

        locator = self._get_locator(selector, selector_type)

        if value is not None:
            await locator.select_option(value=value)
        elif label is not None:
            await locator.select_option(label=label)
        elif index is not None:
            await locator.select_option(index=index)

    async def check(self, selector: str, checked: bool = True, selector_type: str = "css"):
        """勾选/取消勾选复选框"""
        if not self._page:
            return

        locator = self._get_locator(selector, selector_type)

        if checked:
            await locator.check()
        else:
            await locator.uncheck()

    async def hover(self, selector: str, selector_type: str = "css"):
        """悬停"""
        if not self._page:
            return

        locator = self._get_locator(selector, selector_type)
        await locator.hover()

    async def scroll(
        self,
        x: int = 0,
        y: int = 0,
        selector: str = None,
        selector_type: str = "css",
    ):
        """滚动"""
        if not self._page:
            return

        if selector:
            locator = self._get_locator(selector, selector_type)
            await locator.scroll_into_view_if_needed()
        else:
            await self._page.evaluate(f"window.scrollTo({x}, {y})")

    async def evaluate(self, script: str) -> Any:
        """执行JavaScript"""
        if not self._page:
            return None

        return await self._page.evaluate(script)

    async def evaluate_async(self, script: str) -> Any:
        """异步执行JavaScript"""
        if not self._page:
            return None

        return await self._page.evaluate_async(script)

    async def get_dom(self, max_length: int = 50000) -> str:
        """获取DOM内容"""
        if not self._page:
            return ""

        content = await self._page.content()
        return content[:max_length]

    async def get_html(self, selector: str = None, selector_type: str = "css") -> str:
        """获取HTML"""
        if not self._page:
            return ""

        if selector:
            locator = self._get_locator(selector, selector_type)
            return await locator.inner_html()
        else:
            return await self._page.content()

    async def get_text(self, selector: str, selector_type: str = "css") -> str:
        """获取文本"""
        if not self._page:
            return ""

        locator = self._get_locator(selector, selector_type)
        return await locator.inner_text()

    async def get_accessibility_tree(self) -> Dict:
        """获取无障碍树"""
        if not self._page:
            return {}

        try:
            snapshot = await self._page.accessibility.snapshot()
            return self._format_accessibility(snapshot)
        except Exception as e:
            logger.debug(f"无障碍树获取失败: {e}")
            return {}

    def _format_accessibility(self, snapshot: Dict, indent: int = 0) -> Dict:
        """格式化无障碍树"""
        if not snapshot:
            return {}

        result = {
            "role": snapshot.get("role", ""),
            "name": snapshot.get("name", ""),
        }

        children = []
        for child in snapshot.get("children", []):
            children.append(self._format_accessibility(child, indent + 1))

        if children:
            result["children"] = children

        return result

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

        locator = self._get_locator(selector, selector_type)

        try:
            await locator.wait_for(state=state, timeout=timeout)
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

    async def analyze_page(self) -> Dict:
        """分析页面"""
        tree = await self.get_accessibility_tree()
        screenshot = await self.screenshot()

        return {
            "url": self._page.url if self._page else "",
            "title": await self._page.title() if self._page else "",
            "accessibility_tree": tree,
            "has_form": "form" in str(tree).lower(),
            "clickable_count": str(tree).lower().count("button"),
            "links": str(tree).lower().count("link"),
            "screenshot_size": len(screenshot),
        }

    async def switch_page(self, page_id: str):
        """切换页面"""
        if page_id in self._pages:
            self._page = self._pages[page_id]
            self._current_page_id = page_id

    async def close_page(self, page_id: str = None):
        """关闭页面"""
        page_id = page_id or self._current_page_id

        if page_id in self._pages and page_id != "main":
            await self._pages[page_id].close()
            del self._pages[page_id]

            if self._pages:
                self._current_page_id = list(self._pages.keys())[0]
                self._page = self._pages[self._current_page_id]

    async def go_back(self):
        """后退"""
        if self._page:
            await self._page.go_back()

    async def go_forward(self):
        """前进"""
        if self._page:
            await self._page.go_forward()

    async def reload(self):
        """刷新"""
        if self._page:
            await self._page.reload()

    async def close(self):
        """关闭浏览器"""
        for page in list(self._pages.values()):
            try:
                await page.close()
            except Exception:
                pass

        if self._context:
            await self._context.close()

        if self._browser:
            await self._browser.close()

        if self._playwright:
            await self._playwright.stop()

        self._initialized = False
        self._pages.clear()

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def current_page(self) -> Optional[PageInfo]:
        if not self._page:
            return None
        return PageInfo(
            url=self._page.url,
            title=self._page.title() if hasattr(self._page, 'title') else "",
            viewport_size=self.viewport
        )
