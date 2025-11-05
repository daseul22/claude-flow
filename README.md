# Claude Flow - AI-Powered Workflow Automation Platform

> 그룹 챗 오케스트레이션 시스템. AI 에이전트(Worker)들이 협력하여 복잡한 소프트웨어 개발 작업을 자동화합니다.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/React-18-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-4.0.1-green)]()

---

## 📖 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [빠른 시작](#빠른-시작)
- [문서](#문서)
- [사용 예시](#사용-예시)
- [설정](#설정)
- [FAQ](#faq)
- [기여 방법](#기여-방법)

---

## 개요

### Claude Flow란?

**Claude Flow**는 비주얼 인터페이스로 복잡한 소프트웨어 개발 작업을 **노드 기반 워크플로우**로 설계하고 자동화하는 플랫폼입니다. Claude Agent SDK를 기반으로 한 **46개의 전문화된 AI 에이전트(Worker)**가 협력하여 엔지니어링 작업을 완료합니다.

### 핵심 특징

| 기능 | 설명 |
|------|------|
| **🎨 비주얼 에디터** | 드래그 앤 드롭으로 워크플로우 설계 (ReactFlow 기반) |
| **🤖 AI 자동 설계** | 자연어 지시 → 워크플로우 자동 생성 |
| **🔗 노드 기반 오케스트레이션** | Input, Worker, Condition, Merge 노드로 복잡한 로직 표현 |
| **📚 프롬프트 라이브러리** | 46개 전문화된 Worker 프롬프트 (Feature Planner, Backend Coder, QA Engineer 등) |
| **💬 Human-in-the-Loop** | AI와 대화하며 실시간으로 작업 진행 |
| **🔄 세션 재활용** | 노드별 컨텍스트 유지로 장기 대화 지원 |
| **⚡ 실시간 스트리밍** | SSE 기반 실행 로그 실시간 표시 |
| **🔐 보안** | Path Traversal, RCE 방지 (보안 검토 완료) |

---

## 주요 기능

### 1. 그룹 챗 오케스트레이션

```
[Input] → [Planner] → [Coder] → [Reviewer] → [Output]
                         ↓
                    [Test Writer]
```

여러 AI 에이전트가 순차 또는 병렬로 협력합니다.

### 2. 46개의 전문화된 Worker

- **계획**: Feature Planner, Architecture Reviewer, Product Manager
- **개발**: Backend Coder, Frontend Coder, Database Coder, API Coder
- **테스트**: Unit Tester, Integration Tester, E2E Tester
- **검토**: Code Reviewer, Security Reviewer, Performance Tester
- **문서화**: API Documenter, Code Documenter, User Guide Writer
- **기타**: Bug Fixer, Refactoring Planner, Deployment Manager, ...

### 3. 세션 재활용

Claude SDK 세션을 자동으로 저장 및 재활용하여 **컨텍스트 손실 없이** 장기 대화를 지원합니다.

### 4. Human-in-the-Loop

Worker가 `@ASK_USER: "질문"` 패턴으로 사용자 입력 요청 → 사용자 응답 → 작업 자동 재개

### 5. 실시간 스트리밍 (SSE)

- 노드 시작/완료 이벤트
- 실시간 스트리밍 출력 (각 노드의 진행 상황)
- 워크플로우 완료 알림
- 에러 및 경고 메시지

### 6. 조건 분기 및 병렬 실행

**순차 분기 예시**:
```
[Input] → [Analyzer] → [Condition: Code Quality?]
                            ↓[YES] → [Merger] → [Output]
                            ↓[NO]  → [Refactorer] → [Merger]
```

**병렬 실행 예시**:
```
[Input]
  → [Coder]    ┐
  → [Tester]   ├→ [Merger] → [Output]
  → [Reviewer] ┘
```

### 7. 템플릿 시스템

재사용 가능한 워크플로우 템플릿으로 반복 작업 자동화

---

## 빠른 시작

### 1단계: 설치

```bash
# 프로젝트 클론
git clone https://github.com/your-repo/claude-flow-web.git
cd claude-flow-web

# 자동 설치 (권장)
./setup.sh
```

**수동 설치**:
<details>
<summary><b>수동 설치</b> (고급)</summary>

```bash
# Python 의존성 설치
pip install -r requirements.txt

# 웹 프론트엔드 빌드
./web-build.sh

# 또는 수동 빌드:
cd src/presentation/web/frontend
npm install
npm run build
cd ../../../
```
</details>

### 2단계: 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# Claude Code OAuth 토큰 설정
export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'
```

**Claude Code OAuth 토큰 발급**:
1. [Claude Code](https://claude.ai/code) 접속
2. 우측 상단 "Settings" 메뉴 클릭
3. "OAuth Tokens" 탭 → "Generate Token" 클릭
4. 토큰을 복사하여 `.env` 파일에 붙여넣기

### 3단계: 실행

```bash
# 웹 UI 실행 (권장)
claude-flow-web

# 또는 CLI로 실행
python -m src.presentation.web.app
```

웹 브라우저에서 **http://localhost:5173** 접속

---

## 문서

### 📚 완전한 문서 목록

| 문서 | 용도 | 대상 |
|------|------|------|
| **[설치 가이드](docs/installation.md)** | 설치 및 환경 설정 | 모든 사용자 |
| **[사용자 가이드](docs/tutorial.md)** | 워크플로우 설계 및 실행 | 일반 사용자 |
| **[API 레퍼런스](docs/api.md)** | REST API 엔드포인트 | 개발자 |
| **[아키텍처](ARCHITECTURE.md)** | 시스템 설계 및 패턴 | 아키텍트, 개발자 |
| **[코드 레퍼런스](CODE_REFERENCE.md)** | 핵심 클래스 및 함수 | 개발자 |
| **[데이터베이스](DATABASE.md)** | 데이터 모델 및 스키마 | 개발자, DBA |
| **[프로젝트 문서](CLAUDE.md)** | 프로젝트 개요 및 명령어 | 개발자 |

---

## 사용 예시

### 예시 1: 기본 코딩 워크플로우

```
[Input] → [Backend Coder] → [Code Reviewer] → [Output]
                               ↓
                          [Bug Fixer] (조건부)
```

**단계**:
1. Input 노드에서 작업 요구사항 입력
2. Backend Coder가 코드 작성
3. Code Reviewer가 검토 (피드백 또는 승인)
4. 피드백 있으면 Bug Fixer가 수정
5. 최종 코드 및 보고서 저장

### 예시 2: 병렬 테스트 실행

```
[Input]
  → [Unit Tester]
  → [Integration Tester]
  → [E2E Tester]
       ↓
  [Merger] → [Test Report Generator] → [Output]
```

**특징**:
1. 3개의 테스트가 병렬로 실행
2. 모든 테스트 결과가 통합됨
3. 통합 테스트 보고서 생성

### 예시 3: 새 기능 개발 워크플로우

```
[Feature Request]
  ↓
[Architecture Reviewer] → [API Planner] → [API Endpoint Coder]
  ↓                                             ↓
[Database Planner] → [Database Coder] → [Merger] → [Output]
```

---

## 설정

### 필수 환경변수

| 변수 | 설명 | 예시 |
|------|------|------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code OAuth 토큰 | `sk-proj-xxx...` |

### 선택 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `CLAUDE_FLOW_PORT` | 웹 UI 포트 | `5173` |
| `CLAUDE_FLOW_PROJECT_ROOT` | 프로젝트 루트 경로 | 현재 디렉토리 |
| `CLAUDE_FLOW_LOG_LEVEL` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) | `INFO` |

### 환경변수 설정

#### 방법 1: `.env` 파일 (권장)

```bash
cp .env.example .env
nano .env  # 에디터로 수정
```

#### 방법 2: 시스템 환경변수

```bash
# 현재 세션에만 적용
export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'

# 영구 설정 (macOS/Linux)
echo "export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'" >> ~/.zshrc
source ~/.zshrc
```

#### 방법 3: 비밀 관리자 (macOS)

```bash
# macOS Keychain 사용 (고급)
brew install --cask 1password
# 1Password에 토큰 저장 (선택 사항)
```

---

## 시스템 요구사항

### 필수 요구사항

| 항목 | 최소 버전 | 권장 버전 |
|------|----------|----------|
| **Python** | 3.10 | 3.12+ |
| **Node.js** (웹 UI) | 16 | 18+ |
| **메모리** | 2GB RAM | 4GB RAM |
| **디스크** | 500MB 여유 | 2GB 여유 |

### 개발 모드

```bash
# 개발 의존성 설치
pip install -e .

# 웹 프론트엔드 개발 모드 (Hot Reload)
cd src/presentation/web/frontend
npm run dev

# 백엔드 실행 (다른 터미널)
python -m src.presentation.web.app
```

---

## FAQ

### 설치 관련

**Q: "Python 3.10을 찾을 수 없습니다" 에러**

**해결방법**:
```bash
# Python 버전 확인
python3 --version
python3.10 --version

# Python 설치 (macOS)
brew install python@3.12

# 또는 설치 스크립트 실행
./setup.sh
```

**Q: "npm 설치가 실패합니다" 에러**

**해결방법**:
```bash
# macOS
brew install node

# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs
```

**Q: 웹 UI 빌드 실패**

**해결방법**:
```bash
cd src/presentation/web/frontend
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
npm run build
```

### 실행 관련

**Q: "CLAUDE_CODE_OAUTH_TOKEN이 설정되지 않았습니다" 에러**

**해결방법**:
```bash
# 토큰 확인
echo $CLAUDE_CODE_OAUTH_TOKEN

# 토큰 설정
export CLAUDE_CODE_OAUTH_TOKEN='your-token-here'

# 정상 실행
claude-flow-web
```

**Q: 포트 5173이 이미 사용 중입니다**

**해결방법**:
```bash
# 사용 중인 프로세스 확인
lsof -i :5173

# 프로세스 종료
kill -9 <PID>

# 다른 포트로 실행
CLAUDE_FLOW_PORT=5174 claude-flow-web
```

### Worker 실행 관련

**Q: Worker가 응답하지 않습니다**

**디버깅 방법**:
1. 토큰 확인: `echo $CLAUDE_CODE_OAUTH_TOKEN`
2. Claude API 할당량 확인
3. 로그 조회: `~/.claude-flow/logs/`
4. 프롬프트 검증: `prompts/{worker_name}.txt` 확인

**Q: 토큰 만료 오류가 발생합니다**

**해결방법**:
1. **Thinking 비활성화**: 일부 모델의 Thinking 기능 비활성화
2. **세션 재활용**: 노드별 세션 저장 및 재사용
3. **출력 압축**: 불필요한 출력 제거
4. **Worker 모델 변경**: 저비용 모델 사용 (예: Haiku)

---

### 일반 관련

**Q: 워크플로우가 4단계 이상입니다**

워크플로우는 여러 AI 에이전트가 협력하여 작업하므로 충분히 가능합니다. ["사용 예시"](#사용-예시) 섹션에서 "T자 모양 개발" 및 "병렬 테스트" 예시를 참고하세요.

**Q: 언제 어떤 워크플로우를 사용해야 합니까?**

- **기본 흐름**: 새 기능 작성 → 코드 리뷰 → 테스트 → 배포
- **복잡 시나리오**: 새 기능 작성 → 병렬 테스트 및 리뷰 → 병합
- **버그 수정**: 버그 재현 → 원인 파악 → 수정 → 테스트
- **아키텍처**: 설계 → 구현 → 검토 → 테스트

**Q: Worker 에이전트는 몇 가지 유형입니까?**

에이전트는 다음과 같이 분류됩니다:
- **Planner**: 계획 수립 (Feature Planner, Task Planner 등)
- **Coder**: 코드 작성 (Backend Coder, Frontend Coder 등)
- **Tester**: 테스트 (Unit Tester, Integration Tester 등)
- **Reviewer**: 코드 검토 (Code Reviewer, Security Reviewer 등)

**Q: 새 Worker를 추가하려면?**

Worker 노드 설정에서 "Agent" 필드의 드롭다운을 보면 설정된 모든 Worker를 볼 수 있습니다. 새 Worker를 추가하려면 [프로젝트 문서](CLAUDE.md#새-프롬프트-추가-방법)를 참고하세요.

### 워크플로우 관련

**Q: 워크플로우를 여러 번 실행할 수 있습니까?**

네, **세션 재활용**을 통해 가능합니다. 이전 실행의 컨텍스트를 유지하고 반복 실행할 수 있습니다.

**Q: 실행 로그는 어디에 저장됩니까?**

로그는 다음 위치에 저장됩니다:

```
~/.claude-flow/{프로젝트명}/logs/
     session-{session-id}.log      # 실행 세션 로그
     node-{node-id}-{timestamp}.log # 노드별 세부 로그
```

**Q: 실행 중 작업을 중단할 수 있습니까?**

네, **Cancel** 버튼을 클릭하여 현재 노드를 취소할 수 있습니다.

**Q: 워크플로우 실행 속도를 높이려면?**

다음 방법을 시도하세요:

1. **병렬 실행**: Merge 노드를 사용하여 여러 Worker를 병렬로 실행
2. **세션 재활용**: 노드별 세션 저장으로 컨텍스트 유지
3. **Thinking 비활성화**: 필요 없으면 Thinking 모드 비활성화
4. **출력 압축 설정**: 다음 노드로 전달할 출력만 추출

### 커스텀 관련

**Q: 새 Worker를 직접 만들 수 있습니까?**

네, 새 Worker를 직접 만들 수 있습니다:

1. **파일 생성**: `~/.claude-flow/custom_workers/my_worker.txt`
2. **프롬프트 작성** (시스템 프롬프트 형식)
3. **Worker 노드 설정**: `my_worker`로 참조

자세한 내용은 [CLAUDE.md](CLAUDE.md#새-프롬프트-추가-방법) 문서를 참고하세요.

**Q: Worker 노드에 사용자 정의 변수를 추가할 수 있습니까?**

네, 템플릿 변수를 사용할 수 있습니다:

```
템플릿: "{{input}}을 분석하고 {{node_1.output}}을 사용하세요"

지원 변수:
- {{input}}: Input 노드의 초기 입력
- {{node_1.output}}: node_1의 출력
- {{node_2.output}}: node_2의 출력
```

**Q: 조건 노드는 어떻게 작동합니까?**

조건은 여러 유형을 지원합니다:

```
조건 유형:
1. "포함" (contains): 문자열 포함 여부
2. "정규식" (regex): 정규 표현식 (4가지 모드)
3. "길이" (length): 문자열 길이 비교
4. "커스텀" (custom): Python 식 평가
5. "LLM" (llm): AI 판단

예: contains "ERROR"을 포함하면 [TRUE] 경로로 이동
```

**Q: 분기와 병렬은 어떻게 다릅니까?**

병렬 실행은 다음과 같이 구성합니다:

```
[Input]
  → [Coder]    ┐
  → [Tester]   ├→ [Merger] (결과 통합)
  → [Reviewer] ┘
```

---

## 기여 방법

- **이슈 신고**: GitHub Issues에서 버그 및 기능 제안
- **문의사항**: GitHub Discussions에서 질문 및 토론

---

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. [LICENSE](LICENSE) 파일을 참고하세요.

---

## 향후 계획

- [ ] 새 워크플로우 템플릿 추가 (5개)
- [ ] 고급 권한 관리 (15개)
- [ ] 커스텀 Worker 저장소 (30개)
- [ ] 클라우드 스토리지 지원 (10개)

감사합니다! 🙏
