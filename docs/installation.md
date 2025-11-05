# 설치 가이드

Claude Flow를 설치하고 실행하는 방법을 단계별로 설명합니다.

---

## 📚 관련 문서

- **[문서 INDEX](INDEX.md)** - 모든 문서의 전체 목록
- **[프로젝트 README](../README.md)** - 프로젝트 개요 및 빠른 시작
- **[튜토리얼](tutorial.md)** - 첫 번째 워크플로우 작성
- **[FAQ](faq.md)** - 자주 묻는 질문 및 문제 해결

---

**선택하신 설치 방법**:
- [빠른 설치 (권장)](#빠른-설치-권장) - 자동 스크립트 사용
- [수동 설치](#수동-설치) - 단계별 수동 설정
- [개발 모드](#개발-모드-개발자용) - 소스 코드 수정 시 자동 반영
- [Docker 설치](#docker-설치) - 컨테이너 환경

---

## 시스템 요구사항

### 필수 요구사항

| 항목 | 최소 버전 | 권장 버전 |
|------|----------|----------|
| **Python** | 3.10 | 3.12+ |
| **Node.js** (웹 UI 사용) | 16 | 18+ |
| **메모리** | 2GB RAM | 4GB RAM |
| **디스크** | 500MB 여유 | 2GB 여유 |
| **운영체제** | macOS / Linux | macOS 12+ / Ubuntu 20.04+ |

### 선택 요구사항

- **Windows**: WSL2 (Windows Subsystem for Linux) 권장
- **터미널**: Bash, Zsh, 또는 Fish

---

## 빠른 설치 (권장)

### Step 1: 프로젝트 클론

```bash
git clone https://github.com/your-repo/claude-flow-web.git
cd claude-flow-web
```

### Step 2: 자동 설치 실행

```bash
chmod +x setup.sh
./setup.sh
```

이 스크립트가 자동으로:
- ✅ Python 버전 확인 (3.10+)
- ✅ pipx 설치 및 설정
- ✅ Claude Flow 설치 (일반 또는 개발 모드)
- ✅ 웹 프론트엔드 의존성 설치
- ✅ 웹 프론트엔드 빌드
- ✅ 환경변수 설정 안내

### Step 3: 설치 모드 선택

스크립트 실행 중 모드를 선택합니다:

```
ℹ 설치 모드를 선택하세요:

  1) 일반 모드 - 일반 사용자용 (권장)
     코드가 고정되어 안정적으로 동작합니다.

  2) 개발 모드 - 개발자용
     소스 코드 변경사항이 바로 반영됩니다.

선택 [1-2] (기본값: 1): 1
```

**권장**:
- **일반 모드** (1): 일반 사용자, 프로덕션
- **개발 모드** (2): 개발자, 코드 수정이 필요한 경우

### Step 4: 환경변수 설정

스크립트가 환경변수 설정을 안내합니다:

```
ℹ 환경변수 설정이 필요합니다:

  CLAUDE_CODE_OAUTH_TOKEN - Claude Code OAuth 토큰

지금 OAuth 토큰을 설정하시겠습니까? (y/n): y

CLAUDE_CODE_OAUTH_TOKEN: [입력...]
```

**토큰 발급 방법**:
1. [Claude Code](https://claude.ai/code) 접속
2. 우측 상단 프로필 → Settings
3. OAuth Tokens → Generate Token
4. 토큰 복사 후 입력

### Step 5: 설치 완료

```bash
╔════════════════════════════════════════════╗
║        설치가 완료되었습니다!             ║
╚════════════════════════════════════════════╝

ℹ 사용 방법:

  # Web UI 시작 (드래그 앤 드롭 워크플로우 에디터)
  claude-flow-web

  # 웹 브라우저에서 접속
  http://localhost:5173

  # 개발 모드 (소스 변경 시)
  cd src/presentation/web/frontend
  npm run dev

상세 문서: CLAUDE.md 또는 README.md
```

✅ **설치 완료!** 이제 [첫 실행](#첫-실행) 섹션으로 이동하세요.

---

## 수동 설치

자동 설치가 실패했거나 특정 구성을 원하는 경우 사용합니다.

### Step 1: 프로젝트 클론

```bash
git clone https://github.com/your-repo/claude-flow-web.git
cd claude-flow-web
```

### Step 2: Python 버전 확인

```bash
python3 --version
# 3.10.0 이상이어야 함

# Python 3.10 이상이 없으면 설치
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11
```

### Step 3: pipx 설치 (필수)

```bash
# macOS
brew install pipx

# Ubuntu/Debian
sudo apt install pipx

# 또는 pip로 설치
python3 -m pip install --user pipx

# PATH 설정
pipx ensurepath
```

### Step 4: Python 의존성 설치

```bash
pip install -r requirements.txt
```

**주요 의존성**:
- FastAPI 0.109+
- Claude SDK
- structlog
- pydantic

### Step 5: 웹 프론트엔드 설정

```bash
cd src/presentation/web/frontend

# Node.js 버전 확인
node --version  # 16 이상

# 의존성 설치
npm install

# 프로덕션 빌드
npm run build

# 빌드 결과 확인
ls ../../static-react/index.html
```

Node.js가 없으면:

```bash
# macOS
brew install node

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs
```

### Step 6: Claude Flow 패키지 설치

```bash
cd /path/to/claude-flow-web

# 일반 모드 (권장)
pipx install .

# 또는 개발 모드
pipx install -e .

# 설치 확인
which claude-flow-web
claude-flow-web --version
```

### Step 7: 환경변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 토큰 설정
nano .env  # 또는 편집기로 열기

# .env 파일 내용:
# CLAUDE_CODE_OAUTH_TOKEN=sk-proj-xxx...
```

또는 환경변수로 설정:

```bash
export CLAUDE_CODE_OAUTH_TOKEN='sk-proj-xxx...'

# 영구 설정 (권장)
echo "export CLAUDE_CODE_OAUTH_TOKEN='sk-proj-xxx...'" >> ~/.zshrc
source ~/.zshrc
```

### Step 8: 설치 검증

```bash
# 명령어 확인
which claude-flow-web

# 도움말 확인
claude-flow-web --help

# 버전 확인
claude-flow-web --version

# 웹 빌드 확인
ls src/presentation/web/static-react/index.html
```

---

## 개발 모드 (개발자용)

소스 코드 변경 시 자동으로 반영되도록 설정합니다.

### Step 1: 개발 모드로 설치

```bash
pip install -e .  # 현재 디렉토리에서
# 또는
pipx install --python /usr/bin/python3.11 -e .  # 특정 Python 버전
```

### Step 2: 프론트엔드 개발 서버 실행

별도의 터미널에서 실행합니다:

```bash
cd src/presentation/web/frontend

# 개발 서버 시작 (자동 핫 리로드)
npm run dev

# 또는 포트 지정
npm run dev -- --port 5174
```

출력:

```
➜  local:   http://localhost:5173
➜  press h to show help
```

### Step 3: 백엔드 실행

또 다른 터미널에서:

```bash
python -m src.presentation.web.app
```

또는:

```bash
python src/presentation/web/app.py
```

### Step 4: 코드 수정 및 테스트

```
프론트엔드:
- src/presentation/web/frontend/src/**/*.tsx 수정
- 브라우저에서 자동 새로고침

백엔드:
- src/presentation/web/**/*.py 수정
- 서버 재시작 필요 (자동 아님)
```

### Step 5: 코드 포맷팅 및 린팅

```bash
# Black (포맷팅)
black src/ --line-length 100

# Ruff (린팅)
ruff check src/

# 타입 체크 (mypy)
mypy src/
```

---

## Docker 설치

컨테이너 환경에서 Claude Flow를 실행합니다.

### Step 1: Dockerfile 생성

프로젝트 루트에 `Dockerfile` 생성:

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node.js 설치 (웹 빌드용)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 프로젝트 복사
COPY . .

# 웹 프론트엔드 빌드
RUN cd src/presentation/web/frontend && \
    npm install && \
    npm run build

# 포트 노출
EXPOSE 5173

# 헬스 체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5173/api/health || exit 1

# 서버 시작
CMD ["python", "-m", "src.presentation.web.app"]
```

### Step 2: Docker 빌드

```bash
docker build -t claude-flow:latest .
```

### Step 3: Docker 실행

```bash
docker run -d \
  --name claude-flow \
  -p 5173:5173 \
  -e CLAUDE_CODE_OAUTH_TOKEN='sk-proj-xxx...' \
  -v ~/.claude-flow:/root/.claude-flow \
  claude-flow:latest
```

**옵션 설명**:
- `-d`: 백그라운드 실행
- `--name`: 컨테이너 이름
- `-p`: 포트 매핑 (호스트:컨테이너)
- `-e`: 환경변수 설정
- `-v`: 볼륨 마운트 (영구 저장)

### Step 4: 실행 확인

```bash
# 컨테이너 상태 확인
docker ps

# 로그 확인
docker logs -f claude-flow

# 웹 접속
open http://localhost:5173
```

### Step 5: 컨테이너 관리

```bash
# 컨테이너 중지
docker stop claude-flow

# 컨테이너 시작
docker start claude-flow

# 컨테이너 제거
docker rm claude-flow

# 이미지 제거
docker rmi claude-flow:latest
```

---

## 첫 실행

### Step 1: 서버 시작

```bash
claude-flow-web

# 출력:
# ✓ FastAPI 서버 시작
# ✓ React 프론트엔드 로드
# ✓ 서버가 http://localhost:5173 에서 실행 중입니다
#
# Ctrl+C로 중지
```

### Step 2: 웹 브라우저 접속

웹 브라우저를 열고 다음 URL 접속:

```
http://localhost:5173
```

### Step 3: 워크플로우 생성

1. **"새 워크플로우"** 클릭
2. **이름** 입력: "My First Workflow"
3. **생성** 클릭

### Step 4: 첫 번째 워크플로우 실행

[튜토리얼](tutorial.md)을 따라 첫 번째 워크플로우를 실행해보세요.

---

## 포트 설정

기본 포트는 5173입니다. 다른 포트를 사용하려면:

```bash
# 환경변수로 설정
CLAUDE_FLOW_PORT=5174 claude-flow-web

# 또는 .env 파일에 추가
echo "CLAUDE_FLOW_PORT=5174" >> .env

# 또는 명령어 옵션
claude-flow-web --port 5174
```

포트 충돌 확인:

```bash
# macOS/Linux
lsof -i :5173

# 프로세스 종료
kill -9 <PID>
```

---

## 다중 프로젝트 설정

여러 프로젝트를 동시에 관리하려면:

### 방법 1: 별도 포트 사용

```bash
# 터미널 1
CLAUDE_FLOW_PORT=5173 claude-flow-web

# 터미널 2
CLAUDE_FLOW_PORT=5174 claude-flow-web

# 터미널 3
CLAUDE_FLOW_PORT=5175 claude-flow-web
```

### 방법 2: 별도 프로젝트 경로

```bash
export CLAUDE_FLOW_PROJECT_ROOT="/path/to/project-1"
claude-flow-web

# 또는 .env 파일
echo "CLAUDE_FLOW_PROJECT_ROOT=/path/to/project-1" >> .env
```

---

## 트러블슈팅

### Q: "Python 3.10을 찾을 수 없습니다"

**해결책**:

```bash
# 설치된 Python 버전 확인
python3 --version
python3.10 --version
python3.11 --version

# 필요한 버전 설치
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11

# 명시적 지정
./setup.sh  # Python 3.11로 자동 선택
```

### Q: "pipx를 찾을 수 없습니다"

**해결책**:

```bash
# pipx 설치
python3 -m pip install --user pipx

# PATH 설정
python3 -m pipx ensurepath

# 셸 재시작
exec $SHELL
```

### Q: "npm이 설치되지 않았습니다"

**해결책** (웹 UI 필수):

```bash
# macOS
brew install node

# Ubuntu
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs

# 버전 확인
node --version  # v18.0.0 이상
npm --version   # 9.0.0 이상
```

### Q: 웹 UI 빌드 실패

**해결책**:

```bash
cd src/presentation/web/frontend

# 캐시 삭제
rm -rf node_modules package-lock.json

# 다시 설치
npm install --legacy-peer-deps
npm run build

# 결과 확인
ls ../../static-react/index.html
```

### Q: "CLAUDE_CODE_OAUTH_TOKEN이 설정되지 않았습니다"

**해결책**:

```bash
# 1. 토큰 확인
echo $CLAUDE_CODE_OAUTH_TOKEN

# 2. .env 파일 확인
cat .env | grep CLAUDE_CODE_OAUTH_TOKEN

# 3. 토큰 설정
export CLAUDE_CODE_OAUTH_TOKEN='sk-proj-xxx...'

# 4. 다시 실행
claude-flow-web
```

### Q: 포트가 이미 사용 중입니다

**해결책**:

```bash
# 점유 프로세스 확인
lsof -i :5173

# 프로세스 종료
kill -9 <PID>

# 또는 다른 포트로 실행
CLAUDE_FLOW_PORT=5174 claude-flow-web
```

### Q: "ModuleNotFoundError: No module named 'src'"

**해결책**:

```bash
# 프로젝트 루트에서 실행
cd /path/to/claude-flow-web

# 패키지 재설치
pip install -e .

# 또는 직접 실행
python -m src.presentation.web.app
```

---

## 업그레이드

이전 버전에서 업그레이드하려면:

```bash
# 1. 프로젝트 최신 버전 다운로드
git pull origin main

# 2. 패키지 재설치
pip install -e . --upgrade

# 또는 pipx로
pipx install . --upgrade

# 3. 의존성 업데이트
pip install -r requirements.txt --upgrade

# 4. 웹 프론트엔드 재빌드
cd src/presentation/web/frontend
npm install
npm run build
```

---

## 설치 환경별 참고사항

### macOS

```bash
# M1/M2 (Apple Silicon)
# 자동으로 ARM64 바이너리 사용

# Intel Mac
# 자동으로 x86_64 바이너리 사용

# 문제 시 아키텍처 확인
uname -m  # arm64 또는 x86_64
```

### Linux (Ubuntu/Debian)

```bash
# 시스템 패키지 설치
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Python 3.11을 기본값으로 설정
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
```

### Windows (WSL2 권장)

```bash
# WSL2 Ubuntu 20.04 또는 22.04 설치 권장
wsl --list --verbose

# 기존 설치 시 Python/Node 업그레이드
sudo apt update
sudo apt upgrade
```

---

## 보안 설정 (권장)

### 환경변수 보안

```bash
# 1. .env 파일 권한 제한
chmod 600 .env

# 2. .gitignore에 추가 (이미 추가됨)
cat .gitignore | grep .env

# 3. 토큰 자동 로드 (권장)
# ~/.bashrc 또는 ~/.zshrc에 추가:
if [ -f ~/.claude-flow/.env ]; then
    export $(cat ~/.claude-flow/.env | grep -v '^#' | xargs)
fi
```

### 네트워크 보안

```bash
# localhost에서만 수락 (기본)
# 다른 머신에서 접속하려면:

# 방법 1: SSH 터널링 (권장)
ssh -L 5173:localhost:5173 user@remote-host

# 방법 2: 방화벽 설정
sudo ufw allow 5173  # Ubuntu
```

---

## 다음 단계

- ✅ 설치 완료
- 👉 [튜토리얼](tutorial.md) - 첫 워크플로우 만들기
- 📚 [README.md](../README.md) - 기본 사용법
- ❓ [FAQ](faq.md) - 자주 묻는 질문

행운을 빕니다! 🚀
