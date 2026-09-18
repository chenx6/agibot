"""
使用 Playwright 调用浏览器进行 Bing 搜索并获取搜索结果
"""

from playwright.async_api import async_playwright
from trafilatura import extract


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
    results: list[dict[str, str]] = []

    async with async_playwright() as p:
        # 启动 Chromium 浏览器
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled"
            ],  # 减少被识别为爬虫的概率
        )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = await context.new_page()

        # 访问 Bing
        await page.goto("https://www.bing.com", wait_until="domcontentloaded")

        # 在搜索框输入关键字并回车
        # Bing 搜索框 id 通常为 #sb_form_q
        await page.fill("#sb_form_q", keyword)
        await page.press("#sb_form_q", "Enter")

        # 等待搜索结果加载
        await page.wait_for_selector("li.b_algo", timeout=15000)

        # 提取搜索结果
        # Bing 结果项通常在 li.b_algo 中，包含 h2 > a 和摘要
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
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    }
                )

        await context.close()
        await browser.close()

    return results


async def surf_web(url: str):
    """
    访问网页并返回网页的主要内容

    Args:
        url: 需要访问的 url
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60)
        content = await page.content()
        return extract(content)
