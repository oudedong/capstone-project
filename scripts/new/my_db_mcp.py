from mcp.server.fastmcp import FastMCP
from my_db import (
    init_db,
    insert_origin_url, insert_page_url, insert_todo,
    get_origin_urls, get_page_urls,
    get_todo_list_all, get_todo_list_done, get_todo_list_overdue,
    check_done_todo_list,
    delete_done_todo_list, delete_overdue_todo_list, delete_done_page_urls,
)

mcp = FastMCP("DB_tools")


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
def insert_db_source_urls(path: str, url: str, summary: str) -> str:
    """
    일정 관리의 근거가 되는 원본 출처 URL과 요약 정보를 추가합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 출처 웹사이트 URL
        summary: 해당 URL 콘텐츠에 대한 요약 설명
    """
    return insert_origin_url(path, url, summary)

@mcp.tool()
def insert_db_page_urls(path: str, url: str, title: str) -> str:
    """
    수집된 개별 일정 안내 페이지의 URL을 저장합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 수집된 세부 일정 페이지 URL
        title: 수집된 페이지의 제목
    """
    return insert_page_url(path, url, title)

@mcp.tool()
def insert_db_todo_list(path: str, url: str, content: str, due_date: str) -> str:
    """
    구체적인 할 일(일정) 정보를 추가합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 해당 일정이 공지된 출처 URL
        content: 일정의 구체적인 내용 (예: '보고서 제출')
        due_date: 마감 기한 (형식: YYYY-MM-DD HH:MM)
    """
    return insert_todo(path, url, content, due_date)


# ── 조회 ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_db_origin_urls(path: str) -> str:
    """
    요약된 메인 웹사이트나 정보의 근거가 되는 URL 목록을 가져옵니다.

    Args:
        path: 데이터베이스 파일 경로
    """
    return get_origin_urls(path)

@mcp.tool()
def get_db_page_urls(path: str, date: str = None) -> str:
    """
    확인이 필요한(또는 특정 날짜 이전에 확인한) 페이지 URL 목록을 가져옵니다.
    가져온 행들의 마지막 확인 시간(last_check)은 자동으로 현재 시간으로 갱신됩니다.

    Args:
        path: 데이터베이스 파일 경로
        date: 기준 날짜 (기본값: 현재 시간). 이 날짜보다 이전에 확인한 페이지만 조회합니다.
    """
    return get_page_urls(path, date)

@mcp.tool()
def get_db_todo_list_all(path: str) -> str:
    """전체 할 일 목록(todo_list)을 조회하여 JSON 형식으로 반환합니다."""
    return get_todo_list_all(path)

@mcp.tool()
def get_db_todo_list_done(path: str) -> str:
    """완료된 일정들을 조회하여 JSON 형식으로 반환합니다."""
    return get_todo_list_done(path)

@mcp.tool()
def get_db_todo_list_overdue(path: str) -> str:
    """기한이 지난 일정들을 조회하여 JSON 형식으로 반환합니다."""
    return get_todo_list_overdue(path)


# ── 업데이트 ──────────────────────────────────────────────────────────────────

@mcp.tool()
def check_done_todo_list_tool(path: str, ids: list[int]) -> str:
    """
    요청한 ID들에 해당하는 일정들을 완료(is_completed=1) 상태로 변경합니다.

    Args:
        path: 데이터베이스 파일 경로
        ids: 완료 처리할 일정들의 ID 목록
    """
    return check_done_todo_list(path, ids)


# ── 삭제 ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def delete_done_todo_list_tool(path: str) -> str:
    """이미 완료(is_completed=1)된 일정들을 데이터베이스에서 삭제합니다."""
    return delete_done_todo_list(path)

@mcp.tool()
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
def delete_done_page_urls_tool(path: str) -> str:
    """연결된 할 일(todo_list)이 하나도 없는 페이지 URL들을 정리(삭제)합니다."""
    return delete_done_page_urls(path)


if __name__ == "__main__":
    mcp.run()
