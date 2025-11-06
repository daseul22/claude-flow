#!/bin/bash

# Claude Flow TUI 설치 스크립트

set -e  # 에러 발생시 중단

echo "======================================"
echo "  Claude Flow TUI 설치"
echo "======================================"
echo ""

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python 버전 확인
echo "🔍 Python 버전 확인..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3가 설치되어 있지 않습니다."
    echo "   Python 3.10 이상을 설치해주세요."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "   ✓ Python $PYTHON_VERSION 발견"

# Python 3.10 이상 확인
MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo "❌ Python 3.10 이상이 필요합니다. (현재: $PYTHON_VERSION)"
    exit 1
fi

echo ""

# 가상환경 확인 및 생성
if [ -d "venv" ]; then
    echo "📦 기존 가상환경 발견"
else
    echo "📦 가상환경 생성 중..."
    python3 -m venv venv
    echo "   ✓ 가상환경 생성 완료"
fi

echo ""

# 가상환경 활성화
echo "🔧 가상환경 활성화..."
source venv/bin/activate

echo ""

# 패키지 설치
echo "📥 패키지 설치 중..."
echo "   (개발 모드로 설치됩니다)"
pip install --upgrade pip --quiet
pip install -e . --quiet

echo "   ✓ 패키지 설치 완료"
echo ""

# 환경변수 확인
echo "🔑 환경변수 확인..."
if [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
    echo "   ⚠️  CLAUDE_CODE_OAUTH_TOKEN이 설정되지 않았습니다."
    echo ""
    echo "   다음 명령어로 설정하세요:"
    echo "   export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'"
    echo ""
    echo "   또는 .env 파일에 추가하세요:"
    echo "   echo \"CLAUDE_CODE_OAUTH_TOKEN=your-token-here\" >> .env"
    echo ""
else
    echo "   ✓ CLAUDE_CODE_OAUTH_TOKEN 설정됨"
fi

echo ""
echo "======================================"
echo "  ✅ 설치 완료!"
echo "======================================"
echo ""
echo "다음 명령어로 실행하세요:"
echo ""
echo "  # 가상환경 활성화"
echo "  source venv/bin/activate"
echo ""
echo "  # 현재 디렉토리에서 실행"
echo "  claude-flow"
echo ""
echo "  # 특정 디렉토리에서 실행"
echo "  claude-flow /path/to/project"
echo ""
echo "======================================"
echo ""
echo "📚 문서:"
echo "  - 기능명세서: docs/TUI_기능명세서.md"
echo "  - 사용가이드: docs/TUI_사용가이드.md"
echo ""
echo "🎯 키보드 단축키:"
echo "  - Ctrl+N: 새 세션"
echo "  - Ctrl+O: 세션 불러오기"
echo "  - Ctrl+I: 프로젝트 정보"
echo "  - Ctrl+L: 화면 지우기"
echo "  - Ctrl+C: 중단/취소/종료"
echo "  - Ctrl+Q: 종료"
echo ""

