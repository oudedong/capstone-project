from my_scrapper import get_page, get_sub_urls_by_click, Global_visit_page_url, get_clean_url
from my_scrapper import RedirectError, Redirected_page_urls, Redirection_db, Try_login_solver, Redirected_page_solver, Request_to_user_solver
from ..db import insert_origin_url, insert_redirected_urls
from ..db import _db_execute_get
from ..db import get_page_urls_to_check, insert_page_url, insert_page_content, check_page_urls, get_redirected_urls, defresh_todo_list
from ..db import get_unprocessed_page_contents, insert_todo, mark_page_content_processed, upsert_page_content, get_page_content
import json
import subprocess
import sys

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
    def _add(self, r_url:str, t_url:str): # t_url은 나중에 에이전트와 같이 넣기
        insert_redirected_urls(self.db_path, r_url)
    def _contains(self, url:str):
        return len(get_redirected_urls(self.db_path, url)) > 0
    def _get_target_url(self, redirected_url):
        ret = get_redirected_urls(self.db_path, redirected_url)[0]
        t_url = ret['target_url']
        if t_url == None:
            raise Exception(f'target_url이 정해지지않아서 처리할 수 없음')
        return t_url
        
class Redirection_login_db_DB(Redirection_db):
    """db에 login_urls 테이블을 이용한 로그인 리다이렉션 관련정보 db"""
    def __init__(self, db_path:str):
        self.db_path = db_path
    def __call__(self, redirected_url:str)->dict:
        ret = _db_execute_get(self.db_path, 'login_urls', lambda : f"WHERE login_url='{redirected_url}' ")
        return ret[0]

async def get_sub_urls_by_click_db(session_path: str, url: str, db_path, depth: int = 1) -> list[dict]:
    """
    방문,리다이렉션 처리를 db를 이용하는 get_sub_urls_by_click
    """
    r_db = Redirection_login_db_DB(db_path)
    solvers = [Try_login_solver(session_path, r_db), Request_to_user_solver(session_path, r_db)]
    return await get_sub_urls_by_click(session_path, url, Global_visit_DB_page_url(db_path), Redirected_page_urls_DB(db_path, solvers), depth)

async def collect_page_contents(session_path: str, db_path: str, urls_to_check:list[dict]) -> list[dict]:
    """
    DB에 저장된 page_urls 중 확인이 필요한 페이지들을 얻은 후 방문하여 본문을 추출 저장합니다.
    결과로 실패한 것들을 반환함
    """
        
    fails = []
    # urls_to_check = get_page_urls_to_check(db_path, 0)
    # 리다이렉션 처리 시도를 함
    r_db = Redirection_login_db_DB(db_path)
    redirected_page_urls_DB = Redirected_page_urls_DB(db_path, [
        Try_login_solver(session_path, r_db), Request_to_user_solver(session_path, r_db)
    ])
    # print("방문이 필요한 페이지들: ", urls_to_check, file=sys.stderr)
    i = 0
    while i < len(urls_to_check):
        url = urls_to_check[i]
        try:
            try:
                #페이지 가져오고, 가져온거를 db에 저장, 읽은 시간 갱신
                result = await get_page(session_path, url['url'])
                # insert_page_content(db_path, url['url'], result['content']) # 이미 있는건데 변경사항 있으면?
                result_db = get_page_content(db_path, url['url'])
                #이미 있으면(갱신하는 상황)
                if len(result_db) > 0:
                    result_db = result_db[0]
                    # 내용이 같으면 스킵
                    if result_db['content'] == result['content']:
                        i += 1
                        continue
                    defresh_todo_list(db_path, url['url']) # 갱신되기 전에 뽑은 일정들을 오래됨으로 표시함
                upsert_page_content(db_path, url['url'], result['content'])
                check_page_urls(db_path, [url['id']])
                i += 1 
            except RedirectError as e:
                # 리다이렉션 됬을때, 해결시도 후 성공하면 재시도함
                # e.current_url은 실제 튕겨나간(로그인페이지 등) url임
                clean_r_url = get_clean_url(e.current_url)
                if clean_r_url not in redirected_page_urls_DB:
                    redirected_page_urls_DB.add({'redirected_url':e.current_url, 'target_url':None})# target_url은 아직모르니까 비워둠
                    raise Exception(f"리다이렉션 처리정보가 없어서 처리불가: {e.current_url}")
                await redirected_page_urls_DB.try_solve(e.current_url)
        except Exception as e:
            fails += [{"url":url['url'], "e":str(e)}]
            i += 1
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
        try:
            ret:dict = extractor(unprocessed['content'])
        except: continue
        inserted += insert_todo(db_path, unprocessed['url'], ret['content'], ret.get('due_date')) # 이미 있는건데 변경사항 있으면?
        mark_page_content_processed(db_path, [unprocessed['id']])
    return inserted

def gemini_extractor(content:str)->dict:
    """Gemini CLI를 호출하여 일정과 기한을 json형식 문자열로 반환합니다"""
    prompt = (
        "아래 html에서 마감 기한과 일정내용을 찾아줘. 최종 결과는 아래 형식으로 답변하고, 파싱에서 오류가 나지 않게 다른 설명은 아예 하지마."
        "html내용이 게시글 자체일때만 찾아야되, 게시글 목록등 간접적인 페이지에서 추출하면 안되(실패로 처리). 마감기한은 모르겠으면 unknown으로 해"
        '성공시 출력형식: {"content": "찾은내용", "due_date": "YYYY-MM-DD HH:MM"}'
        '실패시 출력형식: {"content": "실패이유", "due_date": null}'
        f"내용:\n{content}"
    )
    
    cmd = ["gemini", "-p", prompt]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=60)
        final_output = result.stdout.strip()
        
        # JSON 블록 안전하게 추출
        start_index = final_output.find('{')
        end_index = final_output.rfind('}') # 뒤에서부터 찾도록 변경
        
        if start_index == -1 or end_index == -1:
            return {"content": f"LLM이 올바른 형식을 반환하지 않음: {final_output}", "due_date": None}
            
        json_str = final_output[start_index:end_index+1]
        return json.loads(json_str)
        
    except json.JSONDecodeError:
        # 파싱 에러 발생 시 프로그램이 죽지 않고 '실패용 안전 딕셔너리'를 반환하여 데이터 흐름 유지
        return {"content": f"JSON 파싱 실패 원본: {final_output}", "due_date": None}
    except Exception as e:
        return {"content": f"시스템 에러: {str(e)}", "due_date": None}
    
async def insert_origin_url_check_redirection(db_path:str , url:str, summary:str)->dict:
    '''리다이렉션 여부를 검사하며 넣습니다'''
    redirected_url = None
    ret_list = insert_origin_url(db_path, url, summary)
    ret = ret_list[0]
    # 리다이렉션 여부 확인
    try:
        await get_page(None, url)
    except RedirectError as re:
        redirected_url = re.current_url # 현재 리다이렉션된 url을 반환함
    except:
        raise
    print('check_redirect결과:', redirected_url, file=sys.stderr)
    # 리다이렉션 되었다면, 리다이렉션된 주소를 db에 저장
    if redirected_url:
        insert_redirected_urls(db_path, redirected_url)
        ret['redirected_url'] = redirected_url
    return ret
