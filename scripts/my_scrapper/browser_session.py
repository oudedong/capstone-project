import asyncio
import time
from playwright.async_api import async_playwright
import sys

async def get_shared_context(headless: bool, session_path: str = None):
    """Playwright context와 browser 인스턴스를 반환합니다."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)

    # 세션 파일이 존재하나 확인
    if session_path is not None:
        try:
            with open(session_path, "rb") as f: pass
        except FileNotFoundError as e:
            session_path = None

    context = await browser.new_context(
        storage_state=session_path,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )
    return context, browser, playwright


class Playwright_mn:
    def __init__(self, playwright, browser, context, session_path:str):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.session_path = session_path
        self.page = None
    @classmethod
    async def create(cls, session_path, headless:bool = True):
        context,browser,playwright = await get_shared_context(headless, session_path)
        return cls(playwright, browser, context, session_path)
    async def reload_state(self): # 세션 새로고침!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        if self.context:
            await self.context.close()
            self.page = None # page도 닫히므로 비워줌
        self.context = await self.browser.new_context(
            storage_state=self.session_path,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
    async def new_page(self):
        if self.page:
            # 있다면 제거
            await self.page.close()
        self.page = await self.context.new_page()
        return self.page
    async def get_page(self):
        if not self.page:
            # 없다면 생성
            await self.new_page()
        return self.page
    async def storage_state(self):
        return await self.context.storage_state(path=self.session_path)
    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()



async def wait_dom_stable(page, timeout: int = 5000, stable_ms: int = 500):
    """DOM 내용과 아이프레임 개수가 모두 멈출 때까지 대기합니다."""
    try:
        await page.wait_for_load_state("load", timeout=2000)
    except Exception:
        pass

    start_time = time.time()
    last_html = ""
    last_frame_count = -1
    stable_start = None

    while True:
        gap = (time.time() - start_time) * 1000
        if gap > timeout:
            print("[!] wait_dom_stable: 시간 초과 (현재 상태로 진행)", file=sys.stderr)
            return

        try:
            current_html = await page.content()
            current_frame_count = len(page.frames)

            # 1. 메인 HTML 내용과 프레임 개수가 '모두' 이전 루프와 똑같은지 확인
            if current_html == last_html and current_frame_count == last_frame_count:
                if stable_start is None:
                    stable_start = time.time()
                
                # 2. 지정된 시간(예: 500ms) 동안 변화가 없었다면 조건 충족
                if (time.time() - stable_start) * 1000 >= stable_ms:
                    # 마지막으로 안전하게 생성된 모든 프레임의 로딩 상태가 끝났는지 체크
                    frame_tasks = [
                        f.wait_for_load_state("load", timeout=1000) 
                        for f in page.frames if not f.is_detached()
                    ]
                    if frame_tasks:
                        await asyncio.gather(*frame_tasks, return_exceptions=True)
                    return  # 완전히 안정화됨
            else:
                # 변화가 생겼다면 타이머를 초기화하고 최신 상태를 기록
                stable_start = None
                last_html = current_html
                last_frame_count = current_frame_count

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
