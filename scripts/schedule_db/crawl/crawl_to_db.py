from my_scrapper import get_page, get_sub_urls_by_click, Global_visit_page_url
from my_scrapper import RedirectError, request_to_user, Redirected_page_urls, Redirection_db, Try_login_solver, Redirected_page_solver, Request_to_user_solver
from ..db import insert_origin_url, insert_redirected_urls
from ..db import _db_execute_get
from ..db import get_page_urls_to_check, insert_page_url, insert_page_content, check_page_urls, get_redirected_urls
from ..db import get_unprocessed_page_contents, insert_todo, mark_page_content_processed
import json
import subprocess

class Global_visit_DB_page_url(Global_visit_page_url):
    """db를 이용한 방문집합"""
    def __init__(self, path:str):
        self.path = path
    def __contains__(self, url:str) -> bool:
        ret = _db_execute_get(self.path, 'page_urls', lambda : f"WHERE url='{url}' ")
        return len(ret) > 0
    def add(self, data:dict):
        return insert_page_url(self.path, data['url'], data['title'])
class Redirected_page_urls_DB(Redirected_page_urls):
    """db를 이용한 리다이렉션 url집합"""
    def __init__(self, db_path:str, solvers:list["Redirected_page_solver"]):
        super().__init__(solvers)
        self.db_path = db_path
    def _add(self, data:dict):
        insert_redirected_urls(self.db_path, data['url'])
    def _contains(self, url:str):
        return len(get_redirected_urls(self.db_path, url)) > 0
class Redirection_login_db_DB(Redirection_db):
    """db에 login_urls 테이블을 이용한 로그인 리다이렉션 관련정보 db"""
    def __init__(self, db_path:str):
        self.db_path = db_path
    def __call__(self, redirected_url:str)->dict:
        ret = _db_execute_get(self.path, 'login_urls', lambda : f"WHERE login_url='{redirected_url}' ")
        return ret[0]

# 전부 수정필요 #############################################################
async def get_sub_urls_by_click_db(session_path: str, url: str, db_path, depth: int = 1) -> list[dict]:
    """
    방문처리를 db를 이용하는 get_sub_urls_by_click
    """
    return await get_sub_urls_by_click(session_path, url, Global_visit_DB_page_url(db_path), Redirected_page_urls_DB(), depth)

async def collect_page_contents(session_path: str, db_path: str) -> list[dict]:
    """
    DB에 저장된 page_urls 중 확인이 필요한 페이지들을 얻은 후 방문하여 본문을 추출 저장합니다.
    결과로 실패한 것들을 반환함
    """
    async def get_insert_check(url:dict):
        #페이지 가져오고, 가져온거를 db에 저장, 읽은 시간 갱신
        result = await get_page(session_path, url['url'])
        insert_page_content(db_path, url['url'], result['content'])
        check_page_urls(db_path, [url['id']])
    fails = []
    urls_to_check = get_page_urls_to_check(db_path, 0)
    print("방문이 필요한 페이지들: ", urls_to_check)
    for url in urls_to_check:
        try:
            try:
                await get_insert_check(url)
            except RedirectError as e:
                # 리다이렉션 됬을때
                await request_to_user(session_path, url['url']) # 바꿀 수 있게하기, 사용자에게 요청말고, 환경변수를 이용한 처리?
                # 처리 됬을시 다시
                check_page_urls(url)
        except Exception as e:
            fails += [{"url":url['url'], "e":str(e)}]
    return fails

def make_todo_list_from_page_contents(db_path: str, extractor)->list[dict]:
    """
    db의 page_contents테이블에서 확인하지 않은 내용에 대해서 일정을 뽑아냅니다.
    Args:
        db_path: db경로
        extractor(content:str)->{content:str:일정내용, due_date:str:기한}: 읽고 일정을 추출해 내는거
    Return:
        추가한 일정들
    """
    unprocessed_contents = get_unprocessed_page_contents(db_path)
    inserted = []
    for unprocessed in unprocessed_contents:
        ret:dict = extractor(unprocessed['content'])
        inserted += insert_todo(db_path, unprocessed['url'], ret['content'], ret.get('due_date'))
        mark_page_content_processed(db_path, [unprocessed['id']])
    return inserted

def gemini_extractor(content:str)->dict:
    """Gemini CLI를 호출하여 일정과 기한을 json형식 문자열로 반환합니다"""
    prompt = (
        "아래 html에서 마감 기한과 일정내용을 찾아줘. 최종 결과는 아래 형식으로 답변하고, 파싱에서 오류가 나지 않게 다른 설명은 아예 하지마."
        "html내용이 게시글 자체일때만 찾아야되, 게시글 목록등 간접적인 페이지에서 추출하면 안되"
        '성공시 출력형식: {"content": "찾은내용", "due_date": "마감기한"}'
        '실패시 출력형식: {"content": "실패이유"}'
        f"내용:\n{content}"
    )
    
    cmd = ["gemini", "-p", prompt]
    
    print("--- Gemini 일정 추출 시작 ---")
    result = subprocess.run(
        cmd, 
        capture_output=True,
        text=True, 
        encoding='utf-8'
    )
    
    final_output = result.stdout
    # final_output = result.strip().strip("'")
    start_index = final_output.find('{')
    end_index = final_output.find('}')
    final_output = final_output[start_index:end_index+1]
    print("결과:",final_output)
    return json.loads(final_output)

async def check_redirect(url: str)->str:
    """리다이렉션 여부를 검사함, 리다이렉션시 리다이렉션된 url을 반환함"""
    try:
        ret = await get_page(None, url)
        print('check_redirect결과:',ret)
    except RedirectError as re:
        return re.current_url # 현재 리다이렉션된 url을 반환함
    except:
        raise
    return None
async def insert_origin_url_check_redirection(db_path:str , url:str, summary:str):
    '''리다이렉션 여부를 검사하며 넣습니다'''
    redirected_url = await check_redirect(url)
    print('check_redirect결과:', redirected_url)
    if redirected_url:
        insert_redirected_urls(db_path, redirected_url)
        is_redirected = True
    return insert_origin_url(db_path, url, summary)
