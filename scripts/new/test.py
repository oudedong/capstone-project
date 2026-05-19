import asyncio
from my_db import *
from run_extraction import *

DB_PATH = "/home/oudedong/capstone-agent/workspace/data/schedule.db"
test_url='https://software.korea.ac.kr/software/9446/subview.do?enc=Zm5jdDF8QEB8JTJGYmJzJTJGc29mdHdhcmUlMkYzNTIlMkZhcnRjbExpc3QuZG8lM0ZwYWdlJTNEMTElMjZmaW5kVHlwZSUzRCUyNmZpbmRXb3JkJTNEJTI2ZmluZENsU2VxJTNEJTI2ZmluZE9wbndyZCUzRCUyNnJnc0JnbmRlU3RyJTNEJTI2cmdzRW5kZGVTdHIlM0QlMjY%3D'
async def demo():
    # init_db(DB_PATH)
    # insert_origin_url(
    # DB_PATH, 
    # 'https://software.korea.ac.kr/software/9446/subview.do?enc=Zm5jdDF8QEB8JTJGYmJzJTJGc29mdHdhcmUlMkYzNTIlMkZhcnRjbExpc3QuZG8lM0ZwYWdlJTNEMTElMjZmaW5kVHlwZSUzRCUyNmZpbmRXb3JkJTNEJTI2ZmluZENsU2VxJTNEJTI2ZmluZE9wbndyZCUzRCUyNnJnc0JnbmRlU3RyJTNEJTI2cmdzRW5kZGVTdHIlM0QlMjY%3D',
    # '학과홈피')
    # await run_extraction()
    print(get_todo_list_all(DB_PATH))
asyncio.run(demo())