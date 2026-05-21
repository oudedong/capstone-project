# Project Status: Schedule Management Assistant

## Database Location
- Path: `/app/workspace/data/schedule.db`
- Status: Initialized with `origin_urls`, `page_urls`, `todo_list` tables.

## 하던거
- 리다이렉트 정보 저장하는 db생성(origin_urls->redirect_url, redirect_url->login_url,로그인정보들...) 그리고 db를 이용해서 url,페이지 수집시, 목록에 있을경우, 자동로그인 시도하기
- 리다이렉트 페이지에 대해서, 비어있을시 로그인페이지, 로그인 정보 요청 후 넣는 mcp 추가하기