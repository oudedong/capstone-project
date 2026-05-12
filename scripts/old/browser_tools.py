import os
import json
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Comment
from typing import Callable
import re
import time
import asyncio

# 환경 변수 로드
load_dotenv()
mcp = FastMCP("browser_tools")


##########################################################################
#세션
SESSION_FILE = Path("./.gemini/session.json")
if os.path.exists(SESSION_FILE):
    # os.remove(SESSION_FILE)
    pass
##########################################################################

async def get_shared_context(headless=True):
    """
    context, 브라우저를 반환해줌
    """
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=headless  # 디버깅 시에 False!(화면을 실시간으로 보여줌)
    )
    storage_state = str(SESSION_FILE) if SESSION_FILE.exists() else None

    context = await browser.new_context(
        storage_state=storage_state,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    )

    return context, browser

async def wait_dom_stable(page, timeout=5000, stable_ms=500):
    # 1. 일단 기본적인 로딩 상태는 짧게 기다림
    try:
        # networkidle은 무거우니 'load' 정도만 기다려도 충분할 때가 많습니다.
        await page.wait_for_load_state("load", timeout=2000)
    except:
        pass # 타임아웃 나도 아래 루프에서 한 번 더 검증하니 괜찮음

    # 2. 실제 데이터가 다 그려졌는지 '내용의 변화'로 체크 (현수님 로직)
    start = time.time()
    last_html = ""
    stable_start = None

    while True:
        gap = (time.time() - start) * 1000
        try:
            # 시간초과시 예외발생
            if gap > timeout:
                raise Exception("wait_dom_stable.시간초과")
            # evaluate 대신 page.content()를 쓰되 에러 시 continue
            html = await page.content() 
            
            if html == last_html:
                if stable_start is None: stable_start = time.time()
                if (time.time() - stable_start) * 1000 >= stable_ms:
                    return # 진짜 안정화됨
            else:
                stable_start = None
                last_html = html
                
        except:
            # 네비게이션 중이면 잠시 대기
            await asyncio.sleep(0.2)
            continue
            
        await asyncio.sleep(0.1)
# async def wait_dom_stable(page, timeout=5000, stable_ms=500):
#     # dom에 변화가 없을때 까지 기다림
#     start = time.time()
#     last_html = ""
#     stable_start = None

#     await page.wait_for_load_state("domcontentloaded", timeout=3000)
#     await page.wait_for_load_state("networkidle", timeout=5000)

#     while True:
#         html = await page.content()

#         if html == last_html:
#             if stable_start is None:
#                 stable_start = time.time()

#             elapsed = (time.time() - stable_start) * 1000
#             if elapsed >= stable_ms:
#                 return
#         else:
#             stable_start = None
#             last_html = html

#         if (time.time() - start) * 1000 > timeout:
#             return

#         await page.wait_for_timeout(100)
async def is_interactable(locator):
    #요소가 눈에 보이나 확인함
    try:
        box = await locator.bounding_box()

        if box is None:
            return False

        if box["width"] < 3 or box["height"] < 3:
            return False

        return True

    except:
        return False

###########################################################################################


@mcp.tool()
async def request_to_user(request_url:str)->str:
    """
    처리하기 힘든 특정url에(로그인 페이지 등등...) 대해 사용자에게 처리를 요청함, 그러면 사용자가 브라우저에서 직접 처리함
    처리결과를 세션에 저장함

    Args:
        request_url: 사용자에게 요청할 url
    Return:
        content: 페이지내용
        intented_url: 처음에 접근하려한 페이지
        current_url: 현재 실제페이지
        is_intended_url: 의도한 페이지로 접근했는지
        current_page_title: 현재페이지의 제목
    """

    context, browser = await get_shared_context(False)
    page = await context.new_page()

    # 페이지 접속
    await page.goto(request_url)

    try:
        # 창 닫을때까지 대기
        await page.wait_for_event("close")
        # 세션 저장
        await context.storage_state(path=SESSION_FILE)
        return "세션 저장 완료"

    except Exception as e:
        return f"시간 초과 또는 오류 발생: {e}"
        
    finally:
        await browser.close()
