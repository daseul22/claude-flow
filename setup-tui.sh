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

# Python 3.10 이상 버전 찾기 (우선순위: python3.14 > python3.13 > python3.12 > python3.11 > python3.10)
PYTHON_CMD=""
for py_cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py_cmd" &> /dev/null; then
        # 버전 체크
        if $py_cmd -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            PYTHON_CMD="$py_cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.10 이상을 찾을 수 없습니다."
    echo ""
    echo "현재 설치된 Python 버전:"
    for py_cmd in python3.9 python3.10 python3.11 python3.12 python3.13 python3.14 python3; do
        if command -v "$py_cmd" &> /dev/null; then
            version=$($py_cmd --version 2>&1)
            echo "  - $py_cmd: $version"
        fi
    done
    echo ""
    echo "Python 3.10 이상을 설치해주세요:"
    echo "  https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
echo "   ✓ Python $PYTHON_VERSION ($PYTHON_CMD) 발견"

echo ""

# 가상환경 확인 및 생성
if [ -d "venv" ]; then
    echo "📦 기존 가상환경 발견"
else
    echo "📦 가상환경 생성 중..."
    $PYTHON_CMD -m venv venv
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

