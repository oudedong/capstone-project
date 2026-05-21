from my_scrapper import get_page, get_sub_urls_by_click, Global_visit_page_url, RedirectError, request_to_user
from ..db import _db_execute_get
from ..db import get_page_urls_to_check, insert_page_url, insert_page_content, check_page_urls
from ..db import get_unprocessed_page_contents, insert_todo, mark_page_content_processed
import json
import subprocess

class Global_visit_DB_page_url(Global_visit_page_url):
    """db를 이용한 방문집합"""
    def __init__(self, path:str):
        self.path = path
    def __contains__(self, url:str) -> bool:
        ret = _db_execute_get(self.path, 'page_urls', lambda : f"WHERE url='{url}' ")
        # ret = _db_execute(self.path, 'page_urls', _get, lambda : f"WHERE url='{url}' ")
        return len(ret) > 0
    def add(self, data:dict):
        return insert_page_url(self.path, data['url'], data['title'])

async def get_sub_urls_by_click_db(session_path: str, url: str, db_path, depth: int = 1) -> list[dict]:
    """
    방문처리를 db를 이용하는 get_sub_urls_by_click
    """
    return await get_sub_urls_by_click(session_path, url, Global_visit_DB_page_url(db_path), depth)

async def collect_page_contents(session_path: str, db_path: str) -> list[dict]:
    """
    DB에 저장된 page_urls 중 확인이 필요한 페이지들을 얻은 후 방문하여 본문을 추출 저장합니다.
    결과로 실패한 것들을 반환함
    """
    fails = []
    urls_to_check = get_page_urls_to_check(db_path, 0)
    print("방문이 필요한 페이지들: ", urls_to_check)
    for url in urls_to_check:
        try:
            try:
                result = await get_page(session_path, url['url'])
                insert_page_content(db_path, url['url'], result['content'])
                check_page_urls(db_path, [url['id']])
            except RedirectError as e:
                # 리다이렉션 됬을때
                await request_to_user(session_path, url) # 바꿀 수 있게하기, 사용자에게 요청말고, 환경변수를 이용한 처리?
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