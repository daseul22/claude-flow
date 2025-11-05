# 🔍 코드베이스 보안 및 버그 패턴 감사 보고서

**작성일**: 2025-01-15
**프로젝트**: Claude Flow (v4.0.1)
**범위**: src/ 디렉토리 전체 코드 분석
**분석 도구**: Grep, AST 분석, 코드 리뷰

---

## 📊 감사 요약

| 심각도 | 개수 | 상태 |
|--------|------|------|
| 🔴 Critical | 0 | - |
| 🔶 High | 1 | 모니터링 필요 |
| 🟡 Medium | 5 | 개선 권장 |
| 🔵 Low | 2 | 문서화 필요 |
| **합계** | **8** | - |

---

## 🔴 Critical 이슈

현재 Critical 수준의 알려진 이슈가 없습니다. ✅

---

## 🔶 High 우선순위 이슈

### BUG-P001: eval() 함수 사용 (부분 수정됨)

**위치**: `src/presentation/web/services/workflow_condition_evaluator.py:387`

**심각도**: 🔶 **High** (AST 검증으로 인한 위험도 감소)

**문제점**:

```python
# 현재 코드 (387줄)
compiled = compile(tree, '<string>', 'eval')
result = eval(compiled, {"__builtins__": {}}, namespace)  # ⚠️ eval 사용
```

**위험성**:
- `eval()`은 전통적으로 원격 코드 실행 취약점으로 간주됨
- AST 화이트리스트 검증이 추가되었으나, 컴파일된 코드를 eval로 실행하는 것 자체는 위험
- 향후 검증 로직에 우회 방법이 발견될 경우 즉시 침투 가능

**현재 방어**:
- ✅ AST 화이트리스트 검증 (55-117줄)
  - 허용 노드: 상수, 변수, 산술/비교/논리 연산
  - 차단 노드: 속성 접근, 메서드 호출, 위험한 함수
- ✅ 제한된 네임스페이스 (`__builtins__: {}`)

**개선 권장사항**:

1. **즉시** (v4.0.2):
   ```python
   # eval() 제거, ast.literal_eval로 교체 고려
   # 또는 sympy.sympify() 같은 안전한 수학식 파서 사용

   from ast import literal_eval

   # 상수만 평가하는 방식으로 변경
   safe_evaluator = SafeExpressionEvaluator(
       allowed_functions=['len', 'str', 'int', 'float', 'bool']
   )
   result = safe_evaluator.evaluate(condition_value, namespace)
   ```

2. **추적**:
   - eval() 사용 위치를 모두 감사 로그에 기록
   - 조건식 입력에 대한 감사 추적 추가

3. **테스트**:
   - 악의적인 조건식 주입 시도에 대한 회귀 테스트 작성
   - 예: `__import__('os').system('rm -rf /')` 같은 injection 테스트

---

## 🟡 Medium 우선순위 이슈

### BUG-P002: 광범위한 Exception 캐칭

**위치**: 여러 파일

```python
# 예시 1: workflow_executor.py:96
except Exception as e:
    logger.warning(f"커스텀 워커 로드 실패: {e}", exc_info=True)

# 예시 2: workflow_condition_evaluator.py:257, 400
except Exception as e:
    logger.error(f"LLM 조건 평가 실패: {e}")

# 예시 3: sdk_executor.py:169, 233, 588
except Exception:
    # 조용히 실패 (에러 메시지 없음)
```

**심각도**: 🟡 **Medium**

**문제점**:
- 일반적인 `Exception`을 캐칭하면 의도하지 않은 버그까지 숨김
- 예: `NameError`, `TypeError`, `RuntimeError` 등 예상치 못한 에러가 로깅되지 않음
- 디버깅 어려움 및 버그 추적 실패

**영향받는 파일** (26개):
- workflow_condition_evaluator.py (257, 400줄)
- workflow_executor.py (96, 305줄)
- workflow_node_executor.py (210줄)
- infrastructure/claude/worker_client.py (78, 91, 190, 264줄)
- infrastructure/claude/sdk_executor.py (169, 233, 588, 737, 791줄)
- 등 (총 26개 위치)

**개선 권장사항**:

```python
# Before: 너무 광범위함
try:
    custom_workers = custom_repo.load_custom_workers()
except Exception as e:
    logger.warning(f"커스텀 워커 로드 실패: {e}", exc_info=True)

# After: 구체적인 예외만 처리
try:
    custom_workers = custom_repo.load_custom_workers()
except (FileNotFoundError, JSONDecodeError) as e:
    logger.warning(f"커스텀 워커 설정 파일 오류: {e}")
except PermissionError as e:
    logger.warning(f"커스텀 워커 디렉토리 권한 오류: {e}")
except Exception as e:
    logger.error(f"예상치 못한 커스텀 워커 로드 오류: {e}", exc_info=True)
    raise
```