def replace_content_first(content:str, replace_content:str, tag:str)->str:
    # content에서 첫번쨰로 찾은요소를 replace_content요소로 교체합니다
    soup = BeautifulSoup(content, 'html.parser')
    
    # 요소 검색
    iframe_tag = soup.find(tag)
    if iframe_tag == None:
        raise Exception("일치하는 요소가 아예없습니다")
    
    #content에서 찾은요소를 replace_content로 교체함
    new_container = soup.new_tag("div", attrs={"class": "merged-iframe"})
    new_container.append(BeautifulSoup(replace_content, 'html.parser'))
    iframe_tag.replace_with(new_container)
            
    return str(soup)
async def recursive_iframe_replace(root) -> str:
    #재귀적으로 iframe요소를 찾아, 내용으로 치환합니다
    child_iframes = root.child_frames
    content = await root.content()
    
    for iframe in child_iframes:
        #이후에 떨어진 요소는 스킵!!!!!!(매우중요)
        if iframe.is_detached():
            continue
        content = replace_content_first(content, await recursive_iframe_replace(iframe), 'iframe')
    return content
def clean_html_content_remove_tags(html_content: str) -> str:
    # 필요없는 태그들을 제거함
    soup = BeautifulSoup(html_content, 'html.parser')
    # 0. 주석 제거
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()
    # 1. 불필요한 태그들 한꺼번에 날려버리기
    unwanted_tags = [
        'script', 'style', 'meta', 'link', 'noscript', 
        'header', 'footer', 'svg', 
        'input', 'button', 'form', 'select', 'textarea'
    ]
    for tag in soup.find_all(unwanted_tags):
        tag.decompose()
    # 2. 중첩된 head 태그들 전부 삭제
    for head in soup.find_all('head'):
        head.decompose()
    # 3. 불필요한 속성(id, class 등)삭제, 허용된 속성만 남김
        allowed_attrs = ['href',]
        for tag in soup.find_all(True):
            new_attrs ={}
            for attr in tag.attrs.keys():
                if attr not in allowed_attrs:
                    continue
                new_attrs[attr] = tag.attrs[attr]
            tag.attrs = new_attrs
    # 4. 최상위 body만 찾아서 그 내용물만 반환
    if soup.body:
        return soup.body.decode_contents().strip() #decode_contents하면 html,body태그는 때줌, 깔끔함
    return str(soup).strip()
def clean_html_content_remove_empty_tags(html_content: str) -> str:
    # 내용을 가지지 않는(텍스트가 x) 태그들을 제거함
    soup = BeautifulSoup(html_content, 'html.parser')
    while True:
        removed_in_this_pass = False
        # 모든 태그를 뒤에서부터 훑습니다 (앞에서부터 지우면 인덱스가 꼬일 수 있음)
        for tag in soup.find_all():
            # 1. 태그 내부에 텍스트가 없고 (공백 제외)
            # 2. 자식 태그도 없다면 삭제
            if not tag.get_text(strip=True) and not tag.find_all():
                tag.decompose()
                removed_in_this_pass = True
        
        # 더 이상 지울 게 없으면 루프 종료
        if not removed_in_this_pass:
            break
    return str(soup).strip()

def clean_html_content_remove_gap(html_content: str) -> str:
    # 1. 탭(\t)과 캐리지 리턴(\r)을 일반 공백(' ')으로 변환 (단어 붙음 방지)
    html_content = re.sub(r'[\t\r]', ' ', html_content)
    # 2. 연속된 공백(2개 이상)을 딱 하나로 축소
    html_content = re.sub(r' +', ' ', html_content)
    # 3. 너무 많은 줄바꿈(3개 이상)을 최대 2개로 축소 (가독성 유지하며 공간 절약) 참고로 \s는 공백문자를 의미함!
    html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)
    # 4. 각 줄의 앞뒤에 붙은 의미 없는 공백 제거
    lines = [line.strip() for line in html_content.split('\n')]
    # 5. 빈 줄이 너무 많아지지 않게 다시 합치기
    return '\n'.join(line for line in lines if line).strip()
def _clean_html_content_series(html_content: str, cleaners:list[Callable[[str],str]]) -> str:
    # 여러 후처리를 묶어줌
    cleaned = html_content
    for cleaner in cleaners:
        cleaned = cleaner(cleaned)
    return cleaned
def clean_html_content_default(html_content: str) -> str:
    # 기본 후처리
    return _clean_html_content_series(
        html_content, 
        [
            clean_html_content_remove_tags,         #불필요 태그 제거
            clean_html_content_remove_empty_tags,   #껍데기,내용없는 태그 제거
            clean_html_content_remove_gap,          #공백제거
         ]
    )

