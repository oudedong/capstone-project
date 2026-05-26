# from mcp.server.fastmcp import FastMCP
from fastmcp import FastMCP
from my_scrapper import request_to_user, get_page, get_sub_urls_by_click_set, get_raw_page
from my_scrapper import Redirected_page_urls, Try_login_solver
from schedule_db.crawl import *
from schedule_db.db import *
# from schedule_db import run_extraction
from functools import wraps
import json
import uuid

import asyncio
import inspect
import sys,os

mcp = FastMCP("browser_tools")

# JSON 변환 데코레이터
def to_json(func):
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return json.dumps(result, ensure_ascii=False, indent=2)

    return async_wrapper if asyncio.iscoroutinefunction(func) or inspect.isawaitable(func) else sync_wrapper

@mcp.tool()
@to_json
async def request_to_user_tool(session_path: str, request_url: str) -> str:
    """
    처리하기 힘든 특정 URL(로그인,캡챠 등)에 대해 사용자에게 처리를 요청합니다.
    사용자가 브라우저에서 직접 처리하면 결과를 세션에 저장합니다.

    Args:
        session_path: 세션정보가 저장된 파일의 path, 없으면 해당경로에 세션파일을 생성함
        request_url: 사용자에게 요청할 URL
    Returns:
        current_url: 현재 페이지 URL
        intended_url: 처음에 접근하려한 URL
        is_intended_url: 의도한 페이지로 접근했는지 여부
        current_page_title: 현재 페이지 제목
    """
    return await request_to_user(session_path,request_url)

@mcp.tool()
@to_json
async def try_to_solve_redirection(session_path: str, db_path:str, redirected_url: str) -> bool:
    """
    리다이렉션 페이지에 대해 기본처리(현재는 로그인 리다이렉션만 처리가능)를 시도합니다.
    처리하면 결과를 세션에 저장합니다.

    Args:
        session_path: 세션정보가 저장된 파일의 path, 없으면 해당경로에 세션파일을 생성함
        db_path: db경로
        redirected_url: 리다이렉션 페이지
    Returns:
        성공여부를 bool로
    """
    login_db = Redirection_login_db_DB(db_path)
    r_db = Redirected_page_urls_DB(db_path, [Try_login_solver(session_path, login_db)])
    return await r_db.try_solve(redirected_url)


@mcp.tool()
@to_json
async def get_raw_page_tool(session_path: str, url: str) -> str:
    """
    URL 페이지를 가져와 HTML을 추출하고, 정보들을 JSON 형태로 반환합니다.

    Args:
        url: 페이지 URL
    Returns:
        session_path: 세션정보가 저장된 파일의 path
        current_url: 현재 페이지 URL
        current_page_title: 현재 페이지 제목
        content: 원본 페이지 내용
        intended_url: 접근하려 했던 URL
        is_intended_url: 현재 페이지가 접근하려 했던 페이지인지 여부
    """
    return await get_raw_page(session_path,url)

@mcp.tool()
@to_json
async def get_post_processed_page_tool(session_path: str, url: str) -> str:
    """
    URL 페이지를 가져와 HTML을 추출하고 **후처리 후** , 정보들을 JSON 형태로 반환합니다.

    Args:
        url: 페이지 URL
    Returns:
        session_path: 세션정보가 저장된 파일의 path
        current_url: 현재 페이지 URL
        current_page_title: 현재 페이지 제목
        content: 현재 페이지 내용 (후처리됨: 불필요 태그·공백 제거)
        intended_url: 접근하려 했던 URL
        is_intended_url: 현재 페이지가 접근하려 했던 페이지인지 여부
    """
    return await get_page(session_path,url)

# 전역 작업 저장소
crawl_tasks = {}

async def _run_extraction(task_id:str, db_path: str, session_path: str):
    task_info = crawl_tasks[task_id]
    
    # stderr 리다이렉션 (Errno 11 방지)
    original_stderr = sys.stderr
    log_dir = os.path.dirname(db_path) or 'workspace'
    log_file_path = os.path.join(log_dir, f'crawl_{task_id}.log')
    
    try:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            sys.stderr = f
            
            task_info["logs"] += "db설정중\n"
            init_db(db_path)
            task_info["logs"] += "완료\n"

            task_info["logs"] += "db의 origin_urls 불러오는중\n"
            origins = get_origin_urls(db_path)
            task_info["logs"] += "완료\n"

            task_info["logs"] += "origin_urls에서 page_url들 수집중\n"
            rets = []
            for origin in origins:
                rets += await get_sub_urls_by_click_db(session_path, origin['url'], db_path)
            task_info["logs"] += f"수집한 페이지 url들:{rets}\n"

            task_info["logs"] += "페이지url에서 본문 추출중\n"
            rets = get_page_urls_to_check(db_path, 2)
            rets = await collect_page_contents(session_path, db_path, rets)
            task_info["logs"] += f"완료, 수집에 실패한 페이지들:{rets}\n"

            task_info["logs"] += "본문들에서 일정 수집중\n"
            rets = make_todo_list_from_page_contents(db_path, gemini_extractor)
            task_info["logs"] += f'완료, 추가한 일정들:{rets}'

            task_info["status"] = "complete"
            task_info["result"] = rets
    except Exception as e:
        task_info["status"] = "error"
        task_info["result"] = f"error: {e}"
    finally:
        sys.stderr = original_stderr

# [접수 툴] 호출 즉시 0.1초 만에 ID만 뱉고 종료 (타임아웃 절대 안 걸림)
@mcp.tool()
async def run_extraction_db(session_path:str, db_path:str) -> dict:
    """
    db에 origin_urls 목록에서 일정을 수집해 todo_list에 저장합니다.

    Args:
        session_path: 세션정보가 저장된 파일의 path
        db_path: db경로
    Returns:
        dict:
            task_id: 태스크id(태스크 결과를 조회할때 씀)
            message: 태스크 정보
    """
    task_id = str(uuid.uuid4())
    crawl_tasks[task_id] = {"status": "running", "logs": ""}
    
    asyncio.create_task(_run_extraction(task_id, db_path, session_path))
    
    return {"task_id": task_id, "message": "일정수집이 백그라운드에서 시작되었습니다."}

# 에이전트가 "다 됐어?"라고 물어볼 때 답해주는 툴 (즉시 응답)
@mcp.tool()
async def run_extraction_db_status(task_id: str) -> dict:
    """
    get_sub_urls_by_click_tool_db의 진행상태를 확인합니다

    Args:
        task_id: 작업 실행시 태스크id
    Returns:
        작업결과
    """
    if task_id not in crawl_tasks:
        return {"status": "not_found", "message": "존재하지 않는 작업 ID입니다."}
    
    task_info = crawl_tasks[task_id]
    return task_info

if __name__ == "__main__":
    mcp.run()