**우선순위 파일** (수정 순서):
1. workflow_condition_evaluator.py - LLM 평가 관련
2. infrastructure/claude/sdk_executor.py - SDK 호출 관련
3. workflow_executor.py - 메인 실행 엔진

---

### BUG-P003: 프로젝트 경로 모듈 변수 사용

**위치**:
- `src/presentation/web/routers/workflows/execution.py:90-97`
- `src/presentation/web/routers/projects/dependencies.py:?`

**심각도**: 🟡 **Medium**

**문제점**:

```python
# execution.py:87-97
from src.presentation.web.routers.projects import dependencies as projects_deps

_current_project_path = projects_deps._current_project_path
logger.info(f"[{session_id}] 프로젝트 경로 확인: {_current_project_path}")
if _current_project_path is None:
    logger.error(f"[{session_id}] 프로젝트 미선택 상태에서 워크플로우 실행 시도")
    raise HTTPException(...)
```

**위험**:
- 모듈 변수 `_current_project_path`는 런타임에 동적으로 변경됨
- 두 개 이상의 동시 요청이 있을 때 Race Condition 가능
- 요청 A가 프로젝트 A를 선택 → 프로젝트 B 선택 → 요청 B 처리 중 요청 A가 실행됨
  → 요청 A가 프로젝트 B에서 실행될 수 있음

**시나리오**:
```
[Request 1] 사용자 A: 프로젝트 A 선택 (설정 project_path = A)
[Request 2] 사용자 B: 프로젝트 B 선택 (설정 project_path = B) ← Race condition!
[Request 1] 워크플로우 실행 (project_path = B 사용!) ❌ 의도와 다름
```

**개선 권선사항**:

```python
# 모듈 변수 대신 FastAPI Context 또는 요청 매개변수 사용
from fastapi import Request

@router.post("/execute")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    http_request: Request,  # FastAPI 요청 객체
    bg_manager: BackgroundWorkflowManager = Depends(get_background_manager),
):
    # 요청 세션에서 프로젝트 경로 가져오기
    project_path = http_request.session.get("project_path")

    # 또는 요청 헤더에서 추출
    project_path = http_request.headers.get("X-Project-Path")
```

---

### BUG-P004: 잠재적 Race Condition (워크플로우 캐시)

**위치**:
- `src/presentation/web/services/workflow_executor.py:65, 99-100`
- `src/presentation/web/routers/workflows/dependencies.py:?`

**심각도**: 🟡 **Medium**

**문제점**:

```python
# workflow_executor.py:62-71
# 메모리 기반 캐시 (여러 워크플로우 실행에 걸쳐 유지)
self._node_sessions: Dict[str, str] = {}  # {node_id: session_id}
self._node_session_history: Dict[str, List[Dict[str, Any]]] = {}
self._node_agent_names: Dict[str, str] = {}
```

**위험**:
- WorkflowExecutor가 프로젝트별로 캐싱되어 메모리에 유지됨
- 여러 워크플로우 실행이 동시에 발생하면 `_node_sessions` 딕셔너리 접근 시 Race Condition 가능
- 예: 워크플로우 A가 node-1의 세션을 저장 중 → 워크플로우 B가 동시에 node-1의 세션 읽음 → 불일치

**시나리오**:
```python
# Thread 1 (WorkflowA)
self._node_sessions["node-1"] = "session-A"

# Thread 2 (WorkflowB) - 동시 실행
session = self._node_sessions.get("node-1")  # ← "session-A" 또는 "session-B"?

# Thread 1 계속
self._node_sessions["node-1"] = "session-A-updated"  # ← 순서 불명확
```

**영향**:
- 노드 세션 재활용 오류
- 여러 워크플로우가 같은 세션 ID를 사용하게 될 수 있음
- 컨텍스트 혼동 및 결과 오염

**개선 권선사항**:

```python
# 1. Lock 추가
import asyncio
from threading import RLock

class WorkflowExecutor:
    def __init__(self):
        self._lock = RLock()
        self._node_sessions: Dict[str, str] = {}

    async def execute(self):
        with self._lock:
            previous_session = self._node_sessions.get(node_id)
```

또는