async def _get_page(url: str, content_extractor: Callable[...,str], post_process: Callable[...,str]) -> str:
    # 웹페이지의 html내용을 가져옴
    context, browser = await get_shared_context()
    page = await context.new_page()
    response = None # 초기화하여 에러 발생 시 NameError 방지

    try:
        # 1. 페이지 이동
        response = await page.goto(url, wait_until="domcontentloaded", timeout=0)
        await page.wait_for_load_state("networkidle", timeout=30000)

        # 2. 내용 추출 및 후처리
        content = await content_extractor(page.main_frame)
        content = post_process(content)

        # 3. 결과 조립 (url은 속성, title은 메서드)
        result = {
            "current_url": page.url,                      # await 제거
            "current_page_title": await page.title(),     # () 추가
            "content": content,
            "intended_url": url,
            "is_intended_url": url == page.url,
        }
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        # response가 성공적으로 생성되었는지 확인 후 상태 코드 출력
        status_code = response.status if response else "Unknown"
        return f"페이지 로드 실패, status:{status_code}, 에러내용: {str(e)}"
    finally:
        await browser.close()
async def _get_page_with_iframe_content(url: str, post_process: Callable[...,str]) -> str:
    # iframe이 포함된 페이지를 가져올때 사용함, iframe의 내용을 본문의 iframe위치에 치환시켜줌 
    return await _get_page(url, recursive_iframe_replace, post_process)
async def _get_page_default(url: str, post_process: Callable[...,str]) -> str:
    # iframe이 없는 페이지를 가져올때 사용함
    async def _content_extractor(page):
        return await page.content()
    return await _get_page(url, _content_extractor, post_process)

@mcp.tool()
async def get_page(url: str) -> str:
    """
    url페이지를 가져와 html을 추출, 정보들을 json형태로 반환함

    Args:
        url: 페이지 url
    Returns:
        current_url: 현재페이지 url
        current_page_title: 현재페이지 제목
        content: 현재페이지 내용(html, 후처리됨: 불필요 태그,공백 제거)
        intended_url: 접근하려했던 url
        is_intended_url: 현재페이지가 접근하려했던 페이지인가?(로그인등의 이유로 리다이렉션 될 수 있음)
    """
    return await _get_page_with_iframe_content(url, clean_html_content_default)

from collections import deque

async def tag_extractor(frame):
    forbidden_keywords = [
        "로그아웃", "logout", "signout", "exit", "나가기", 
        "비밀번호 변경", "회원탈퇴", "delete account"
    ]
    
    # selector = ["a", "button", "li", "span", "div"]
    selectors = ["a", "li", "span", "div"]
    selector_str = ", ".join(selectors)
    
    # 2. JS를 주입할 때 필터링 조건을 강화합니다.
    await frame.evaluate(f"""(args) => {{
        const {{ sel, keywords }} = args;
        const elements = document.querySelectorAll(sel);
        
        elements.forEach(el => {{
            const text = el.innerText.toLowerCase();
            const href = el.getAttribute('href') || "";
            
            // 블랙리스트 키워드가 포함되어 있는지 검사
            const isForbidden = keywords.some(k => text.includes(k) || href.toLowerCase().includes(k));
            
            if (isForbidden) {{
                // 로그아웃 버튼 등은 무시하도록 클래스를 붙이지 않음
                return;
            }}

            const hasDirectText = Array.from(el.childNodes).some(node => 
                node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0
            );
            
            if (hasDirectText) {{
                el.classList.add('mcp-clickable-target');
            }}
        }});
    }}""", {"sel": selector_str, "keywords": forbidden_keywords})
    
    return frame.locator(".mcp-clickable-target").filter(visible=True)

describe = """
el => ({
    tag: el.tagName,
    text: el.innerText.trim(),
})
"""

