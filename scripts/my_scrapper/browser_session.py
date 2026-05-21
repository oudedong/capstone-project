import asyncio
import time
from playwright.async_api import async_playwright

async def get_shared_context(headless: bool, session_path: str = None):
    """Playwright context와 browser 인스턴스를 반환합니다."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)

    context = await browser.new_context(
        storage_state=session_path,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
    return context, browser, playwright


class Playwright_mn:
    def __init__(self, playwright, browser, context):
        self.playwright = playwright
        self.browser = browser
        self.context = context
    @classmethod
    async def create(cls, session_path, headless:bool = True):
        context,browser,playwright = await get_shared_context(headless, session_path)
        return cls(playwright, browser, context)
    async def new_page(self):
        return await self.context.new_page()
    async def storage_state(self):
        return self.context.storage_state(path=self.session_path)
    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()



async def wait_dom_stable(page, timeout: int = 5000, stable_ms: int = 500):
    """DOM 변화가 멈출 때까지 대기합니다."""
    try:
        await page.wait_for_load_state("load", timeout=2000)
    except Exception:
        pass  # 타임아웃이 나도 아래 루프에서 한 번 더 검증

    start = time.time()
    last_html = ""
    stable_start = None

    while True:
        gap = (time.time() - start) * 1000
        try:
            if gap > timeout:
                raise Exception("wait_dom_stable: 시간 초과")
            html = await page.content()

            if html == last_html:
                if stable_start is None:
                    stable_start = time.time()
                if (time.time() - stable_start) * 1000 >= stable_ms:
                    return  # 안정화 완료
            else:
                stable_start = None
                last_html = html

        except Exception:
            await asyncio.sleep(0.2)
            continue

        await asyncio.sleep(0.1)


async def is_interactable(locator) -> bool:
    """요소가 화면에 실제로 보이는 크기를 가지는지 확인합니다."""
    try:
        box = await locator.bounding_box()
        if box is None:
            return False
        return box["width"] >= 3 and box["height"] >= 3
    except Exception:
        return False