```python
# 2. 각 워크플로우 실행 인스턴스에서 로컬 변수 사용
async def execute_workflow(self, session_id):
    local_node_sessions = {}  # 로컬 변수 (공유 불가)
    # ... 실행 ...
```

---

### BUG-P005: JSON 파싱 예외 처리 누락

**위치**: `src/presentation/web/routers/custom_workers.py:52-59`

**심각도**: 🟡 **Medium**

**문제점**:

```python
def load_session_state(session_id: str) -> Optional[dict]:
    """세션 상태를 파일에서 로드"""
    session_dir = get_session_dir(session_id)
    state_file = session_dir / "state.json"
    if state_file.exists():
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)  # ❌ JSONDecodeError 처리 없음
    return None
```

**위험**:
- 파일은 있지만 JSON이 손상된 경우 `JSONDecodeError` 발생
- 예외를 처리하지 않으면 500 에러 발생
- 정상적인 폴백 처리 불가능

**개선**:

```python
def load_session_state(session_id: str) -> Optional[dict]:
    """세션 상태를 파일에서 로드"""
    session_dir = get_session_dir(session_id)
    state_file = session_dir / "state.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"세션 상태 파일 손상: {state_file} - {e}")
            return None  # 폴백: None 반환
    return None
```

---

### BUG-P006: Dictionary 접근 시 KeyError 가능성

**위치**: `src/presentation/web/services/workflow_condition_evaluator.py:542`

**심각도**: 🟡 **Medium**

**문제점**:

```python
# 542줄
result_text += f"반복 횟수: {current_iteration}/{max_iterations}\n"
```

`max_iterations`이 None일 수 있는데 f-string에 직접 사용됨.

**실제로는**:
```python
# 481-482줄
max_iter_display = max_iterations if max_iterations is not None else "무제한"
```

올바르게 처리되어 있음. ✅ (거짓 경고)

---

## 🔵 Low 우선순위 이슈

### BUG-P007: 명시적 None 체크 부재 (Low)

**위치**: `src/presentation/web/services/workflow_executor.py:129`

**심각도**: 🔵 **Low**

**문제점**:

```python
config = self.agent_config_map.get(agent_name)
if not config:  # ← "if not config"는 None뿐만 아니라 빈 객체도 걸러냄
    raise ValueError(...)
```

**개선** (코드 명확성):

```python
config = self.agent_config_map.get(agent_name)
if config is None:  # ← 명시적 None 체크가 더 명확
    raise ValueError(...)
```

---

### BUG-P008: 하드코딩된 모델명 (Low)

**위치**: 여러 파일

**심각도**: 🔵 **Low**

**예시**:

```python
# workflow_condition_evaluator.py:143
options = ClaudeAgentOptions(
    model=WorkflowConfig.HAIKU_MODEL,  # ✅ 상수 사용 (좋음)
)

# sdk_executor.py:49
model: str = "claude-sonnet-4-5-20250929"  # ⚠️ 하드코딩 (나쁨)
```

**권장**:

```python
# constants.py에서 정의
CLAUDE_SONNET_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20251001"

# 사용
model: str = CLAUDE_SONNET_MODEL
```

---

## ✅ 이미 수정된 이슈들

### BUG-002: Path Traversal (CWE-22) ✅

**상태**: 🟢 **완료**

**위치**: `src/presentation/web/routers/filesystem.py:92-128, 186-190`

**수정 내용**:
- `is_safe_path()` 함수로 경로 검증
- `browse_directory()`에서 검증 적용
- `../../../../../etc` 같은 공격 차단

---

### BUG-003: Remote Code Execution via eval() (CWE-94) ⚠️

**상태**: 🟡 **부분 수정**

**위치**: `src/presentation/web/services/workflow_condition_evaluator.py:55-117, 363-402`

**현재 방어**:
- ✅ AST 화이트리스트 검증 추가
- ✅ 제한된 네임스페이스 사용
- ⚠️ eval() 자체는 여전히 사용 중

**향후 계획**: eval() 완전 제거 (위의 BUG-P001 참조)

---

## 📈 코드 품질 지표

### 리소스 누수 (Resource Leak)

**상태**: ✅ **양호**

분석 결과:
- ✅ 파일 I/O: 모두 `with` 문 사용
- ✅ 네트워크 연결: SDK 자동 관리
- ✅ 데이터베이스: 현재 사용하지 않음

---

### None 참조 오류 (NullPointerException)

**상태**: 🟡 **부분 처리됨**

- ✅ 주요 경로에서는 None 체크 존재
- ⚠️ 일부 헬퍼 함수에서 명시적 체크 부재
- ⚠️ Dictionary.get() 사용 후 None 체크 불일치

