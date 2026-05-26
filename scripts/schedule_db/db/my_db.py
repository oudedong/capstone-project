import sqlite3
import datetime
from typing import Callable
import sys
# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _cursor_to_list_dict(cursor) -> list[dict]:
    """SQLite 커서 결과를 딕셔너리 리스트로 변환합니다."""
    colnames = cursor.description
    if not colnames:
        return []
    return [
        {colnames[i][0]: row[i] for i in range(len(colnames))}
        for row in cursor.fetchall()
    ]

def _db_execute(path: str, table: str,
                action_db: Callable[[str, str, Callable[[], str]], list[dict]],
                filter_func: Callable[[], str] = None,
                additional: Callable[..., None] = None) -> list[dict]:
    """DB 작업을 수행하고 결과를 딕셔너리로 반환하는 공통 래퍼입니다."""
    if additional is None:
        additional = lambda x, y: None

    conn = None
    try:

        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        action_db(cursor, table, filter_func) # 자원해제를 위해서 cursor을 제공해줌
        result = _cursor_to_list_dict(cursor) # 딕셔너리 형태로 변환
        additional(cursor, result)
        conn.commit()
        return result
    except Exception as e:
        print(f"DB 작업 중 에러 발생: {e}", file=sys.stderr)
        raise
    finally:
        if conn:
            conn.close()


# ── 초기화 ────────────────────────────────────────────────────────────────────

