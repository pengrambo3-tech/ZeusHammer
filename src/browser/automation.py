"""
ZeusHammer Browser Automation

Fuses OpenClaw's browser automation with Hermes' Playwright integration.

Features:
1. Multi-provider support (Playwright, Selenium, remote)
2. Element interaction
3. Screenshot and accessibility tree
4. Browser context management
5. Proxy and stealth mode
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class BrowserProvider(Enum):
    """Browser automation providers"""
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    REMOTE = "remote"  # Remote WebDriver


@dataclass
class BrowserConfig:
    """Browser configuration"""
    provider: BrowserProvider = BrowserProvider.PLAYWRIGHT
    headless: bool = True
    viewport: tuple = (1280, 720)
    user_agent: str = ""
    proxy: str = ""  # HTTP proxy
    stealth: bool = False  # Anti-detection mode

    # Playwright specific
    slow_mo: int = 0  # Slow down operations (ms)
    downloads_path: str = ""

    # Authentication
    storage_state: str = ""  # Path to storage state for auth


@dataclass
class BrowserElement:
    """Browser element representation"""
    selector: str
    selector_type: str  # css, xpath, text, role
    tag: str = ""
    text: str = ""
    visible: bool = True
    enabled: bool = True
    rect: Dict[str, int] = field(default_factory=dict)


@dataclass
class BrowserPage:
    """Browser page context"""
    url: str
    title: str = ""
    elements: List[BrowserElement] = field(default_factory=list)
    accessibility_tree: str = ""


class PlaywrightBrowser:
    """
    Playwright browser automation.

    Full-featured browser control with:
    - Element selection and interaction
    - Screenshot and PDF
    - Network interception
    - File downloads
    - Multiple contexts
    """

    def __init__(self, config: BrowserConfig):
        self.config = config
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def initialize(self) -> bool:
        """Initialize Playwright"""
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            # Launch browser
            launch_options = {
                "headless": self.config.headless,
                "slow_mo": self.config.slow_mo,
            }

            if self.config.user_agent:
                launch_options["user_agent"] = self.config.user_agent

            if self.config.proxy:
                launch_options["proxy"] = {"http": self.config.proxy, "https": self.config.proxy}

            # Stealth mode (basic)
            if self.config.stealth:
                launch_options["ignore_default_args"] = [
                    "--enable-blink-features=AutomationControlled"
                ]

            self._browser = await self._playwright.chromium.launch(**launch_options)

            # Create context
            context_options = {}
            if self.config.viewport:
                context_options["viewport"] = {
                    "width": self.config.viewport[0],
                    "height": self.config.viewport[1]
                }

            if self.config.storage_state:
                context_options["storage_state"] = self.config.storage_state

            self._context = await self._browser.new_context(**context_options)

            # Create page
            self._page = await self._context.new_page()

            logger.info("Playwright browser initialized")
            return True

        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install")
            return False
        except Exception as e:
            logger.error(f"Browser initialization failed: {e}")
            return False

    async def navigate(self, url: str, wait_until: str = "load") -> Dict[str, Any]:
        """Navigate to URL"""
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

    async def click(self, selector: str, selector_type: str = "css") -> bool:
        """Click element"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.click()
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    async def fill(self, selector: str, text: str, selector_type: str = "css") -> bool:
        """Fill input field"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.fill(text)
            return True
        except Exception as e:
            logger.error(f"Fill failed: {e}")
            return False

    async def select(self, selector: str, value: str, selector_type: str = "css") -> bool:
        """Select option in dropdown"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.select_option(value)
            return True
        except Exception as e:
            logger.error(f"Select failed: {e}")
            return False

    async def hover(self, selector: str, selector_type: str = "css") -> bool:
        """Hover over element"""
        if not self._page:
            return False

        try:
            locator = self._get_locator(selector, selector_type)
            await locator.hover()
            return True
        except Exception as e:
            logger.error(f"Hover failed: {e}")
            return False

    async def screenshot(self, path: str = "", full_page: bool = False) -> Optional[bytes]:
        """Take screenshot"""
        if not self._page:
            return None

        try:
            if path:
                await self._page.screenshot(path=path, full_page=full_page)
                return b""
            else:
                return await self._page.screenshot(full_page=full_page)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def get_accessibility_tree(self) -> str:
        """Get accessibility tree for AI understanding"""
        if not self._page:
            return ""

        try:
            snapshot = await self._page.accessibility.snapshot()
            return self._format_accessibility_tree(snapshot)
        except Exception as e:
            logger.error(f"Accessibility tree failed: {e}")
            return ""

    def _get_locator(self, selector: str, selector_type: str):
        """Get Playwright locator based on selector type"""
        if selector_type == "xpath":
            return self._page.locator(f"xpath={selector}")
        elif selector_type == "text":
            return self._page.get_by_text(selector)
        elif selector_type == "role":
            return self._page.get_by_role(selector)
        else:
            return self._page.locator(selector)

    def _format_accessibility_tree(self, snapshot: Dict) -> str:
        """Format accessibility tree for readability"""
        if not snapshot:
            return ""

        lines = []

        def format_node(node: Dict, indent: int = 0):
            prefix = "  " * indent
            role = node.get("role", "")
            name = node.get("name", "")

            if name:
                lines.append(f"{prefix}[{role}] {name}")
            else:
                lines.append(f"{prefix}[{role}]")

            for child in node.get("children", []):
                format_node(child, indent + 1)

        format_node(snapshot)
        return "\n".join(lines)

    async def get_page_info(self) -> BrowserPage:
        """Get current page info"""
        if not self._page:
            return BrowserPage(url="", title="")

        return BrowserPage(
            url=self._page.url,
            title=await self._page.title(),
        )

    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> bool:
        """Wait for element to appear"""
        if not self._page:
            return False

        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def evaluate(self, script: str) -> Any:
        """Execute JavaScript"""
        if not self._page:
            return None

        try:
            return await self._page.evaluate(script)
        except Exception as e:
            logger.error(f"Evaluate failed: {e}")
            return None

    async def close(self):
        """Close browser"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

        logger.info("Browser closed")


class BrowserOrchestrator:
    """
    Browser automation orchestrator.

    Manages browser instances and provides unified interface.
    """

    def __init__(self):
        self._browsers: Dict[str, PlaywrightBrowser] = {}
        self._default_config = BrowserConfig()

    def set_default_config(self, config: BrowserConfig):
        """Set default browser configuration"""
        self._default_config = config

    async def create_browser(
        self,
        name: str = "default",
        config: BrowserConfig = None,
        storage_state: str = ""
    ) -> bool:
        """Create a new browser instance"""
        config = config or self._default_config

        if storage_state:
            config.storage_state = storage_state

        browser = PlaywrightBrowser(config)

        if await browser.initialize():
            self._browsers[name] = browser
            return True

        return False

    def get_browser(self, name: str = "default") -> Optional[PlaywrightBrowser]:
        """Get browser instance"""
        return self._browsers.get(name)

    async def close_browser(self, name: str = "default"):
        """Close browser instance"""
        browser = self._browsers.get(name)
        if browser:
            await browser.close()
            del self._browsers[name]

    async def close_all(self):
        """Close all browsers"""
        for browser in list(self._browsers.values()):
            await browser.close()
        self._browsers.clear()

    # Convenience methods

    async def goto(self, url: str, browser_name: str = "default") -> Dict[str, Any]:
        """Navigate to URL"""
        browser = self.get_browser(browser_name)
        if not browser:
            return {"success": False, "error": "Browser not found"}
        return await browser.navigate(url)

    async def click(self, selector: str, browser_name: str = "default") -> bool:
        """Click element"""
        browser = self.get_browser(browser_name)
        if not browser:
            return False
        return await browser.click(selector)

    async def fill(self, selector: str, text: str, browser_name: str = "default") -> bool:
        """Fill input"""
        browser = self.get_browser(browser_name)
        if not browser:
            return False
        return await browser.fill(selector, text)

    async def screenshot(self, path: str = "", browser_name: str = "default") -> Optional[bytes]:
        """Take screenshot"""
        browser = self.get_browser(browser_name)
        if not browser:
            return None
        return await browser.screenshot(path)

    async def get_tree(self, browser_name: str = "default") -> str:
        """Get accessibility tree"""
        browser = self.get_browser(browser_name)
        if not browser:
            return ""
        return await browser.get_accessibility_tree()


# Global orchestrator
_orchestrator: Optional[BrowserOrchestrator] = None


def get_browser_orchestrator() -> BrowserOrchestrator:
    """Get global browser orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = BrowserOrchestrator()
    return _orchestrator
