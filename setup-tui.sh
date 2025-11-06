#!/bin/bash
# Claude Flow TUI 설치 스크립트 (pipx 글로벌 설치)

set -e  # 에러 발생 시 즉시 종료

# 색상 코드
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 헬퍼 함수
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}      Claude Flow TUI 설치                 ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}"
    echo ""
}

# 1. Python 버전 체크
check_python() {
    print_info "Python 버전 확인 중..."

    # Python 3.10 이상 버전 찾기
    PYTHON_CMD=""
    for py_cmd in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$py_cmd" &> /dev/null; then
            if $py_cmd -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                PYTHON_CMD="$py_cmd"
                break
            fi
        fi
    done

    if [ -z "$PYTHON_CMD" ]; then
        print_error "Python 3.10 이상을 찾을 수 없습니다."
        echo ""
        echo "  현재 설치된 Python 버전:"
        for py_cmd in python3.9 python3.10 python3.11 python3.12 python3.13 python3.14 python3; do
            if command -v "$py_cmd" &> /dev/null; then
                version=$($py_cmd --version 2>&1)
                echo "    - $py_cmd: $version"
            fi
        done
        echo ""
        echo "  Python 3.10 이상을 설치해주세요:"
        echo "  https://www.python.org/downloads/"
        exit 1
    fi

    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
    print_success "Python $PYTHON_VERSION ($PYTHON_CMD) 확인됨"
}

# 2. pipx 설치
install_pipx() {
    print_info "pipx 확인 중..."

    if command -v pipx &> /dev/null; then
        print_success "pipx가 이미 설치되어 있습니다."
        return
    fi

    print_warning "pipx가 설치되지 않았습니다. 설치 중..."

    # macOS - Homebrew 사용
    if command -v brew &> /dev/null; then
        brew install pipx
        pipx ensurepath
        print_success "pipx 설치 완료 (Homebrew)"

    # Linux/macOS - pip 사용
    else
        $PYTHON_CMD -m pip install --user pipx
        $PYTHON_CMD -m pipx ensurepath
        print_success "pipx 설치 완료 (pip)"
    fi

    # PATH 갱신 안내
    print_warning "셸을 재시작하거나 다음 명령어를 실행하세요:"
    if [ -f ~/.zshrc ]; then
        echo "  source ~/.zshrc"
    elif [ -f ~/.bashrc ]; then
        echo "  source ~/.bashrc"
    fi
    echo ""
}

# 3. 설치 모드 선택
choose_install_mode() {
    echo ""
    print_info "설치 모드를 선택하세요:"
    echo ""
    echo -e "  ${CYAN}1)${NC} 일반 모드 - 일반 사용자용 (권장)"
    echo "     전역에서 claude-flow 명령어 사용 가능"
    echo ""
    echo -e "  ${CYAN}2)${NC} 개발 모드 - 개발자용"
    echo "     소스 코드 변경사항이 바로 반영됩니다."
    echo ""

    read -p "선택 [1-2] (기본값: 1): " mode_choice

    case $mode_choice in
        2)
            INSTALL_MODE="editable"
            print_info "개발 모드로 설치합니다."
            ;;
        *)
            INSTALL_MODE="normal"
            print_info "일반 모드로 설치합니다."
            ;;
    esac
}

# 4. claude-flow 설치
install_claude_flow() {
    echo ""
    print_info "claude-flow TUI 설치 중 (Python $PYTHON_VERSION 사용)..."

    # 기존 설치 확인
    if pipx list 2>/dev/null | grep -q "claude-flow"; then
        print_warning "기존 설치를 제거하고 재설치합니다..."
        pipx uninstall claude-flow || true
    fi

    # 설치 모드에 따라 설치
    if [ "$INSTALL_MODE" = "editable" ]; then
        pipx install --python "$PYTHON_CMD" -e .
        print_success "claude-flow 설치 완료 (개발 모드)"
    else
        pipx install --python "$PYTHON_CMD" .
        print_success "claude-flow 설치 완료 (일반 모드)"
    fi
}

# 5. 환경변수 안내
setup_environment() {
    echo ""
    print_info "환경변수 확인..."

    # .env 파일에서 토큰 로드 시도
    if [ -f ".env" ] && [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
        TOKEN_FROM_ENV=$(grep -E "^CLAUDE_CODE_OAUTH_TOKEN=" .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")

        if [ -n "$TOKEN_FROM_ENV" ]; then
            export CLAUDE_CODE_OAUTH_TOKEN="$TOKEN_FROM_ENV"
            print_success "CLAUDE_CODE_OAUTH_TOKEN이 .env에서 로드됨"
        fi
    fi

    # 환경변수 확인
    if [ -z "$CLAUDE_CODE_OAUTH_TOKEN" ]; then
        echo ""
        print_warning "CLAUDE_CODE_OAUTH_TOKEN이 설정되지 않았습니다."
        echo ""
        echo "  Claude Code에서 OAuth 토큰을 발급받으세요:"
        echo "  ${CYAN}https://claude.ai/code${NC} → Settings → OAuth Tokens"
        echo ""
        echo "  설정 방법:"
        echo "  ${CYAN}export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'${NC}"
        echo ""
        echo "  또는 .env 파일에 추가:"
        echo "  ${CYAN}echo \"CLAUDE_CODE_OAUTH_TOKEN=your-token-here\" >> .env${NC}"
        echo ""
    else
        print_success "CLAUDE_CODE_OAUTH_TOKEN 설정 확인됨"
    fi
}

# 6. 완료 메시지
print_completion() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}      ✅ 설치 완료!                         ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "다음 명령어로 실행하세요:"
    echo ""
    echo -e "  ${CYAN}# 현재 디렉토리에서 실행${NC}"
    echo "  claude-flow"
    echo ""
    echo -e "  ${CYAN}# 특정 디렉토리에서 실행${NC}"
    echo "  claude-flow /path/to/project"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
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
}

# 메인 실행 흐름
main() {
    print_header
    check_python
    install_pipx
    choose_install_mode
    install_claude_flow
    setup_environment
    print_completion
}

# 스크립트 실행
main

