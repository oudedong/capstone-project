from mcp.server.fastmcp import FastMCP
from browser_crawler import request_to_user, get_page, get_sub_urls_by_click_db, get_sub_urls_by_click_set, populate_page_contents

mcp = FastMCP("browser_tools")


@mcp.tool()
async def request_to_user_tool(request_url: str) -> str:
    """
    처리하기 힘든 특정 URL(로그인 페이지 등)에 대해 사용자에게 처리를 요청합니다.
    사용자가 브라우저에서 직접 처리하면 결과를 세션에 저장합니다.

    Args:
        request_url: 사용자에게 요청할 URL
    Returns:
        current_url: 현재 페이지 URL
        intended_url: 처음에 접근하려한 URL
        is_intended_url: 의도한 페이지로 접근했는지 여부
        current_page_title: 현재 페이지 제목
    """
    return await request_to_user(request_url)


@mcp.tool()
async def get_page_tool(url: str) -> str:
    """
    URL 페이지를 가져와 HTML을 추출하고, 정보들을 JSON 형태로 반환합니다.

    Args:
        url: 페이지 URL
    Returns:
        current_url: 현재 페이지 URL
        current_page_title: 현재 페이지 제목
        content: 현재 페이지 내용 (후처리됨: 불필요 태그·공백 제거)
        intended_url: 접근하려 했던 URL
        is_intended_url: 현재 페이지가 접근하려 했던 페이지인지 여부
    """
    return await get_page(url)


@mcp.tool()
async def get_sub_urls_by_click_tool_db(url: str, db_path:str, depth: int = 1) -> list[dict]:
    """
    페이지에서 클릭 가능한 요소들을 클릭해보며 이동되는 URL들을 수집합니다.
    페이지 내 iframe도 포함하여 탐색합니다.

    Args:
        url: 탐색을 시작할 페이지 URL
        db_path: db경로
        depth: URL 수집 깊이 (기본값: 1, 0이면 무제한)
    Returns:
        list of dict:
            url: 이동된 페이지의 URL
            title: 이동된 페이지의 제목
    """
    return await get_sub_urls_by_click_db(url, db_path, depth)

@mcp.tool()
async def get_sub_urls_by_click_tool_set(url: str, depth: int = 1) -> list[dict]:
    """
    페이지에서 클릭 가능한 요소들을 클릭해보며 이동되는 URL들을 수집합니다.
    페이지 내 iframe도 포함하여 탐색합니다.

    Args:
        url: 탐색을 시작할 페이지 URL
        depth: URL 수집 깊이 (기본값: 1, 0이면 무제한)
    Returns:
        list of dict:
            url: 이동된 페이지의 URL
            title: 이동된 페이지의 제목
    """
    return await get_sub_urls_by_click_set(url, depth)

@mcp.tool()
async def populate_page_contents_tool(db_path: str) -> str:
    """
    DB에 저장된 URL들 중 본문이 수집되지 않은 페이지들을 방문하여 본문을 일괄 수집합니다.

    Args:
        db_path: 데이터베이스 파일 경로
    Returns:
        수집 결과 메시지
    """
    return await populate_page_contents(db_path)


if __name__ == "__main__":
    mcp.run()
