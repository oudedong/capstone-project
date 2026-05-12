# Task Context
- **`/app` 루트의 파일은 초기화될 수 있으므로, 보존이 필요한 상태 데이터는 반드시 `workspace/` 하위에 저장해야 합니다.**
- 모든 일정관련 정보들은 sqlite를 이용하여 db로 관리됩니다.
## Database Schema (SQLite)
비서는 다음 SQL 구조를 참조하여 데이터를 관리하고 쿼리를 생성한다.
### 1. origin_urls (출처 URL 관리)
- **용도**: 요약된 메인 웹사이트나 정보의 근거가 되는 URL 저장
- **구조**:
  - `id`: INTEGER (PK, 자동 증가)
  - `url`: TEXT (UNIQUE)
  - `summary`: TEXT (URL 콘텐츠의 요약본)

### 2. page_urls (세부 페이지 추적)
- **용도**: 출저 URL에서 크롤링하거나 확인한 개별 페이지들의 이력 관리
- **구조**:
  - `id`: INTEGER (PK, 자동 증가)
  - `url`: TEXT (UNIQUE)
  - `title`: TEXT (UNIQUE)
  - `last_check`: TEXT (마지막 확인 시간)

### 3. todo_list (할 일 목록)
- **용도**: 사용자의 작업, 마감 기한 및 관련 링크 관리
- **구조**:
  - `id`: INTEGER (PK)
  - `url`: TEXT (page_urls에 url에 대한 FK, 해당하는 page_urls링크)
  - `content`: TEXT (NOT NULL, 할 일 내용)
  - `is_completed`: BOOLEAN (기본값 0, 완료 여부)
  - `due_date`: TEXT (NULL가능, 모르면 비워도됨)