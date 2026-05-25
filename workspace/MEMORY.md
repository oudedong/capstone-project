# Project Status: Schedule Management Assistant

## Database Location
- Path: `/app/workspace/data/schedule.db`
- Status: Initialized with `origin_urls`, `page_urls`, `todo_list` tables.

## 하던거
- 리다이렉트 정보 저장하는 db생성(redirect_url->login_url,로그인정보들...) 그리고 db를 이용해서 url,페이지 수집시, 목록에 있을경우, 자동로그인 시도하기
- 리다이렉트 페이지에 대해서, 비어있을시 로그인페이지, 로그인 정보 요청 후 넣는 mcp 추가하기

## Crawler Behavior Notes
- **Crawler Delay Mechanism**: 일정 추출 시 `run_extraction_db` 작업이 오래 걸리는 이유는 BFS(Breadth-First Search) 방식의 특성 때문입니다. 이미 방문한 페이지라도 실제 해당 노드(URL)에 다시 접근하여 방문 여부를 확인해야 하므로, 수집된 데이터 양이 많을수록 확인 작업에 시간이 소요됩니다. 이는 정상적인 동작이므로 진행 로그가 느려지더라도 인내심을 가지고 기다려야 합니다.