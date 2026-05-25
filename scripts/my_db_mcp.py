from mcp.server.fastmcp import FastMCP
from schedule_db.db import *
from schedule_db.crawl import insert_origin_url_check_redirection
from functools import wraps
import json

mcp = FastMCP("DB_tools")


# JSON 변환 데코레이터
def to_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return json.dumps(result, ensure_ascii=False, indent=2)
    return wrapper

# ── 초기화 ────────────────────────────────────────────────────────────────────

@mcp.tool()
def init_db_tool(path: str) -> str:
    """
    일정 관리 데이터베이스 파일을 초기화하고 필요한 테이블들을 생성합니다.

    Args:
        path: SQLite 데이터베이스 파일이 생성될 경로
    Returns:
        성공 메시지 또는 에러 메시지
    """
    return init_db(path)


# ── 삽입 ──────────────────────────────────────────────────────────────────────

@mcp.tool()
@to_json
async def insert_db_source_urls(path: str, url: str, summary: str) -> str:
    """
    일정 관리의 근거가 되는 원본 출처 URL과 요약 정보를 origin_urls에 추가합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 출처 웹사이트 URL
        summary: 해당 URL 콘텐츠에 대한 요약 설명(직접확인하거나, 사용자한테 물어보기!)
    Return: 삽입결과, 만약 redirected_urls가 존재하면 해당 url은 리다이렉션 처리가 필요합니다.
    """
    return await insert_origin_url_check_redirection(path, url, summary)

@mcp.tool()
@to_json
def insert_db_page_urls(path: str, url: str, title: str) -> str:
    """
    일정 안내 페이지의 URL을 page_urls에 추가 합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 수집된 세부 일정 페이지 URL
        title: 수집된 페이지의 제목
    """
    return insert_page_url(path, url, title)

@mcp.tool()
@to_json
def insert_db_todo_list(path: str, url: str, content: str, due_date: str) -> str:
    """
    구체적인 할 일(일정) 정보를 todo_list에 추가합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 해당 일정이 공지된 출처 URL
        content: 일정의 구체적인 내용 (예: '보고서 제출')
        due_date: 마감 기한 (형식: YYYY-MM-DD HH:MM)
    """
    return insert_todo(path, url, content, due_date)

@mcp.tool()
@to_json
def insert_db_login_urls(path:str, login_url:str, 
                        css_path_id:str, css_path_pw:str, 
                        login_id:str, login_pw:str) -> str:
    """
    로그인페이지와 로그인방법을 login_urls에 추가합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 로그인페이지 url
        css_path_id: 아이디입력창 css선택자
        css_path_pw: 비밀번호입력창 css선택자
        login_id: 아이디
        login_pw: 비번
    """
    return insert_login_urls(path, login_url, css_path_id, css_path_pw, login_id, login_pw)


# ── 총정리 ────────────────────────────────────────────────────────────────────


# ── 조회 ──────────────────────────────────────────────────────────────────────

@mcp.tool()
@to_json
def get_db_todo_list_diff(path: str) -> str:
    """
    todo_list에서 갱신이전, 갱신이후 목록을 가져와 보여줍니다.
    Args:
        path: 데이터베이스 파일 경로
    """
    return get_todo_list_diff(path)

@mcp.tool()
@to_json
def get_db_origin_urls(path: str) -> str:
    """
    요약된 메인 웹사이트나 정보의 근거가 되는 URL 목록을 가져옵니다.

    Args:
        path: 데이터베이스 파일 경로
    """
    return get_origin_urls(path)

@mcp.tool()
@to_json
def get_db_page_urls(path: str, refresh=2) -> str: ############################################ 수정필요... 
    """
    확인이 필요한(또는 특정 날짜 이전에 확인한) 페이지 URL 목록을 가져옵니다.
    가져온 행들의 마지막 확인 시간(last_check)은 자동으로 현재 시간으로 갱신됩니다.

    Args:
        path: 데이터베이스 파일 경로
        refresh=2: 마지막 확인일 ex) 2이면 갱신일이 2일전 이상인 목록.
    """
    return get_page_urls(path, refresh)

@mcp.tool()
@to_json
def get_db_todo_list_all(path: str) -> str:
    """전체 할 일 목록(todo_list)을 조회하여 JSON 형식으로 반환합니다."""
    return get_todo_list_all(path)

@mcp.tool()
@to_json
def get_db_todo_list_done(path: str) -> str:
    """완료된 일정들을 조회하여 JSON 형식으로 반환합니다."""
    return get_todo_list_done(path)

@mcp.tool()
@to_json
def get_db_todo_list_overdue(path: str) -> str:
    """기한이 지난 완료되지 않은 일정들을 조회하여 JSON 형식으로 반환합니다."""
    return get_todo_list_overdue(path)

@mcp.tool()
@to_json
def get_db_unprocessed_page_contents(path: str) -> str:
    """처리되지 않은 페이지 본문 목록을 조회하여 JSON 형식으로 반환합니다."""
    return get_unprocessed_page_contents(path)

@mcp.tool()
@to_json
def get_db_unprocessed_redirected_urls(path:str):
    """처리되지 않은(target_url이 없는) 리다이렉션 url들을 가져옵니다"""
    return get_unprocessed_redirected_urls(path)

# ── 업데이트 ──────────────────────────────────────────────────────────────────

@mcp.tool()
@to_json
def check_done_todo_list_tool(path: str, ids: list[int]) -> str:
    """
    요청한 ID들에 해당하는 일정들을 완료(is_completed=1) 상태로 변경합니다.

    Args:
        path: 데이터베이스 파일 경로
        ids: 완료 처리할 일정들의 ID 목록
    """
    return check_done_todo_list(path, ids)

@mcp.tool()
@to_json
def mark_db_page_content_processed(path: str, ids: list[int]) -> str:
    """
    요청한 ID들에 해당하는 페이지 본문들을 처리 완료(is_processed=1) 상태로 변경합니다.

    Args:
        path: 데이터베이스 파일 경로
        ids: 처리 완료할 페이지 본문들의 ID 목록
    """
    return mark_page_content_processed(path, ids)

@mcp.tool()
@to_json
def add_db_target_url_to_redirected_urls(path: str, redirected_url:str, target_url:str):
    """
    redirected_urls 테이블에 redirected_url에 대해, target_url을 업데이트 합니다
    
    Args:
        redirected_url: 리다이렉션 되는 페이지의 url
        target_url: 리다이렉션을 해결하기 위한 페이지의 url
    
    """
    return add_target_url_to_redirected_urls(path, redirected_url, target_url)

# ── 삭제 ──────────────────────────────────────────────────────────────────────

@mcp.tool()
@to_json
def delete_done_todo_list_tool(path: str) -> str:
    """이미 완료(is_completed=1)된 일정들을 데이터베이스에서 삭제합니다."""
    return delete_done_todo_list(path)

@mcp.tool()
@to_json
def delete_overdue_todo_list_tool(path: str, only_completed: bool = True) -> str:
    """
    기한이 지난 일정들을 삭제합니다.

    Args:
        path: 데이터베이스 파일 경로
        only_completed: True일 경우 기한이 지나고 '완료된' 것만 삭제,
                        False일 경우 기한이 지난 '모든' 일정 삭제
    """
    return delete_overdue_todo_list(path, only_completed)

@mcp.tool()
@to_json
def delete_db_old_todo_list(path: str) -> str:
    """
    갱신되지 않은 일정들을 삭제합니다.
    Args:
        path: 데이터베이스 파일 경로
    """
    return delete_old_todo_list(path)

if __name__ == "__main__":
    mcp.run()