async def recursive_dynamic_click(
        init_url: str, page, frame_index: int, tag_extractor, global_visited:set,
        init_click_elements_nths: list[int] = None, new_elements_nths: list[int] = None) -> list[dict]:
    """
    ...
    Args:
        init_url: 현재 프레임이 속한 url
        page: playwright페이지
        frame_index: 현재프레임의 인덱스
        tag_extractor: 프레임에서 클릭할 후보요소들을 뽑아줌, tag_extractor(page)
        global_visited: 재방문 방지용 집합
        init_click_elements_nths: 클릭하고 시작할 요소들(페이지에 변화를 일으키게)
        new_elements_nths: 클릭 했을때 새로생기는 요소들**** 처음엔 그냥 전부로!
    Return:
        list[dict{
            "url": 이동된 페이지의 url,
            "title": 이동된 페이지의 제목,
        }]
    """
    print(f"호출됨:\ninit_url:{init_url}\ninit_click_elements_nths:{init_click_elements_nths}\n,new_elements_nths:{new_elements_nths}", file=sys.stderr)
    async def restore_locator():
        target_frame = page.frames[frame_index]
        return await tag_extractor(target_frame)
    async def restore_state():
        # 페이지 url 및 클릭상태 복구
        # 복구 후 로케이터를 반환함!
        await page.goto(init_url, wait_until="domcontentloaded")
        for nth in init_click_elements_nths:
            await wait_dom_stable(page)
            target_frame = page.frames[frame_index]
            locators = await tag_extractor(target_frame)
            await locators.nth(nth).click()
        #마지막 클릭후에도 갱신!!!!!!
        await wait_dom_stable(page)
        target_frame = page.frames[frame_index]
        return await tag_extractor(target_frame)

    # 초기화
    if init_click_elements_nths is None: init_click_elements_nths = []
    if global_visited is None: global_visited = set()
    # if global_element is None: global_element = [] # 중복 클릭방지?? 페이지별로 누적시킴?, 이미본 요소들!!!!!, 여기이미 있으면 new_elements_nths에서 제외시킴
    rets = []

    # 상태 복구: 페이지로 이동 후 이전 클릭 경로 재현
    locators = await restore_state()
    count = await locators.count()
    
    # 클릭 전 요소들의 HTML 리스트 (비교군)
    before_elems_html = []
    for j in range(count):
        before_elems_html.append(await locators.nth(j).evaluate(describe))

    # 탐색할 인덱스 설정 (처음엔 전체, 재귀 시에는 새로 생긴 것만)
    targets_to_click = new_elements_nths if new_elements_nths is not None else range(count)

    for i in targets_to_click:
        try:
            # 타겟 찾기
            locators = await restore_locator()
            target = locators.nth(i)
            target_html = await target.evaluate(describe, timeout=5000)
            # 눈에 보이는 요소인지 확인
            if not await is_interactable(target):
                continue
            print(f"[*] 클릭 시도: {target_html}", file=sys.stderr)
            
            await target.click(timeout=5000)
            await wait_dom_stable(page)

            # URL 이동 여부 체크
            after_url = page.url
            print(f"[*] 이동된 url: {after_url}", file=sys.stderr)
            if after_url != init_url:
                if after_url not in global_visited: #하ㅏㅏㅏㅏㅏㅏ
                    title = await page.title()
                    rets.append({"url": after_url, "title": title.strip()})
                    global_visited.add(after_url)
                # 다시 원래 페이지로 이동 및 클릭상태 복구
                locators = await restore_state()
                continue # 아래는 안하도록!

            # 새로운 요소가 생겼는지 체크
            after_count = await locators.count()
            new_indices = []
            
            for k in range(after_count):
                html = await locators.nth(k).evaluate(describe)
                if html not in before_elems_html:
                    print(f"[!] 새로운 요소 {html} 발견", file=sys.stderr)
                    new_indices.append(k)

            # 새로운 요소가 발견되면 재귀 호출
            if len(new_indices) > 0:
                # if i not in init_click_elements_nths: #이상한 경우 방지... 함정(무한루프)
                #     next_path = init_click_elements_nths + [i]
                #     rets += await recursive_dynamic_click(
                #         init_url, page, frame_index, tag_extractor, global_visited, 
                #         next_path, new_indices
                #     )
                next_path = init_click_elements_nths + [i]
                rets += await recursive_dynamic_click(
                    init_url, page, frame_index, tag_extractor, global_visited, 
                    next_path, new_indices
                )
                # 다시 원래 페이지로 이동 및 클릭상태 복구
                locators = await restore_state()

        except Exception as e:
            # ----디버깅용----
            print(f"클릭 실패\n요소:{target_html}\n오류내용:{e}", file=sys.stderr)
            # 다시 원래 페이지로 이동 및 클릭상태 복구
            # locators = await restore_state()
            continue
    
    return rets

