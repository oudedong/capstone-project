import sys
from collections import deque
from typing import Callable

from .browser_session import Playwright_mn, wait_dom_stable, is_interactable
from .html_cleaner import recursive_iframe_replace, clean_html

from abc import ABC, abstractmethod

# ── 페이지 가져오기 ────────────────────────────────────────────────────────────

async def request_to_user(session_path: str, request_url: str) -> str:
    """
    처리하기 힘든 URL(로그인 페이지 등)에 대해 사용자가 직접 브라우저에서 처리하도록 열어줍니다.
    처리 결과를 세션에 저장합니다.
    """
    context = await Playwright_mn.create(session_path, False)
    # context, browser, playwright = await get_shared_context(headless=False)
    page = await context.new_page()
    await page.goto(request_url)

    try:
        await page.wait_for_event("close", timeout=300000)
        await context.storage_state(path=session_path)
        return "세션 저장 완료"
    except Exception as e:
        print(f"시간 초과 또는 오류 발생: {e}")
        raise
    finally:
        await context.close()

class RedirectError(Exception):
    def __init__(self, intended_url, current_url, current_page_title):
        self.intended_url = intended_url
        self.current_url = current_url
        self.current_page_title = current_page_title
    def __str__(self):
        return f"의도한 페이지로 이동되지 않았습니다. 의도한 페이지:{self.intended_url}, 현재 페이지제목:{self.current_page_title}, 현재url:{self.current_url}"


async def _fetch_page(session_path: str, url: str,
                      content_extractor: Callable,
                      post_process: Callable[[str], str]) -> dict:
    """웹페이지를 열고 내용을 추출한 뒤 후처리하여 JSON으로 반환합니다."""
    context = await Playwright_mn.create(session_path, True)
    # context, browser, playwright = await get_shared_context()
    page = await context.new_page()
    response = None

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=0)
        await page.wait_for_load_state("networkidle", timeout=30000)

        content = await content_extractor(page.main_frame)
        content = post_process(content)

        result = {
            "current_url": page.url,
            "current_page_title": await page.title(),
            "content": content,
            "intended_url": url,
            "is_intended_url": url == page.url,
        }
        if not result['is_intended_url']:
            # 의도한 페이지로 안 가졌을시 예외발생..(로그인 리다이렉션 등등...)
            raise RedirectError(result['intended_url'], result['current_url'], result['current_page_title'])
        return result
    except RedirectError as re:
        raise
    except Exception as e:
        status_code = response.status if response else "Unknown"
        return f"페이지 로드 실패, status:{status_code}, 에러내용: {str(e)}"
    finally:
        await context.close()

async def get_page(session_path: str, url: str) -> str:
    """URL 페이지를 가져와 HTML을 후처리하고 JSON으로 반환합니다."""
    async def _content_extractor(frame):
        return await recursive_iframe_replace(frame)

    return await _fetch_page(session_path, url, _content_extractor, clean_html)


# ── URL 수집 (클릭 탐색) ───────────────────────────────────────────────────────

# 클릭 대상 요소를 뽑아주는 JS 설명자
_DESCRIBE_JS = """
el => ({
    tag: el.tagName,
    text: el.innerText.trim(),
})
"""

async def _tag_extractor(frame):
    """프레임에서 클릭 가능한 후보 요소들을 뽑아줍니다 (로그아웃 등 위험 요소 제외)."""
    forbidden_keywords = [
        "로그아웃", "logout", "signout", "exit", "나가기",
        "비밀번호 변경", "회원탈퇴", "delete account"
    ]
    selectors = ["a", "li", "span", "div"]
    selector_str = ", ".join(selectors)

    await frame.evaluate(f"""(args) => {{
        const {{ sel, keywords }} = args;
        const elements = document.querySelectorAll(sel);
        elements.forEach(el => {{
            const text = el.innerText.toLowerCase();
            const href = el.getAttribute('href') || "";
            const isForbidden = keywords.some(k => text.includes(k) || href.toLowerCase().includes(k));
            if (isForbidden) return;
            const hasDirectText = Array.from(el.childNodes).some(node =>
                node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0
            );
            if (hasDirectText) {{
                el.classList.add('mcp-clickable-target');
            }}
        }});
    }}""", {"sel": selector_str, "keywords": forbidden_keywords})

    return frame.locator(".mcp-clickable-target").filter(visible=True)


