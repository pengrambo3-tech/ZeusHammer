"""
ZeusHammer 浏览器控制

真实集成Hermes的Playwright浏览器控制。
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RealBrowser:
    """
    真实浏览器控制器

    使用Playwright进行真实的浏览器自动化。
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._page = None
        self._playwright = None

    async def initialize(self):
        """初始化Playwright"""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless
            )
            self._page = await self._browser.new_page()
            logger.info("Playwright浏览器初始化成功")
            return True
        except ImportError:
            logger.error("请安装playwright: pip install playwright && playwright install")
            return False
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            return False

    async def navigate(self, url: str) -> Dict[str, Any]:
        """导航到URL"""
        if not self._page:
            return {"success": False, "error": "浏览器未初始化"}

        try:
            await self._page.goto(url, wait_until="load")
            return {
                "success": True,
                "url": url,
                "title": await self._page.title()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self) -> bytes:
        """截图"""
        if self._page:
            return await self._page.screenshot()
        return b""

    async def find_element(self, selector: str) -> Optional[Dict]:
        """查找元素"""
        if not self._page:
            return None

        try:
            element = await self._page.query_selector(selector)
            if element:
                return {
                    "tag": await element.evaluate("el => el.tagName"),
                    "text": await element.text_content(),
                    "visible": await element.is_visible()
                }
        except Exception:
            pass
        return None

    async def click(self, selector: str):
        """点击元素"""
        if self._page:
            await self._page.click(selector)

    async def fill(self, selector: str, text: str):
        """填写表单"""
        if self._page:
            await self._page.fill(selector, text)

    async def get_dom(self) -> str:
        """获取DOM"""
        if self._page:
            return await self._page.content()
        return ""

    async def close(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


class FallbackBrowser:
    """
    回退浏览器 - 当Playwright不可用时使用

    尝试调用系统默认浏览器。
    """

    def __init__(self):
        self._url = None

    async def initialize(self):
        logger.info("使用回退浏览器")
        return True

    async def navigate(self, url: str) -> Dict[str, Any]:
        import subprocess
        import platform

        self._url = url
        system = platform.system()

        try:
            if system == "Darwin":
                subprocess.run(["open", url])
            elif system == "Linux":
                subprocess.run(["xdg-open", url])
            elif system == "Windows":
                subprocess.run(["start", url], shell=True)
            return {"success": True, "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close(self):
        pass


async def create_browser(headless: bool = True):
    """创建浏览器实例"""
    browser = RealBrowser(headless)
    if await browser.initialize():
        return browser
    return FallbackBrowser()