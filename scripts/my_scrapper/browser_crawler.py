import sys
from collections import deque
from typing import Callable
from urllib.parse import urlparse

from .browser_session import Playwright_mn, wait_dom_stable, is_interactable
from .html_cleaner import recursive_iframe_replace, clean_html

from abc import ABC, abstractmethod

# ── 페이지 가져오기 ────────────────────────────────────────────────────────────

async def _request_to_user(mn: Playwright_mn, request_url:str):
    page = await mn.new_page()
    await page.goto(request_url)
    await page.wait_for_event("close", timeout=300000)
    await mn.storage_state() # 세션저장

async def request_to_user(session_path: str, request_url: str) -> str:
    """
    처리하기 힘든 URL(로그인 페이지 등)에 대해 사용자가 직접 브라우저에서 처리하도록 열어줍니다.
    처리 결과를 세션에 저장합니다.
    """
    mn = await Playwright_mn.create(session_path, False)
    try:
        await _request_to_user(mn, request_url)
        return "세션 저장 완료"
    except Exception as e:
        return f"시간 초과 또는 오류 발생: {e}"
    finally:
        await mn.close()

    # page = await mn.new_page()
    # await page.goto(request_url)

    # try:
    #     await page.wait_for_event("close", timeout=300000)
    #     await mn.storage_state()
    #     return "세션 저장 완료"
    # except Exception as e:
    #     return f"시간 초과 또는 오류 발생: {e}"
    # finally:
    #     await context.close()

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
    # context = await Playwright_mn.create(session_path, True)
    context = await Playwright_mn.create(session_path, False)
    page = await context.get_page()
    response = None

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=0)
        await page.wait_for_load_state("networkidle", timeout=30000)
        await wait_dom_stable(page)

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
        init_url: str, nm: Playwright_mn, frame_index: int, tag_extractor,
        global_visited, Redirected_page_urls:"Redirected_page_urls"=None, # 방문한 url집합, 리다이렉션 url집합
        init_click_elements_nths: list[int] = None,
        new_elements_nths: list[int] = None) -> list[dict]:
    """
    프레임에서 클릭 가능한 요소들을 모두 클릭해보며 이동되는 URL을 수집합니다.
    동적으로 생성되는 요소(드롭다운 등)도 재귀적으로 탐색합니다.
    """
    if init_click_elements_nths is None:
        init_click_elements_nths = []
    
    page = await nm.get_page() ##

    async def restore_locator():
        target_frame = page.frames[frame_index]
        return await tag_extractor(target_frame)

    async def restore_state():
        await page.goto(init_url, wait_until="domcontentloaded")
        for nth in init_click_elements_nths:
            await wait_dom_stable(page)
            target_frame = page.frames[frame_index]
            locators = await tag_extractor(target_frame)
            await locators.nth(nth).click(timeout=5000)
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

    # 인덱스,순서로 요소를 나타냄
    targets_to_click = new_elements_nths if new_elements_nths is not None else range(count)

    j = 0
    while j < len(targets_to_click):
        i = targets_to_click[j]
        target_html = None
        try:
            locators = await restore_locator() # 뭔가 문제가 있음, 주석치면 잘 안돌아감...
            target = locators.nth(i)
            target_html = await target.evaluate(_DESCRIBE_JS, timeout=5000)

            if not await is_interactable(target):
                j += 1
                continue

            print(f"[*] 클릭 시도: {target_html}", file=sys.stderr)
            await target.click(timeout=5000)
            await wait_dom_stable(page)

            after_url = page.url
            print(f"[*] 이동된 url: {after_url}", file=sys.stderr)

            # 페이지 이동이 생겼으면
            if after_url != init_url:
                # 리다이렉션 페이지인지 확인(리다이렉션 집합이 있는경우에만)
                if Redirected_page_urls != None:
                    if after_url in Redirected_page_urls:
                        # 해결시도
                        ret = await Redirected_page_urls.try_solve(after_url)
                        # 성공시
                        if ret:
                            # 세션갱신 후 재시도(j증가 x)
                            await nm.reload_state()
                            page = await nm.get_page()
                            locators = await restore_state()
                            continue 
                        # 실패시 건너뜀
                        j += 1
                        continue
                # 이미 방문한 페이지인지
                if after_url not in global_visited:
                    title = await page.title()
                    ret = {"url": after_url, "title": title.strip()}
                    rets.append(ret)
                    global_visited.add(ret)
                    print(f"[*] 추가한 url: {ret['url']}", file=sys.stderr)
                locators = await restore_state()
                j += 1
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
            # 새로운 요소가 있다면
            if new_indices:
                next_path = init_click_elements_nths + [i]
                rets += await _recursive_dynamic_click(
                    init_url, nm, frame_index, tag_extractor,
                    global_visited, Redirected_page_urls,
                    next_path, new_indices
                )
                locators = await restore_state()
            j += 1
        except Exception as e:
            # import traceback
            # traceback.print_exc(file=sys.stderr)
            # print(f"클릭 실패\n요소:{target_html}\n오류내용:{e}", file=sys.stderr)
            j += 1
            continue

    return rets