def init_db(path: str) -> str:
    """일정 관리 데이터베이스를 초기화하고 필요한 테이블들을 생성합니다."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    try: # todo_list에 is_fresh 추가됨!(갱신상태인지)
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS origin_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                summary TEXT
            );

            CREATE TABLE IF NOT EXISTS page_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT NULL,
                last_check TEXT
            );

            CREATE TABLE IF NOT EXISTS todo_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                content TEXT NOT NULL,
                is_completed BOOLEAN NOT NULL DEFAULT 0,
                due_date TEXT,
                is_fresh BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (url) REFERENCES page_urls (url) ON UPDATE CASCADE
            );

            CREATE TABLE IF NOT EXISTS page_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                content TEXT,
                is_processed BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (url) REFERENCES page_urls (url) ON DELETE CASCADE
            );
                             
            CREATE TABLE IF NOT EXISTS redirected_urls ( 
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redirected_url TEXT NOT NULL UNIQUE,  
                target_url TEXT
            );
            
            CREATE TABLE IF NOT EXISTS login_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login_url TEXT NOT NULL UNIQUE,
                css_path_id TEXT,
                css_path_pw TEXT,
                login_id TEXT,
                login_pw TEXT
            );
        ''')
        conn.commit()
        return "데이터베이스 초기화 성공"
    except Exception as e:
        return f"초기화 중 에러 발생: {e}"
    finally:
        conn.close()


# ── 삽입 ──────────────────────────────────────────────────────────────────────

def _insert(cursor, table: str, columns: list[str], values: list):
    """데이터베이스에 행을 삽입하고 삽입된 행의 ID를 반환하는 내부 함수입니다."""
    col_names = ', '.join(columns)
    placeholders = ', '.join(['?'] * len(values))
    sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) RETURNING *"
    try:
        cursor.execute(sql, values)
    except Exception as e:
        print(f"삽입 중 에러 발생: {e}", file=sys.stderr)
        raise

def _db_execute_insert(path: str, table: str, columns: list[str], values:list) -> list[dict]:
    def convert(cursor, table, filter_func):
        return _insert(cursor, table, columns, values)
    ret = _db_execute(path, table, convert)
    return ret

def insert_redirected_urls(path:str, redirected_url:str): ###################################
    """리다이렉트 url을 저장합니다."""
    return _db_execute_insert(path, 'redirected_urls', ['redirected_url'], [redirected_url])

def insert_origin_url(path: str, url: str, summary: str):
    """원천 페이지 URL과 페이지에 대한 간략한 설명을 저장하고 삽입내용을 반환합니다."""
    return _db_execute_insert(path, 'origin_urls', ['url', 'summary'], [url, summary])

def insert_page_url(path: str, url: str, title: str):
    """개별 일정 안내 페이지 URL과 제목을 저장하고 ID를 반환합니다."""
    return _db_execute_insert(path, 'page_urls', ['url', 'title'], [url, title])

def insert_todo(path: str, url: str, content: str, due_date: str):
    """할 일(일정) 정보를 추가합니다."""
    return _db_execute_insert(path, 'todo_list', ['url', 'content', 'due_date'], [url, content, due_date])

def insert_page_content(path: str, url: str, content: str):
    """페이지의 본문 내용을 저장합니다."""
    return _db_execute_insert(path, 'page_contents', ['url', 'content'], [url, content])


def insert_login_urls(path:str, login_url:str, 
                      css_path_id, css_path_pw, 
                      login_id, login_pw): #아이디,비번 직접 안쓰게 개선필요...
    """login_urls에 로그인 정보를 추가합니다"""
    return _db_execute_insert(path, 'login_urls', 
                              ['login_url', 'css_path_id', 'css_path_pw', 'login_id', 'login_pw'], 
                              [login_url, css_path_id, css_path_pw, login_id, login_pw])

# ── upsert ──────────────────────────────────────────────────────────────────────

def upsert_page_content(path: str, url: str, content: str):
    """페이지의 본문 내용을 저장 또는 업데이트 합니다."""
    _filter = lambda: f"WHERE url='{url}' "
    if _db_execute_get(path, 'page_contents', _filter):
        # 이미 있으면 삽입하지 말고 업데이트, is_processed도 초기화
        _db_execute_update(path, 'page_contents', 'content', content, _filter)
        return _db_execute_update(path, 'page_contents', 'is_processed', False, _filter) 

    return insert_page_content(path, url, content)

# ── 조회 ──────────────────────────────────────────────────────────────────────

def _get(cursor, table: str, filter_func: Callable[[], str] = None):
    """데이터베이스에서 정보를 조회하는 내부 함수입니다."""
    if filter_func is None:
        filter_func = lambda: ''

    query = f"SELECT * FROM {table} " + filter_func()
    cursor.execute(query)
    try:
        cursor.execute(query)
    except Exception as e:
        print(f"get 중 에러 발생: {e}", file=sys.stderr)
        raise

def _db_execute_get(path: str, table: str,
              filter_func: Callable[[], str] = None,
              additional: Callable[..., None] = None) -> list[dict]:
    return _db_execute(path, table, _get, filter_func, additional)

def get_origin_urls(path: str):
    """출처 URL 목록을 JSON으로 반환합니다."""
    return _db_execute_get(path, 'origin_urls')

def get_page_urls(path: str):
    """페이지 URL 목록을 JSON으로 반환합니다."""
    return _db_execute_get(path, 'page_urls')

def get_page_urls_to_check(path: str, refresh: int):
    """확인이 필요한(한번도 확인안함, 기한이 아직 안끝난 미완료 일정이 있음) 페이지 URL 목록을 JSON으로 반환합니다."""
    #refresh: 새로고침일, 0으로 하면 사용안함
    date_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    date_refresh = (datetime.datetime.now()-datetime.timedelta(days=refresh)).strftime('%Y-%m-%d %H:%M')

    def filter_func():
        ret = f"WHERE last_check IS NULL "
        if refresh > 0:
            ret += f"OR (last_check < '{date_refresh}' AND EXISTS (SELECT * FROM todo_list WHERE todo_list.url=page_urls.url AND todo_list.due_date >= '{date_now}')) "
        return ret

    return _db_execute_get(path, 'page_urls', filter_func)

_get_todo_list_base_filter = "WHERE is_fresh=1 AND due_date IS NOT NULL "

def get_todo_list_all(path: str):
    """전체 할 일 목록을 JSON으로 반환합니다."""
    return _db_execute_get(path, 'todo_list', lambda:_get_todo_list_base_filter)

def get_todo_list_going(path:str):
    """진행중인 일정목록을 JSON으로 반환합니다."""
    date_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    return _db_execute_get(path, 'todo_list', lambda:_get_todo_list_base_filter+f"AND due_date >= '{date_now}'")

def get_todo_list_done(path: str):
    """완료된 할 일 목록을 JSON으로 반환합니다."""
    return _db_execute_get(path, 'todo_list', lambda: f"{_get_todo_list_base_filter}AND is_completed=1 ")

def get_todo_list_overdue(path: str):
    """기한이 지나고 끝내지못한 할 일 목록을 JSON으로 반환합니다."""
    date_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    return _db_execute_get(path, 'todo_list', lambda: f"{_get_todo_list_base_filter}AND due_date < '{date_now}' AND is_completed=0")

def get_todo_list_diff(path:str): # 효율적이게 수정필요..
    """페이지별로 갱신이전, 이후 todo_list를 반환합니다."""
    todos = _db_execute_get(path, 'todo_list', lambda:"WHERE due_date IS NOT NULL ")
    temp = {}
    ret = {}
    for todo in todos:
        if temp.get(todo['url']) == None:
            temp[todo['url']] = {'fresh': [], 'old': []}
        to_append = None
        if todo['is_fresh']:
            to_append = temp[todo['url']]['fresh']
        else:
            to_append = temp[todo['url']]['old']
        to_append.append({'content':todo['content'],'is_completed':todo['is_completed'], 'due_date':todo['due_date']})
    for k in temp.keys():
        cur = temp[k]
        if len(cur['old']) <= 0:
            continue
        ret[k] = cur
    return ret
        
def get_unprocessed_page_contents(path: str):
    """처리되지 않은 페이지 본문 목록을 반환합니다."""
    return _db_execute_get(path, 'page_contents', lambda: "WHERE is_processed=0 ")

def get_redirected_urls(path:str, cur_url:str):
    """특정 리다이렉션 url에대해 target_url을 가져옵니다"""
    return _db_execute_get(path, 'redirected_urls', lambda: f"WHERE redirected_url='{cur_url}' ")

def get_unprocessed_redirected_urls(path:str):
    """처리되지 않은 리다이렉션 url들을 가져옵니다"""
    return _db_execute_get(path, 'redirected_urls', lambda: f"WHERE target_url IS NULL ")

def get_page_content(path:str, url:str):
    """특정페이지의 content를 가져옵니다"""
    return _db_execute_get(path, 'page_contents', lambda: f"WHERE url='{url}' ")


def get_db_stats(path: str) -> dict:
    """DB의 전체적인 통계 정보를 반환합니다."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    try:
        stats = {}
        # 전체 페이지 수
        cursor.execute("SELECT count(*) FROM page_urls")
        stats['total_pages'] = cursor.fetchone()[0]
        
        # 분석 완료된 본문 수
        cursor.execute("SELECT count(*) FROM page_contents WHERE is_processed=1")
        stats['processed_contents'] = cursor.fetchone()[0]
        
        # 전체 일정 수 (신선한 것만)
        cursor.execute("SELECT count(*) FROM todo_list WHERE is_fresh=1 AND due_date IS NOT NULL")
        stats['total_todos'] = cursor.fetchone()[0]
        
        # 완료된 일정 수
        cursor.execute("SELECT count(*) FROM todo_list WHERE is_fresh=1 AND is_completed=1")
        stats['completed_todos'] = cursor.fetchone()[0]
        
        return stats
    finally:
        conn.close()

