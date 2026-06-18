#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== 프로젝트 실행 환경 구축을 시작합니다 ==="

# 1. 가상환경 (.venv) 확인 및 생성
if [ ! -d ".venv" ]; then
    echo "[1/4] .venv 가상환경이 존재하지 않습니다. 가상환경을 생성합니다..."
    python3 -m venv .venv
else
    echo "[1/4] 기존 .venv 가상환경을 사용합니다."
fi

# 2. 가상환경 활성화
echo "[2/4] 가상환경을 활성화합니다."
source .venv/bin/activate

# 3. 필수 패키지 설치
echo "[3/4] requirements.txt 패키지 설치 및 pip 업그레이드를 진행합니다..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Playwright 브라우저 설치
echo "[4/4] Playwright 필요한 브라우저를 설치합니다..."
playwright install chromium

echo "=== 설치가 완료되었습니다! ==="
echo "가상환경을 활성화하려면 아래 명령어를 실행하세요:"
echo "source .venv/bin/activate"