async def _recursive_dynamic_click(
        init_url: str, page, frame_index: int, tag_extractor,
        global_visited,
        init_click_elements_nths: list[int] = None,
        new_elements_nths: list[int] = None) -> list[dict]:
    """
    프레임에서 클릭 가능한 요소들을 모두 클릭해보며 이동되는 URL을 수집합니다.
    동적으로 생성되는 요소(드롭다운 등)도 재귀적으로 탐색합니다.
    """
    if init_click_elements_nths is None:
        init_click_elements_nths = []

    async def restore_locator():
        target_frame = page.frames[frame_index]
        return await tag_extractor(target_frame)

    async def restore_state():
        await page.goto(init_url, wait_until="domcontentloaded")
        for nth in init_click_elements_nths:
            await wait_dom_stable(page)
            target_frame = page.frames[frame_index]
            locators = await tag_extractor(target_frame)
            await locators.nth(nth).click(timeout=5000) # ?
        await wait_dom_stable(page)
        target_frame = page.frames[frame_index]
        return await tag_extractor(target_frame)

    rets = []
    locators = await restore_state()
    count = await locators.count()

    before_elems_html = [
        await locators.nth(j).evaluate(_DESCRIBE_JS)
        for j in range(count)
    ]

    targets_to_click = new_elements_nths if new_elements_nths is not None else range(count)

    for i in targets_to_click:
        target_html = None
        try:
            locators = await restore_locator()
            target = locators.nth(i)
            target_html = await target.evaluate(_DESCRIBE_JS, timeout=5000)

            if not await is_interactable(target):
                continue

            print(f"[*] 클릭 시도: {target_html}", file=sys.stderr)
            await target.click(timeout=5000)
            await wait_dom_stable(page)

            after_url = page.url
            print(f"[*] 이동된 url: {after_url}", file=sys.stderr)

            if after_url != init_url:
                if after_url not in global_visited:
                    title = await page.title()
                    ret = {"url": after_url, "title": title.strip()}
                    rets.append(ret)
                    global_visited.add(ret)
                locators = await restore_state()
                continue

            # 클릭 후 새로 생긴 요소 탐색
            locators = await restore_locator() # 무조건 필수!!! 클릭 후 locator 상태 갱신!!!!!
            after_count = await locators.count()
            new_indices = []
            for k in range(after_count):
                html = await locators.nth(k).evaluate(_DESCRIBE_JS)
                if html not in before_elems_html:
                    print(f"[!] 새로운 요소 발견: {html}", file=sys.stderr)
                    new_indices.append(k)

            if new_indices:
                next_path = init_click_elements_nths + [i]
                rets += await _recursive_dynamic_click(
                    init_url, page, frame_index, tag_extractor,
                    global_visited, next_path, new_indices
                )
                locators = await restore_state()

        except Exception as e:
            # import traceback
            # traceback.print_exc(file=sys.stderr)
            print(f"클릭 실패\n요소:{target_html}\n오류내용:{e}", file=sys.stderr)
            continue

    return rets


async def get_sub_urls_by_click(session_path:str, url: str, visited, depth: int = 1) -> list[dict]:
    """
    페이지에서 클릭 가능한 요소들을 탐색하여 이동되는 URL들을 수집합니다.
    iframe 내부도 탐색하며, depth만큼 재귀적으로 수집합니다.
    """
    context = await Playwright_mn.create(session_path, False)
    # context, browser, playwright = await get_shared_context(headless=False)
    page = await context.new_page()

    queue = deque([(url, 0)])
    visited.add({"url": url, "title": None})
    rets = []

    try:
        while queue:
            cur_url, cur_depth = queue.popleft()
            if depth > 0 and cur_depth >= depth:
                continue
            
            await page.goto(cur_url, wait_until="domcontentloaded", timeout=0)
            await page.wait_for_load_state("networkidle", timeout=5000)

            for i in range(len(page.frames)):
                try:
                    frame_rets = await _recursive_dynamic_click(
                        cur_url, page, i, _tag_extractor, visited
                    )
                    for ret in frame_rets:
                        rets.append(ret)
                        queue.append((ret['url'], cur_depth + 1))
                except Exception as e:
                    print(f"url:{cur_url}, e:{str(e)}", file=sys.stderr)
                    continue
    finally:
        await context.close()

    return rets

class Global_visit_page_url(ABC):
    """방문집합 형식"""
    @abstractmethod
    def __contains__(self, url:str) -> bool:
        """집합에 대해 in연산"""
        pass
    def add(self, data:dict) -> str:
        """집합 추가 연산"""
        pass
class Global_visit_set_page_url(Global_visit_page_url):
    """set을 이용한 방문집합, 디버깅용"""
    def __init__(self):
        self.set = set()
    def __contains__(self, url:str) -> bool:
        return url in self.set
    def add(self, data:dict) -> str:
        self.set.add(data['url'])

async def get_sub_urls_by_click_set(session_path:str, url: str, depth: int = 1) -> list[dict]:
    """
    방문처리를 set를 이용하는 get_sub_urls_by_click
    """
    return await get_sub_urls_by_click(session_path, url, Global_visit_set_page_url(), depth)