# syntax=docker/dockerfile:1
FROM node:20-slim

# 필요한 빌드 도구 설치 (C++ 및 Python 환경)
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3.11-venv\
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# 2. tzdata 패키지 설치 및 타임존 설정 (Debian/Ubuntu 계열)
ENV TZ=Asia/Seoul
RUN apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

# Gemini CLI 설치
RUN npm install -g @google/gemini-cli

# 파이썬 라이브러리 설치
## 1. 가상환경 생성 (절대 경로 사용 권장)
RUN python3 -m venv /app/.venv
## 2. PATH 설정 (이 설정으로 인해 이후 pip 호출 시 가상환경의 pip가 실행됨)
ENV PATH="/app/.venv/bin:$PATH"
## 3. 패키지 설치
RUN pip install --no-cache-dir mcp fastmcp beautifulsoup4 requests playwright && playwright install chromium
RUN playwright install-deps

# 작업 디렉토리 설정
WORKDIR /app
COPY . .

# 배시 틀어놓음
CMD ["bash"]