def get_upcoming_todos(path: str, days: int = 7) -> list[dict]:
    """지정한 일수 이내로 남은 임박한 일정들을 가져옵니다."""
    date_limit = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
    date_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    
    def filter_func():
        return f"WHERE is_fresh=1 AND is_completed=0 AND due_date >= '{date_now}' AND due_date <= '{date_limit}' ORDER BY due_date ASC"
    
    return _db_execute_get(path, 'todo_list', filter_func)

# ── 업데이트 ──────────────────────────────────────────────────────────────────

def _update(cursor, table: str, column: str, val, 
            filter_func: Callable[[], str] = None):
    """데이터베이스 행을 업데이트하는 내부 함수입니다."""
    if filter_func is None:
        filter_func = lambda: ''

    val_str = f"'{val}'" if isinstance(val, str) else str(val) # 문자열에는 알아서 ''씌워줌!!!!
    query = f"UPDATE {table} SET {column}={val_str} {filter_func()} RETURNING *"
    try:
        cursor.execute(query)
    except Exception as e:
        print(f"db업데이트중 오류발생: {str(e)}", file=sys.stderr)
        raise

def _db_execute_update(path: str, table: str, column: str, val,
                 filter_func: Callable[[], str] = None) -> list[dict]:
    def _action(cursor, table:str, filter):
        return _update(cursor, table, column, val, filter)
    return _db_execute(path, table, _action, filter_func)

