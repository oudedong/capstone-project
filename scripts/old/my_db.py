# scripts/my_assistant.py
from fastmcp import FastMCP
import json
import sqlite3
from typing import Callable
import datetime

# 1. 서버 초기화
mcp = FastMCP("DB_tools")

@mcp.tool()
def init_db(path: str) -> str:
    """
    일정 관리 데이터베이스 파일을 초기화하고 필요한 테이블들을 생성합니다.

    Args:
        path: SQLite 데이터베이스 파일이 생성될 경로
    Returns:
        성공 메시지 또는 에러 메시지
    """
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    try:
        cursor.executescript('''
        CREATE TABLE IF NOT EXISTS origin_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            summary TEXT
        );
                         
        CREATE TABLE IF NOT EXISTS page_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            last_check TEXT
        );

        CREATE TABLE IF NOT EXISTS todo_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            content TEXT NOT NULL,
            is_completed BOOLEAN NOT NULL DEFAULT 0,
            due_date TEXT,
            FOREIGN KEY (url) REFERENCES page_urls (url) ON UPDATE CASCADE
        );
    ''')
        conn.commit()
        return "데이터베이스 초기화 성공"
    except Exception as e:
        return f"초기화 중 에러 발생: {e}"
    finally:
        conn.close()

#######################################################################################
# 내부 헬퍼 함수
#######################################################################################

def get_from_cursor_to_listDict(cursor) -> list[dict]:
    """SQLite 커서의 결과를 딕셔너리 리스트 형태로 변환합니다."""
    colnames = cursor.description
    if not colnames:
        return []
    rows = cursor.fetchall()
    rets = []
    for row in rows:
        cur_dict = {}
        for i in range(len(colnames)):
            col = colnames[i][0]
            val = row[i]
            cur_dict[col] = val
        rets.append(cur_dict)
    return rets

def db_with_default_except_handle(path: str, table: str, 
                                  action_db: Callable[[str, str, Callable[[], str]], list[dict]],
                                  filter_func: Callable[[], str] = None,
                                  additional: Callable[..., None] = None) -> str:
    """DB 작업을 수행하고 예외를 처리하며 결과를 JSON으로 반환하는 공통 래퍼 함수입니다."""
    if additional is None: 
        additional = lambda x, y: None
    
    conn = None
    try:
        result = action_db(path, table, filter_func)

        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        additional(cursor, result)
        conn.commit()
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return f"DB 작업 중 에러 발생: {e}"
    finally:
        if conn:
            conn.close()
