from mcp.server.fastmcp import FastMCP
from my_scrapper import request_to_user, get_page, get_sub_urls_by_click_set
from my_scrapper import Redirected_page_urls, Try_login_solver
from schedule_db.crawl import *
from functools import wraps
import json

mcp = FastMCP("browser_tools")

# JSON 변환 데코레이터
def to_json(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        return json.dumps(result, ensure_ascii=False, indent=2)
    return wrapper

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
    r_db = Redirected_page_urls([Try_login_solver(session_path, login_db)])
    return await r_db.try_solve(redirected_url)

@mcp.tool()
@to_json
async def get_page_tool(session_path: str, url: str) -> str:
    """
    URL 페이지를 가져와 HTML을 추출하고, 정보들을 JSON 형태로 반환합니다.

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


@mcp.tool(task=True)
@to_json
async def get_sub_urls_by_click_tool_db(session_path:str, url: str, db_path:str, depth: int = 1) -> list[dict]:
    """
    페이지에서 클릭 가능한 요소들을 클릭해보며 이동되는 URL들을 수집합니다.
    페이지 내 iframe도 포함하여 탐색합니다.

    Args:
        session_path: 세션정보가 저장된 파일의 path
        url: 탐색을 시작할 페이지 URL
        db_path: db경로
        depth: URL 수집 깊이 (기본값: 1, 0이면 무제한)
    Returns:
        list of dict:
            url: 이동된 페이지의 URL
            title: 이동된 페이지의 제목
    """
    return await get_sub_urls_by_click_db(session_path, url, db_path, depth)

@mcp.tool(task=True)
@to_json
async def get_sub_urls_by_click_tool_set(session_path:str, url: str, depth: int = 1) -> list[dict]:
    """
    페이지에서 클릭 가능한 요소들을 클릭해보며 이동되는 URL들을 수집합니다.
    페이지 내 iframe도 포함하여 탐색합니다.
    DB내용은 탐색시 참조하지 않음

    Args:
        session_path: 세션정보가 저장된 파일의 path
        url: 탐색을 시작할 페이지 URL
        depth: URL 수집 깊이 (기본값: 1, 0이면 무제한)
    Returns:
        list of dict:
            url: 이동된 페이지의 URL
            title: 이동된 페이지의 제목
    """
    return await get_sub_urls_by_click_set(session_path, url, None, depth)

@mcp.tool()
@to_json
async def collect_page_contents_tool(session_path:str,db_path: str) -> str:
    """
    DB에 저장된 URL들 중 본문이 수집되지 않은 페이지들을 방문하여 본문을 일괄 수집해 db에 저장합니다.

    Args:
        db_path: 데이터베이스 파일 경로
        session_path: 세션정보가 저장된 파일의 path
    Returns:
        수집에 실패한 페이지들
    """
    return await collect_page_contents(session_path,db_path)


if __name__ == "__main__":
    mcp.run()