def check_done_todo_list(path: str, ids: list[int]):
    """지정한 ID들의 할 일을 완료 상태로 변경합니다."""
    rets = []
    for row_id in ids:
        ret = _db_execute_update(path, 'todo_list', 'is_completed', 1,
                                lambda rid=row_id: f'WHERE id={rid} ')
        rets += ret
    return rets

def mark_page_content_processed(path: str, ids: list[int]):
    """지정한 ID들의 페이지 본문을 처리 완료 상태로 변경합니다."""
    rets = []
    for row_id in ids:
        ret = _db_execute_update(path, 'page_contents', 'is_processed', 1,
                                lambda rid=row_id: f'WHERE id={rid} ')
        rets += ret
    return rets

def check_page_urls(path: str, ids: list[int]):
    """지정한 ID들의 페이지 url들의 방문시간을 갱신합니다."""
    rets = []
    date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for row_id in ids:
        ret = _db_execute_update(path, 'page_urls', 'last_check', f"{date}",
                                lambda rid=row_id: f'WHERE id={rid} ')
        rets += ret
    return rets

def add_target_url_to_redirected_urls(path: str, r_url:str, t_url:str):
    """redirected_urls 테이블에 redirected_url에 대해, target_url을 업데이트 합니다"""
    if len(get_redirected_urls(path, r_url)) < 1:
        raise Exception(f"redirected_urls 테이블에 {r_url}이 없습니다, 먼저 추가해주세요")
    ret = _db_execute_update(path, 'redirected_urls', 'target_url', t_url, lambda: f"WHERE redirected_url='{r_url}' ")
    return ret

def defresh_todo_list(path:str, url:str):
    """url에 해당하는 todo_list들의 갱신상태를 오래됨으로 바꿉니다"""
    ret = _db_execute_update(path, 'todo_list', 'is_fresh', 0, lambda: f"WHERE url='{url}' ")
    return ret

# ── 삭제 ──────────────────────────────────────────────────────────────────────

def _delete(cursor, table: str, filter_func: Callable[[], str]) -> list[dict]:
    """데이터베이스에서 행을 삭제하는 내부 함수입니다."""
    query = f"DELETE FROM {table} {filter_func()} RETURNING *"
    try:
        cursor.execute(query)
    except Exception as e:
        print(f"db삭제중 오류발생: {str(e)}", file=sys.stderr)
        raise

def _db_execute_delete(path: str, table: str, filter_func: Callable[[], str] = None) -> list[dict]:
    return _db_execute(path, table, _delete, filter_func)

def delete_done_todo_list(path: str) -> str:
    """완료된 할 일들을 삭제합니다."""
    return _db_execute_delete(path, 'todo_list', lambda: "WHERE is_completed=1 ")

def delete_overdue_todo_list(path: str, only_completed: bool = True):
    """기한이 지난 할 일들을 삭제합니다."""
    def filter_func():
        w = "WHERE due_date < datetime('now', 'localtime') "
        if only_completed:
            w += "AND is_completed=1 "
        return w
    return _db_execute_delete(path, 'todo_list', filter_func)

def delete_old_todo_list(path:str):
    return _db_execute_delete(path, 'todo_list', lambda: "WHERE is_fresh=0 ")