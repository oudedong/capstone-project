import asyncio
from schedule_db.db import *
from schedule_db import *
from schedule_db.crawl import *
from my_scrapper import *
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.path.join(BASE_DIR, 'workspace', 'data', 'schedule_test.db')
SESSION_FILE = Path("/home/oudedong/capstone-agent/.gemini/session.json")

test_url='https://lms.korea.ac.kr/'
r_url = 'https://lms.korea.ac.kr/xn-sso/login.php'
test_url2='https://mylms.korea.ac.kr/accounts/1/external_tools/10?launch_type=global_navigation'
test_url3='https://software.korea.ac.kr/software/9446/subview.do?enc=Zm5jdDF8QEB8JTJGYmJzJTJGc29mdHdhcmUlMkYzNTIlMkZhcnRjbExpc3QuZG8lM0ZwYWdlJTNEMTElMjZmaW5kVHlwZSUzRCUyNmZpbmRXb3JkJTNEJTI2ZmluZENsU2VxJTNEJTI2ZmluZE9wbndyZCUzRCUyNnJnc0JnbmRlU3RyJTNEJTI2cmdzRW5kZGVTdHIlM0QlMjY%3D'
# class Redirection_db_temp(Redirection_db):
#     def __call__(self, redirected_url):
#         return {
#             'login_url':"https://ksso.korea.ac.kr/svc/tk/Auth.do?id=lms&ac=Y&ifa=N&RelayState=https%3A%2F%2Flms.korea.ac.kr%2Fxn-sso%2Fgw-cb.php%3Ffrom%3D%26site%3D%26login_type%3Dstandalone%26return_url%3Dhttps%253A%252F%252Flms.korea.ac.kr%252Flogin%252Fcallback&",
#             'css_path_id':'#one_id',
#             'css_path_pw':'#password',
#             'login_id':'oudedong',
#             'login_pw':'Hsi24682!!'
#         }
    
# async def test():
#     init_db(DB_PATH)
#     r_db = Redirection_login_db_DB(DB_PATH)
#     solvers = [Try_login_solver(SESSION_FILE, r_db, False), Request_to_user_solver(SESSION_FILE, r_db)]
#     r_set = Redirected_page_urls_DB(DB_PATH, solvers)
#     # r_set.add({"redirected":r_url, "target_url: None"})
#     ret = await get_sub_urls_by_click_db(SESSION_FILE, test_url2, DB_PATH)
#     print(ret)

# asyncio.run(test())

# async def test():
#     init_db(DB_PATH)
#     await insert_origin_url_check_redirection(DB_PATH, test_url2, "lms목록")
#     await insert_origin_url_check_redirection(DB_PATH, test_url3, "학과공지")
#     print(get_unprocessed_redirected_urls(DB_PATH))
#     ret = await run_extraction(DB_PATH, SESSION_FILE, 1)
#     print(ret)

# # 전처리 없는 get_page
# async def test():
#     ret = await get_raw_page(SESSION_FILE, 'https://ksso.korea.ac.kr/svc/tk/Auth.do?id=lms&ac=Y&ifa=N&RelayState=https%3A%2F%2Flms.korea.ac.kr%2Fxn-sso%2Fgw-cb.php%3Ffrom%3D%26site%3D%26login_type%3Dstandalone%26return_url%3Dhttps%253A%252F%252Flms.korea.ac.kr%252Flogin%252Fcallback&')
#     print(ret)

# # 리다이렉션 solver
# async def test():
#     init_db(DB_PATH)
#     login_db = Redirection_login_db_DB(DB_PATH)
#     r_db = Redirected_page_urls_DB(DB_PATH, [Try_login_solver(SESSION_FILE, login_db, False)])
#     insert_redirected_urls(DB_PATH, "https://lms.korea.ac.kr/")
#     add_target_url_to_redirected_urls(DB_PATH, "https://lms.korea.ac.kr/", 'https://ksso.korea.ac.kr/svc/tk/Auth.do?id=lms&ac=Y&ifa=N&RelayState=https%3A%2F%2Flms.korea.ac.kr%2Fxn-sso%2Fgw-cb.php%3Ffrom%3D%26site%3D%26login_type%3Dstandalone%26return_url%3Dhttps%253A%252F%252Flms.korea.ac.kr%252Flogin%252Fcallback&')
#     insert_login_urls(DB_PATH, 'https://ksso.korea.ac.kr/svc/tk/Auth.do?id=lms&ac=Y&ifa=N&RelayState=https%3A%2F%2Flms.korea.ac.kr%2Fxn-sso%2Fgw-cb.php%3Ffrom%3D%26site%3D%26login_type%3Dstandalone%26return_url%3Dhttps%253A%252F%252Flms.korea.ac.kr%252Flogin%252Fcallback&', "#one_id", "#password", "oudedong", "Hsi24682!!")
#     ret = await r_db.try_solve("https://lms.korea.ac.kr/")
#     print(ret)

# origin_url삽입시 리다이렉션 감지,저장
async def test():
    init_db(DB_PATH)
    await insert_origin_url_check_redirection(DB_PATH, test_url2, "고려대 LMS")
    await run_extraction(DB_PATH, SESSION_FILE)
asyncio.run(test())