async def get_sub_urls_by_click(session_path:str, url: str, visited, Redirected_page_urls:"Redirected_page_urls"=None, depth: int = 1) -> list[dict]:
    """
    페이지에서 클릭 가능한 요소들을 탐색하여 이동되는 URL들을 수집합니다.
    iframe 내부도 탐색하며, depth만큼 재귀적으로 수집합니다.
    """
    nm = await Playwright_mn.create(session_path, False)
    page = None

    queue = deque([(url, 0)])
    try: # 수정필요...
        visited.add({"url": url, "title": None})
    except: pass
    rets = []

    try:
        while queue:
            cur_url, cur_depth = queue.popleft()
            if depth > 0 and cur_depth >= depth:
                continue
            
            # 세션 갱신등으로 page가 바뀌었을 수 있으므로 갱신
            page = await nm.get_page()
            await page.goto(cur_url, wait_until="domcontentloaded", timeout=0)
            await wait_dom_stable(page)
            # 만약 처음접속한 페이지가 리다이렉션 페이지이면
            if cur_url != page.url:
                if Redirected_page_urls != None :
                    # 리다이렉션 정보가 있을때
                    if page.url in Redirected_page_urls:
                        ret = await Redirected_page_urls.try_solve(page.url)
                        # 해결실패시
                        if not ret:
                            # 건너뜀
                            print(f"리다이렉션 해결실패 url:{cur_url}, 건너뜀", file=sys.stderr)
                            continue
                        # 해결성공시: 페이지 갱신후 다시 접속함
                        await nm.reload_state()
                        page = await nm.get_page()
                        await page.goto(cur_url, wait_until="domcontentloaded", timeout=0)
                        await wait_dom_stable(page)
                    # 없을때
                    else:
                        # 리다이렉션 정보를 db에 추가 후 건너뜀
                        print(f"db에 정보가 없는 리다이렉션 발생 url:{cur_url}, db에 추가 후 건너뜀", file=sys.stderr)
                        Redirected_page_urls.add({'redirected_url':page.url, 'target_url':None}) # page.url이 실제,리다이렉션된 url
                        continue
                else:
                    print(f"리다이렉션 발생 url:{cur_url}, 건너뜀", file=sys.stderr)
                    continue

            for i in range(len(page.frames)):
                try:
                    frame_rets = await _recursive_dynamic_click(
                        cur_url, nm, i, _tag_extractor, visited, Redirected_page_urls
                    )
                    for ret in frame_rets:
                        rets.append(ret)
                        queue.append((ret['url'], cur_depth + 1))
                except Exception as e:
                    print(f"url:{cur_url}, e:{str(e)}", file=sys.stderr)
                    continue
    finally:
        await nm.close()

    return rets

class Global_visit_page_url(ABC):
    """방문집합 형식"""
    @abstractmethod
    def __contains__(self, url:str) -> bool:
        """집합에 대해 in연산"""
        pass
    @abstractmethod
    def add(self, data:dict):
        """집합 추가 연산"""
        pass
class Global_visit_set_page_url(Global_visit_page_url):
    """set을 이용한 방문집합, 디버깅용"""
    def __init__(self):
        self.set = set()
    def __contains__(self, url:str) -> bool:
        return url in self.set
    def add(self, data:dict):
        self.set.add(data['url'])

def get_clean_url(url:str)->str:
    # URL에서 쿼리스트링을 제외한 부분만 반환함
    parsed_url = urlparse(url)
    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    return clean_url

class Redirected_page_urls(Global_visit_page_url):
    """리다이렉션 페이지로 이동했는지 확인, 해결을 시도해보는 클래스"""
    def __init__(self, solvers:list["Redirected_page_solver"]):
        self.solvers = solvers # 리다이렉션을 해결해볼 방법들
    async def try_solve(self, redirected_url:str) -> bool:
        # 리다이렉션 문제를 해결시도해봄
        t_url = None
        try:
            t_url = self._get_target_url(redirected_url)
        except Exception as e:
            print(f't_url을 얻을 수 없음: url:{redirected_url}, e:{str(e)}', file=sys.stderr)
            return False
        for solver in self.solvers:
            if await solver(t_url):
                return True
        return False
    @abstractmethod
    def _get_target_url(self, redirected_url):
        # 리다이렉션을 처리하기위해 이동해야되는 페이지를 줌(로그인페이지 등등)
        pass
    def add(self, data:dict):
        # 쿼리스트링 때줌, 아래 2가지 값이 있어야됨
        r_url = get_clean_url(data['redirected_url']) # 리다이렉션된 url
        t_url = data['target_url']                    # 처리를 할 url위치 
        self._add(r_url, t_url)
    @abstractmethod
    def _add(self, r_url:str, t_url:str):
        # 실제 삽입부분
        pass
    def __contains__(self, url:str)->bool:
        # 마찬가지로 쿼리스트링 때줌
        url = get_clean_url(url)
        return self._contains(url)
    @abstractmethod
    def _contains(self, url:str):
        # 실제 in연산 부분
        pass