#######################################################################################
# 삽입관련
#######################################################################################
def insert_db(path: str, table: str, columns: list[str], values: list) -> str:
    """데이터베이스에 행을 삽입하는 내부 함수입니다."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    
    col_names = ', '.join(columns)
    placeholders = ', '.join(['?'] * len(values))
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        
    try:
        cursor.execute(sql, values)
        conn.commit()
        return f"{table} 테이블에 데이터 저장 완료"
    except Exception as e:
        return f"삽입 중 에러 발생: {e}"
    finally:
        conn.close()
@mcp.tool()
def insert_db_source_urls(path: str, url: str, summary: str) -> str:
    """
    일정 관리의 근거가 되는 원본 출처 URL과 요약 정보를 추가합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 출처 웹사이트 URL
        summary: 해당 URL 콘텐츠에 대한 요약 설명
    """
    return insert_db(path, 'origin_urls', ['url', 'summary'], [url, summary])

@mcp.tool()
def insert_db_page_urls(path: str, url: str) -> str:
    """
    수집된 개별 일정 안내 페이지의 URL을 저장합니다.

    Args:
        path: 데이터베이스 파일 경로
        url: 수집된 세부 일정 페이지 URL
    """
    return insert_db(path, 'page_urls', ['url'], [url])

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
    return insert_db(path, 'todo_list', ['url', 'content', 'due_date'], [url, content, due_date])

#############################################################################################
# db get부분
#############################################################################################
def get_db(path: str, table: str, filter_func: Callable[..., str] = None) -> list[dict]:
    """데이터베이스에서 정보를 조회하는 내부 함수입니다."""
    if filter_func is None:
        filter_func = lambda : ''

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    query = f"SELECT * FROM {table} "
    query += filter_func()

    cursor.execute(query)
    ret = get_from_cursor_to_listDict(cursor)
    conn.commit()
    conn.close()
    return ret

def get_db_with_default_except_handle(path:str, table:str, filter_func:Callable[[],str]=None, additional:Callable[...,None]=None) -> str:
    return db_with_default_except_handle(path, table, get_db, filter_func, additional)

def get_origin_urls_with_default_except_handle(path:str, filter_func:Callable[[],str]=None) -> str:
    return get_db_with_default_except_handle(path, 'origin_urls', filter_func)
@mcp.tool()
def get_db_origin_urls(path: str) -> str:
    """
    요약된 메인 웹사이트나 정보의 근거가 되는 URL 목록을 가져옵니다.

    Args:
        path: 데이터베이스 파일 경로
    """
    return get_origin_urls_with_default_except_handle(path)

def get_page_urls_with_default_except_handle(path:str, filter_func:Callable[[],str]=None, additional:Callable[...,None]=None) -> str:
    return get_db_with_default_except_handle(path, 'page_urls', filter_func, additional)
@mcp.tool()
def get_db_page_urls(path: str, date: str = None) -> str:
    """
    확인이 필요한(또는 특정 날짜 이전에 확인한) 페이지 URL 목록을 가져옵니다.
    가져온 행들의 마지막 확인 시간(last_check)은 자동으로 현재 시간으로 갱신됩니다.

    Args:
        path: 데이터베이스 파일 경로
        date: 기준 날짜 (기본값: 현재 시간). 이 날짜보다 이전에 확인한 페이지만 조회합니다.
    """
    if date is None:
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        
    def filter_func() -> str:
        return f"WHERE last_check IS NULL OR last_check < '{date}' "
    def check_callback(cursor, results: list[dict]):
        for result in results:
            cursor.execute("UPDATE page_urls SET last_check=datetime('now', 'localtime') WHERE id=?", (result['id'],))
    return get_page_urls_with_default_except_handle(path, filter_func, check_callback)

def get_todoList_with_default_except_handle(path:str, filter_func:Callable[[],str]=None) -> str:
    return get_db_with_default_except_handle(path, 'todo_list', filter_func)
@mcp.tool()
def get_db_todo_list_all(path: str) -> str:
    """
    전체 할 일 목록(todo_list)을 조회하여 JSON 형식으로 반환합니다.
    """
    return get_todoList_with_default_except_handle(path)
@mcp.tool()
def get_db_todo_list_done(path: str) -> str:
    """
    전체 할 일 목록(todo_list)중 완료된 일정들을 조회하여 JSON 형식으로 반환합니다.
    """
    def filter_func() -> str:
        return "WHERE is_completed=1 "

    return get_todoList_with_default_except_handle(path, filter_func)
@mcp.tool()
def get_db_todo_list_overdue(path: str) -> str:
    """
    전체 할 일 목록(todo_list)중 기한이 지난 일정들을 조회하여 JSON 형식으로 반환합니다.
    """
    def filter_func() -> str:
        return "WHERE due_date < datetime('now', 'localtime')"

    return get_todoList_with_default_except_handle(path, filter_func)

#############################################################################################
# db 업데이트 부분
#############################################################################################
def update_db(path: str, table: str, column: str, val, filter_func: Callable[..., str] = None) -> list[dict]:
    """데이터베이스의 정보를 업데이트하는 내부 함수입니다."""
    if filter_func is None:
        filter_func = lambda : ''

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    query = f"UPDATE {table} SET {column}="
    if isinstance(val, str):
        val = f"'{val}'"
    query += f"{val} "
    query += filter_func()
    query += " RETURNING *"

    cursor.execute(query)
    ret = get_from_cursor_to_listDict(cursor)
    conn.commit()
    conn.close()
    return ret
def update_db_with_default_except_handle(path: str, table: str, column: str, val, filter_func: Callable[[], str] = None, additional: Callable[..., None] = None) -> str:
    def _update_db(p, t, f):
        return update_db(p, t, column, val, f)
    return db_with_default_except_handle(path, table, _update_db, filter_func, additional)
@mcp.tool()
def check_done_todo_list(path: str, ids: list[int]) -> str:
    """
    요청한 ID들에 해당하는 일정들을 완료(is_completed=1) 상태로 변경합니다.

    Args:
        path: 데이터베이스 파일 경로
        ids: 완료 처리할 일정들의 ID 목록
    """
    def get_filter(row_id):
        return lambda : f'WHERE id={row_id} '
    
    rets = []
    for row_id in ids:
        # 각 업데이트 결과를 리스트에 모읍니다.
        res_json = update_db_with_default_except_handle(path, 'todo_list', 'is_completed', 1, get_filter(row_id))
        try:
            rets.append(json.loads(res_json))
        except:
            rets.append(res_json)
    return json.dumps(rets, ensure_ascii=False)
#############################################################################################
# db 삭제부분
#############################################################################################
def delete_db(path: str, table: str, filter_func: Callable[..., str]) -> list[dict]:
    """데이터베이스에서 정보를 삭제하는 내부 함수입니다."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    query = f"DELETE FROM {table} "
    query += filter_func()
    query += " RETURNING *"

    cursor.execute(query)
    ret = get_from_cursor_to_listDict(cursor)
    conn.commit()
    conn.close()
    return ret
@mcp.tool()
def delete_done_todo_list(path: str) -> str:
    """
    이미 완료(is_completed=1)된 일정들을 데이터베이스에서 삭제합니다.
    """
    def filter_func():
        return "WHERE is_completed=1 "
    return db_with_default_except_handle(path, 'todo_list', delete_db, filter_func)
@mcp.tool()
def delete_overdue_todo_list(path: str, only_completed: bool = True) -> str:
    """
    기한이 지난 일정들을 삭제합니다.

    Args:
        path: 데이터베이스 파일 경로
        only_completed: True일 경우 기한이 지나고 '완료된' 것만 삭제, False일 경우 기한이 지난 '모든' 일정 삭제
    """
    def get_filter():
        w = "WHERE due_date < datetime('now', 'localtime') "
        if only_completed:
            w += "AND is_completed=1 "
        return w
    return db_with_default_except_handle(path, 'todo_list', delete_db, get_filter)
@mcp.tool()
def delete_done_page_urls(path: str) -> str:
    """
    연결된 할 일(todo_list)이 하나도 없는 페이지 URL들을 정리(삭제)합니다.
    """
    def filter_func():
        return "WHERE NOT EXISTS (SELECT 1 FROM todo_list WHERE todo_list.url = page_urls.url) "
    return db_with_default_except_handle(path, 'page_urls', delete_db, filter_func)

if __name__ == "__main__":
    mcp.run()