# 개선버전인 위에꺼 쓰기
async def recursive_click(init_url: str, page, frame_index: int, tag_extractor, global_visited) -> list[dict]:
    """
    현재 프레임에서 클릭가능한 요소들을 클릭해봐서, 이동되는 페이지들의 url을 수집함
    Args:
        init_url: 현재 프레임이 속한 url
        page: playwright페이지
        frame_index: 현재프레임의 인덱스
        tag_extractor: 프레임에서 클릭할 후보요소들을 뽑아줌, tag_extractor(page)
        global_visited: 재방문 방지용 집합
    Return:
        list[dict{
            "url": 이동된 페이지의 url,
            "title": 이동된 페이지의 제목,
        }]
    """
    rets = []
    
    # 1. 현재 프레임에서 클릭할 개수 파악
    # (주의: page.frames[frame_index]로 접근해야 안전함)
    target_frame = page.frames[frame_index]
    locators = await tag_extractor(target_frame)
    count = await locators.count()

    for i in range(count):
        try:
            # 매 루프마다 프레임과 로케이터를 새로 갱신 (Stale 방지)
            current_frame = page.frames[frame_index]
            target = (await tag_extractor(current_frame)).nth(i)
            # 눈에 보이는 요소인지 확인
            if not await is_interactable(target):
                continue
            # ----디버깅용----
            print(f"현재요소:{await target.evaluate("el => el.outerHTML")}", file=sys.stderr)
            
            # 클릭 전 URL
            before_url = page.url
            
            #클릭, 로딩대기
            await target.click(timeout=5000)
            await page.wait_for_load_state("domcontentloaded", timeout=5000)

            after_url = page.url
            # 3. URL이 바뀌었고, 처음 보는 곳이라면 수집
            if after_url != init_url and after_url not in global_visited:
                title = await page.title()
                rets.append({
                    "url": after_url,
                    "title": title.strip(),
                })
                # global_visited는 참조 전달이므로 여기서 추가하면 메인 루프에도 반영됨
                global_visited.add(after_url)

            # 4. 원래 위치로 복구
            if page.url != init_url:
                await page.goto(init_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle", timeout=3000)
                
        except Exception as e:
            # ----디버깅용----
            print(f"클릭 실패\n요소:{await target.evaluate("el => el.outerHTML")}\n오류내용:{e}", file=sys.stderr)
            continue
    
    return rets
import sys
@mcp.tool()
async def get_sub_urls_by_click(url: str, depth: int = 1) -> list[dict]:
    """
    현재 페이지에서 클릭가능한 요소들을 클릭해봐서, 이동되는 페이지들의 url을 수집함(페이지내 아이프레임 포함)
    Args:
        url: 페이지 url
        depth: url수집 깊이
    Return:
        list[dict{
            "url": 이동된 페이지의 url,
            "title": 이동된 페이지의 제목,
            "depth": 시작url로 부터의 깊이
        }]
    """
    context, browser = await get_shared_context(False)
    page = await context.new_page()
    
    queue = deque([(url, 0)]) 
    visited = {url} # set
    rets = []

    try:
        while queue:
            cur_url, cur_depth = queue.popleft()
            if cur_depth >= depth:
                continue
            
            response = await page.goto(url, wait_until="domcontentloaded", timeout=0)
            await page.wait_for_load_state("networkidle", timeout=30000)

            # page.frames는 [메인프레임, 아이프레임1, 아이프레임2...] 순서임
            # 메인프레임도 결국 하나의 프레임이므로 따로 처리할 필요 없음
            for i in range(len(page.frames)):
                try:
                    # recursive_click에 visited를 넘겨서 중복 클릭 방지
                    # frame_rets = await recursive_click(cur_url, page, i, tag_extractor, visited)
                    frame_rets = await recursive_dynamic_click(cur_url, page, i, tag_extractor, visited)
                    
                    for ret in frame_rets:
                        rets.append(ret)
                        queue.append((ret['url'], cur_depth + 1))
                except Exception as e:
                    print(f"url:{cur_url}, e:{str(e)}", file=sys.stderr)
                    continue
    finally:
        await browser.close()
    return rets

if __name__ == "__main__":
    mcp.run()

##########################################################################################
# 루트에서 모든 url,페이지 제목 스크렙퍼 만들기: O
## bfs이용, 이미 방문한 url이면 무시, 가지치기: O
## 페이지,iframe에서 텍스트(숫자,특수기호는 무시??)를 가진요소만 추출: O
## 인덱스로 각각을 모두 접근: O
## 그리고 재귀적으로!!!: O, depth이용, depth만큼 재귀