class Redirected_page_urls_set(Redirected_page_urls):
    """파이썬 딕셔너리를 활용하는 Redirected_page_urls"""
    def __init__(self, solvers):
        super().__init__(solvers)
        self.r_db = {}
    def _contains(self, url:str)->bool:
        ret = self.r_db.get(url)
        return not(ret == None)
    def _add(self, r_url:str, t_url:str):
        self.r_db[r_url]=t_url
    def _get_target_url(self, redirected_url):
        return self.r_db[redirected_url]
class Redirected_page_solver(ABC):
    """
    해결을 담당하는 클래스
    예외처리는 여기서!!
    """
    def __init__(self, session_path:str, data_source, headless):
        self.session_path = session_path #해결완료시 세션을 저장할 경로
        self.data_source = data_source #리다이렉션 해결에 필요한 정보들을 줄 객체!!!!! 리다이렉션된 주소를 입력으로 받아서, 해당 url에 필요한 데이터들을 줌
        self.headless = headless
    async def __call__(self, redirected_url:str)->bool:
        data = self.data_source(redirected_url)
        try:
            # solver로 해결시도
            mn = await Playwright_mn.create(self.session_path, self.headless)
            result = await self._solve(mn, data)
            if result:
                #성공시 세션저장
                await mn.context.storage_state(path=self.session_path)
            return result
        except Exception as e:
            print(f"solver실패: 클래스명:{self.__class__.__name__}, e:{str(e)}", file=sys.stderr)
            result = False
        finally:
            # mn반환
            await mn.close()
    @abstractmethod
    async def _solve(self, mn:Playwright_mn, data:dict)->bool:
        """
        실제 해결하는 부분
        mn: playwright객체,
        data: 리다이렉션 해결에 필요한 데이터
        """
        pass
class Try_login_solver(Redirected_page_solver):
    """
    로그인 페이지에서 로그인을 시도해보는 클래스
    아이디,비밀번호 입력창의 css경로와 아이디 비번을 활용함
    """
    def __init__(self, session_path:str, data_source, headless=True):
        super().__init__(session_path, data_source, headless)
    async def _solve(self, mn:Playwright_mn, data:dict)->bool:
        """
        data는 반드시 아래 필드를 가지고 있어야됨!!!!
        login_url: 로그인을 시도할 url
        css_path_id: 아이디 입력창의 css경로
        css_path_pw: pw 입력창의 css경로
        login_id: 로그인 id
        login_pw: 비밀번호
        """
        ############## 나중에 별도클래스로 빼주기...
        login_url = data['login_url']
        css_path_id = data['css_path_id']
        css_path_pw = data['css_path_pw']
        login_id = data['login_id']
        login_pw = data['login_pw']
        # 로그인 페이지로 이동
        page = await mn.get_page()
        await page.goto(login_url)
        await wait_dom_stable(page)
        # 로그인 요소들 찾기
        id_field = page.locator(css_path_id)
        pw_field = page.locator(css_path_pw)
        # id,비번 입력
        await id_field.fill(login_id)
        await pw_field.fill(login_pw)
        # 엔터
        await pw_field.press("Enter")
        
        # 로그인 성공여부 확인
        await wait_dom_stable(page)
        ## url이 바뀌었다면 성공처리
        if page.url != login_url:
            return True
        return False
class Request_to_user_solver(Redirected_page_solver):
    """
    유저에게 해결을 요청하는 클래스
    아이디,비밀번호 입력창의 css경로와 아이디 비번을 활용함
    """
    def __init__(self, session_path:str, data_source):
        super().__init__(session_path, data_source, False)
    async def _solve(self, mn:Playwright_mn, data:dict)->bool:
        """
        data는 반드시 아래 필드를 가지고 있어야됨!!!!
        login_url: 로그인을 시도할 url
        유저에게 알릴방법: (미구현됨...)
        """
        login_url = data['login_url']
        # channel_to_user = data['channel_to_user']

        _request_to_user(mn, login_url)
        return True
    
class Redirection_db(ABC):
    """
    리다이렉션 해결에 필요한 정보들을 가짐
    """
    @abstractmethod
    def __call__(self, redirected_url:str)->dict:
        """
        url을 받아 해당 url에서 solver가 리다이렉션 해결에 필요한 정보들을 dict형태로 반환함
        """
        pass

async def get_sub_urls_by_click_set(session_path:str, url: str, Redirected_page_urls: Redirected_page_urls, depth: int = 1) -> list[dict]:
    """
    방문처리를 set를 이용하는 get_sub_urls_by_click
    """
    return await get_sub_urls_by_click(session_path, url, Global_visit_set_page_url(), Redirected_page_urls, depth)