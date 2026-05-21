import asyncio
from schedule_db.db import *
from schedule_db import *
from schedule_db.crawl import *
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.path.join(BASE_DIR, 'workspace', 'data', 'schedule_test.db')
SESSION_FILE = Path("/home/oudedong/capstone-agent/.gemini/session.json")
test_url='https://software.korea.ac.kr/software/9446/subview.do?enc=Zm5jdDF8QEB8JTJGYmJzJTJGc29mdHdhcmUlMkYzNTIlMkZhcnRjbExpc3QuZG8lM0ZwYWdlJTNEMTElMjZmaW5kVHlwZSUzRCUyNmZpbmRXb3JkJTNEJTI2ZmluZENsU2VxJTNEJTI2ZmluZE9wbndyZCUzRCUyNnJnc0JnbmRlU3RyJTNEJTI2cmdzRW5kZGVTdHIlM0QlMjY%3D'
async def run():
    # init_db(DB_PATH)
    # insert_origin_url(
    # DB_PATH, 
    # 'https://software.korea.ac.kr/software/9446/subview.do?enc=Zm5jdDF8QEB8JTJGYmJzJTJGc29mdHdhcmUlMkYzNTIlMkZhcnRjbExpc3QuZG8lM0ZwYWdlJTNEMTElMjZmaW5kVHlwZSUzRCUyNmZpbmRXb3JkJTNEJTI2ZmluZENsU2VxJTNEJTI2ZmluZE9wbndyZCUzRCUyNnJnc0JnbmRlU3RyJTNEJTI2cmdzRW5kZGVTdHIlM0QlMjY%3D',
    # '학과홈피')
    # await run_extraction()
    init_db(DB_PATH)
    ret = await insert_origin_url_check_redirection(DB_PATH, 'https://mylms.korea.ac.kr/accounts/1/external_tools/10?launch_type=global_navigation', 'LMS모든 메세지')
    print(ret)
asyncio.run(run())