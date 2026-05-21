from .crawl import *
from .db import get_origin_urls, init_db
    
async def run_extraction(db_path: str, session_path: str):
    init_db(db_path)
    origins = get_origin_urls(db_path)
    rets = []
    for origin in origins:
        rets += await get_sub_urls_by_click_db(session_path, origin['url'], DB_PATH)
    print('origin url들에서 수집한 페이지 url들:', rets)
    rets = await collect_page_contents(session_path, db_path)
    print('수집에 실패한 페이지들:', rets)
    rets = make_todo_list_from_page_contents(db_path, gemini_extractor)
    print('추가한 일정들:', rets)