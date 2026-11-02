"""
使用 Playwright 调用浏览器进行 Bing 搜索并获取搜索结果
"""

from asyncio import wait_for
from contextlib import asynccontextmanager

from playwright.async_api import Page, async_playwright
from trafilatura import extract

from ...logger import get_logger

logger = get_logger()


async def _close_quietly(browser, context) -> None:
    """
    尽最大努力关闭 context / browser
    """
    for obj in (context, browser):
        if obj is None:
            continue
        try:
            await wait_for(obj.close(), timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.warning("Close context failed, %s", e)


@asynccontextmanager
async def browser_page(headless: bool = True):
    """
    打开一个已注入反检测脚本的 page，退出时保证关闭浏览器。

    用法::

        async with browser_page(headless=True, user_agent=UA) as page:
            await page.goto(...)
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = None
        try:
            options = {
                "viewport": {"width": 1280, "height": 800},
                "locale": "zh-CN",
            }
            options["user_agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            context = await browser.new_context(**options)
            page = await context.new_page()
            await page.add_init_script(path="agibot/agent/tool/playwright_init.js")
            yield page
        finally:
            # 无论成功/超时/异常，都确保浏览器被关闭
            await _close_quietly(browser, context)


async def parse_bing_results(page: Page, max_results: int) -> list[dict[str, str]]:
    """
    从已加载的 Bing 结果页解析标题、链接和摘要。
    """
    results: list[dict[str, str]] = []
    items = await page.query_selector_all("li.b_algo")
    for item in items:
        if len(results) >= max_results:
            break
        # 标题和链接
        link_el = await item.query_selector("h2 a")
        if not link_el:
            continue
        title = (await link_el.inner_text()).strip()
        url = await link_el.get_attribute("href")
        # 摘要
        snippet_el = await item.query_selector(".b_caption p, .b_algoSlug, p")
        snippet = (await snippet_el.inner_text()).strip() if snippet_el else ""
        if title and url:
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


async def run_bing_search(
    page: Page, keyword: str, max_results: int
) -> list[dict[str, str]]:
    """
    在给定 page 上执行 Bing 搜索并返回解析结果。
    """
    await page.goto("https://www.bing.com", wait_until="domcontentloaded")
    # Bing 搜索框 id 通常为 #sb_form_q
    await page.fill("#sb_form_q", keyword)
    await page.press("#sb_form_q", "Enter")
    # 等待搜索结果加载
    await page.wait_for_selector("li.b_algo", timeout=15000)
    return await parse_bing_results(page, max_results)


async def fetch_page_content(page: Page, url: str) -> str:
    """
    在给定 page 上访问 url，返回正文提取结果。
    """
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    content = await page.content()
    return extract(content) or ""


async def search_bing(
    keyword: str, max_results: int = 10, headless: bool = True
) -> list[dict[str, str]]:
    """
    在 Bing 上搜索关键字并返回搜索结果

    Args:
        keyword: 搜索关键字
        max_results: 最多返回的结果数
        headless: 是否使用无头模式（True 不显示浏览器界面）

    Returns:
        搜索结果列表，每项包含 title, url, snippet
    """
    async with browser_page(headless=headless) as page:
        return await run_bing_search(page, keyword, max_results)


async def surf_web(url: str, headless: bool = True) -> str:
    """
    访问网页并返回网页的主要内容

    Args:
        url: 需要访问的 url
        headless: 是否使用无头模式（True 不显示浏览器界面）
    """
    async with browser_page(headless=headless) as page:
        return await fetch_page_content(page, url)
