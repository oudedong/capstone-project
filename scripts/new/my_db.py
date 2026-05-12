import json
import sqlite3
import datetime
from typing import Callable


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
                additional: Callable[..., None] = None) -> str:
    """DB 작업을 수행하고 예외를 처리하며 결과를 JSON으로 반환하는 공통 래퍼입니다."""
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


# ── 초기화 ────────────────────────────────────────────────────────────────────

def init_db(path: str) -> str:
    """일정 관리 데이터베이스를 초기화하고 필요한 테이블들을 생성합니다."""
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
                title TEXT NULL,
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


# ── 삽입 ──────────────────────────────────────────────────────────────────────

def _insert(path: str, table: str, columns: list[str], values: list) -> str:
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

def insert_origin_url(path: str, url: str, summary: str) -> str:
    """원본 출처 URL과 요약 정보를 추가합니다."""
    return _insert(path, 'origin_urls', ['url', 'summary'], [url, summary])

def insert_page_url(path: str, url: str, title: str) -> str:
    """개별 일정 안내 페이지 URL과 제목을 저장합니다."""
    return _insert(path, 'page_urls', ['url', 'title'], [url, title])

def insert_todo(path: str, url: str, content: str, due_date: str) -> str:
    """할 일(일정) 정보를 추가합니다."""
    return _insert(path, 'todo_list', ['url', 'content', 'due_date'], [url, content, due_date])


# ── 조회 ──────────────────────────────────────────────────────────────────────

def _get(path: str, table: str, filter_func: Callable[[], str] = None) -> list[dict]:
    """데이터베이스에서 정보를 조회하는 내부 함수입니다."""
    if filter_func is None:
        filter_func = lambda: ''

    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    query = f"SELECT * FROM {table} " + filter_func()
    cursor.execute(query)
    ret = _cursor_to_list_dict(cursor)
    conn.commit()
    conn.close()
    return ret

def _get_json(path: str, table: str,
              filter_func: Callable[[], str] = None,
              additional: Callable[..., None] = None) -> str:
    return _db_execute(path, table, _get, filter_func, additional)

def get_origin_urls(path: str) -> str:
    """출처 URL 목록을 JSON으로 반환합니다."""
    return _get_json(path, 'origin_urls')

def get_page_urls(path: str, date: str = None) -> str:
    """확인이 필요한 페이지 URL 목록을 반환하고, last_check를 현재 시간으로 갱신합니다."""
    if date is None:
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    def filter_func() -> str:
        return f"WHERE last_check IS NULL OR last_check < '{date}' "

    def update_last_check(cursor, results: list[dict]):
        for result in results:
            cursor.execute(
                "UPDATE page_urls SET last_check=datetime('now', 'localtime') WHERE id=?",
                (result['id'],)
            )

    return _get_json(path, 'page_urls', filter_func, update_last_check)

def get_todo_list_all(path: str) -> str:
    """전체 할 일 목록을 JSON으로 반환합니다."""
    return _get_json(path, 'todo_list')

def get_todo_list_done(path: str) -> str:
    """완료된 할 일 목록을 JSON으로 반환합니다."""
    return _get_json(path, 'todo_list', lambda: "WHERE is_completed=1 ")

def get_todo_list_overdue(path: str) -> str:
    """기한이 지난 할 일 목록을 JSON으로 반환합니다."""
    return _get_json(path, 'todo_list', lambda: "WHERE due_date < datetime('now', 'localtime')")


# ── 업데이트 ──────────────────────────────────────────────────────────────────

def _update(path: str, table: str, column: str, val,
            filter_func: Callable[[], str] = None) -> list[dict]:
    """데이터베이스 행을 업데이트하는 내부 함수입니다."""
    if filter_func is None:
        filter_func = lambda: ''

    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    val_str = f"'{val}'" if isinstance(val, str) else str(val)
    query = f"UPDATE {table} SET {column}={val_str} {filter_func()} RETURNING *"
    cursor.execute(query)
    ret = _cursor_to_list_dict(cursor)
    conn.commit()
    conn.close()
    return ret

def _update_json(path: str, table: str, column: str, val,
                 filter_func: Callable[[], str] = None) -> str:
    def _action(p, t, f):
        return _update(p, t, column, val, f)
    return _db_execute(path, table, _action, filter_func)

def check_done_todo_list(path: str, ids: list[int]) -> str:
    """지정한 ID들의 할 일을 완료 상태로 변경합니다."""
    rets = []
    for row_id in ids:
        res_json = _update_json(path, 'todo_list', 'is_completed', 1,
                                lambda rid=row_id: f'WHERE id={rid} ')
        try:
            rets.append(json.loads(res_json))
        except Exception:
            rets.append(res_json)
    return json.dumps(rets, ensure_ascii=False)


# ── 삭제 ──────────────────────────────────────────────────────────────────────

def _delete(path: str, table: str, filter_func: Callable[[], str]) -> list[dict]:
    """데이터베이스에서 행을 삭제하는 내부 함수입니다."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    query = f"DELETE FROM {table} {filter_func()} RETURNING *"
    cursor.execute(query)
    ret = _cursor_to_list_dict(cursor)
    conn.commit()
    conn.close()
    return ret

def delete_done_todo_list(path: str) -> str:
    """완료된 할 일들을 삭제합니다."""
    return _db_execute(path, 'todo_list', _delete, lambda: "WHERE is_completed=1 ")

def delete_overdue_todo_list(path: str, only_completed: bool = True) -> str:
    """기한이 지난 할 일들을 삭제합니다."""
    def filter_func():
        w = "WHERE due_date < datetime('now', 'localtime') "
        if only_completed:
            w += "AND is_completed=1 "
        return w
    return _db_execute(path, 'todo_list', _delete, filter_func)

def delete_done_page_urls(path: str) -> str:
    """연결된 할 일이 없는 페이지 URL들을 삭제합니다."""
    def filter_func():
        return "WHERE NOT EXISTS (SELECT 1 FROM todo_list WHERE todo_list.url = page_urls.url) "
    return _db_execute(path, 'page_urls', _delete, filter_func)


# ── 클래스 ──────────────────────────────────────────────────────────────────────

class Global_visit_db_page_url:
    """db를 이용한 방문집합"""
    def __init__(self, path:str):
        self.path = path
    # db에서 in연산
    def __contains__(self, url:str) -> bool:
        ret = _get(self.path, 'page_urls', lambda : f"WHERE url='{url}' ")
        return len(ret) > 0
    def add(self, data:dict) -> str:
        return insert_page_url(self.path, data['url'], data['title'])