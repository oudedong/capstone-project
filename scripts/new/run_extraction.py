
import os
from pathlib import Path
from crawl_to_db import *
from my_db import get_origin_urls, init_db
import asyncio

# 프로젝트 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = os.path.join(BASE_DIR, 'workspace', 'data', 'schedule_test.db')
SESSION_FILE = Path("/home/oudedong/capstone-agent/.gemini/session.json")
    

async def run_extraction():
    init_db(DB_PATH)
    origins = get_origin_urls(DB_PATH)
    rets = []
    for origin in origins:
        rets += await get_sub_urls_by_click_db(SESSION_FILE, origin['url'], DB_PATH)
    print('origin url들에서 수집한 페이지 url들:', rets)
    rets = await collect_page_contents(SESSION_FILE, DB_PATH)
    print('수집에 실패한 페이지들:', rets)
    rets = make_todo_list_from_page_contents(DB_PATH, gemini_extractor)
    print('추가한 일정들:', rets)

asyncio.run(run_extraction())

# if __name__ == "__main__":
#     asyncio.run(run_extraction())