---

### 예외 처리 (Exception Handling)

**상태**: 🟡 **개선 필요**

- ❌ 광범위한 `except Exception` 사용 (26개 위치)
- ✅ 중요 경로에서는 구체적 예외 처리
- ⚠️ 일부 예외 조용히 무시됨

---

### 동시성 (Concurrency)

**상태**: 🟡 **위험 요소 있음**

- ⚠️ 모듈 변수로 공유 상태 관리
- ⚠️ Dictionary 동시 접근 시 Race Condition 가능
- ✅ asyncio 기본 구조는 적절함

---

## 🛠️ 수정 로드맵

### Phase 1: 즉시 (1주)
- [ ] BUG-P001: eval() 함수 대체 (High)
- [ ] BUG-P002: 광범위 Exception 수정 (Medium)

### Phase 2: 단기 (2-3주)
- [ ] BUG-P003: 프로젝트 경로 Race Condition (Medium)
- [ ] BUG-P004: WorkflowExecutor 캐시 동시성 (Medium)
- [ ] BUG-P005: JSON 파싱 예외 처리 (Medium)

### Phase 3: 장기 (1개월)
- [ ] BUG-P007, P008: 코드 품질 개선 (Low)
- [ ] 단위 테스트 추가 (pytest)
- [ ] 정적 분석 도구 통합 (pylint, mypy strict mode)

---

## 🧪 권장 테스트

### 보안 테스트
```python
# test_security.py

# 1. eval() RCE 테스트
def test_eval_injection_prevention():
    from workflow_condition_evaluator import evaluate_condition

    # 악의적인 조건식
    malicious_inputs = [
        "__import__('os').system('rm -rf /')",
        "open('/etc/passwd').read()",
        "(lambda: __import__('os').system('ls'))()",
    ]

    for payload in malicious_inputs:
        result = evaluate_condition("custom", payload, "test")
        assert result is False  # 모두 False를 반환해야 함

# 2. Path Traversal 테스트
def test_path_traversal_prevention():
    from filesystem import is_safe_path
    from pathlib import Path

    attacks = [
        "../../../../../../etc/passwd",
        "/etc/passwd",
        "../../../.ssh/id_rsa",
    ]

    for attack in attacks:
        safe = is_safe_path(Path.home(), Path(attack).resolve())
        assert not safe
```

### 동시성 테스트
```python
# test_concurrency.py
import asyncio
import pytest

@pytest.mark.asyncio
async def test_concurrent_workflow_execution():
    """여러 워크플로우 동시 실행 시 세션 혼동 없음"""

    # 3개의 워크플로우를 동시에 실행
    results = await asyncio.gather(
        execute_workflow("workflow-A", "project-A"),
        execute_workflow("workflow-B", "project-B"),
        execute_workflow("workflow-C", "project-C"),
    )

    # 각 워크플로우가 올바른 프로젝트에서 실행되었는지 확인
    assert results[0]["project"] == "project-A"
    assert results[1]["project"] == "project-B"
    assert results[2]["project"] == "project-C"
```

---

## 📋 체크리스트

감사 과정:
- [x] Python 코드 정적 분석 (Grep, AST)
- [x] TypeScript/React 코드 검토
- [x] 보안 취약점 확인 (CWE, OWASP Top 10)
- [x] 리소스 누수 확인
- [x] 동시성 이슈 확인
- [x] 예외 처리 검증

---

## 📚 참고 자료

- **CWE-22**: Path Traversal - https://cwe.mitre.org/data/definitions/22.html
- **CWE-94**: Code Injection - https://cwe.mitre.org/data/definitions/94.html
- **OWASP**: Secure Coding Guidelines - https://owasp.org/

---

## 결론

코드베이스는 **전반적으로 양호**하지만, 다음 영역에서 개선이 필요합니다:

1. **eval() 함수 사용 (High)**: AST 검증이 있으나 완전히 제거 필요
2. **예외 처리 (Medium)**: 광범위한 Exception 캐칭 개선
3. **동시성 (Medium)**: Race Condition 위험 요소 제거
4. **코드 품질 (Low)**: 명확성 및 유지보수성 개선

**권장 조치**: Phase 1 수정 사항을 우선순위로 진행하고, 향후 정적 분석 도구를 CI/CD에 통합할 것.

---

**보고서 작성자**: Claude Code Audit Agent
**보고서 생성 일시**: 2025-01-15
**감사 완료**: ✅
