# Changelog

All notable changes to Claude Flow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [4.0.1] - 2025-11-06

### Added

#### 여러 Input 노드 병렬 실행 기능
- 여러 Input 노드를 동시에 실행 가능
- 독립적인 워크플로우 경로를 병렬로 처리
- 기존 단일 Input 로직 100% 호환
- Merge 노드와 완벽히 연동 (여러 경로 수렴)

**구현 세부사항**:
- `_find_start_nodes()` 함수 구현: 모든 Input 노드 반환 (List[str])
- 병렬 Input 실행 로직 추가 (`_execute_nodes_in_parallel()`)
- 병렬 실행 후 다음 노드 결정 (Merge 노드 감지 및 대기 큐 관리)

**수정 파일**:
- `src/presentation/web/services/workflow_executor.py` (272-311줄, 560-677줄)

**테스트 파일**:
- `test_parallel_inputs.py`: 3개 Input 노드 병렬 실행 검증

#### Worker 노드 출력 추출 설정 UI
- Worker 노드 설정의 "고급 설정" 섹션에 "출력 추출 전략" UI 추가
- 3가지 전략 선택 가능: 전체 텍스트, 마지막 블록만, 마커 사이 텍스트
- 백엔드의 `extract_text_with_strategy()` 함수와 완벽 호환

**수정 파일**:
- `src/presentation/web/frontend/src/components/node-config/WorkerNodeConfig.tsx`

#### 로그 상세 모달 노드 필터링 기능
- 로그 상세 모달 헤더에 노드 필터 드롭다운 추가
- 특정 노드 선택 시 해당 노드의 로그만 전체 화면으로 표시
- "모든 노드" 옵션으로 기존 동작 유지

**수정 파일**:
- `src/presentation/web/frontend/src/components/LogDetailModal.tsx`

#### 자동 출력 추출 기능
- Worker 출력에서 표준 마커 자동 감지 (`---NEXT_WORKER_OUTPUT_START/END---`)
- Zero-configuration: 설정 없이 자동으로 핵심 출력만 추출
- 우선순위: 사용자 지정 > 자동 마커 > 전체 텍스트

**수정 파일**:
- `src/presentation/web/services/workflow_utils.py` (extract_text_with_strategy)

### Fixed

#### Condition 노드 SDK 실행 로그 스트리밍 구현 (Critical)
- Condition 노드의 LLM 조건 평가 시 SDK 실행 과정이 UI에 전혀 표시되지 않는 버그 수정
- `evaluate_llm_condition_stream()` 제너레이터 구현: 실시간 스트리밍 지원
- `execute_condition_node_stream()` 제너레이터 구현: 일반 조건 평가 결과도 출력
- Worker 노드와 동일한 패턴으로 이벤트 스트리밍
- 디버깅 로그 강화 (입력값 확인, 전달값 확인)

**수정 파일**:
- `src/presentation/web/services/workflow_condition_evaluator.py` (119-319줄)
- `src/presentation/web/services/node_executors/condition_executor.py` (57-139줄)

#### LLM 조건 평가 CLI 경로 버그 수정 (Critical)
- Claude Agent SDK가 쉘 alias를 인식하지 못해 잘못된 CLI 버전(1.0.103) 사용하는 문제 수정
- Claude CLI 경로 명시적 지정 (`~/.claude/local/claude`)
- 에러 처리 개선: 실제 에러 타입과 메시지를 명확히 표시
- Fallback: LLM 실패 시 False 반환 (워크플로우 중단 방지)

**수정 파일**:
- `src/presentation/web/services/workflow_condition_evaluator.py` (145-151줄, 263-276줄)

#### 프로젝트별 로그 경로 버그 수정
- 로그가 `~/.claude-flow/{project-name}/logs`에 저장되지 않고 하드코딩된 경로에 저장되는 문제 수정
- `project_path`가 None일 때 `self.project_path` 사용

**수정 파일**:
- `src/presentation/web/services/workflow_executor.py:418`

#### 동적 워크플로우 실행 엔진 구현 (Condition 분기 완벽 지원)
- 위상 정렬이 Condition 노드의 `next_node_id`를 무시하는 Critical 버그 수정
- 동적 노드 선택 알고리즘으로 전면 재작성
- Condition 분기 완벽 지원
- 피드백 루프 지원 (Condition이 이전 노드로 분기 가능)
- Condition 노드 재실행 허용
- Merge 노드 대기 로직
- 무한 루프 방지

**수정 파일**:
- `src/presentation/web/services/workflow_executor.py` (270-504줄)
- `src/infrastructure/claude/__init__.py` (존재하지 않는 import 제거)

**테스트 파일**:
- `test_dynamic_execution.py`

#### Condition 노드 max_iterations null 처리 버그 수정 (Critical)
- Condition 노드가 false로 평가되어도 무조건 true 경로로 분기하는 버그 수정
- `max_iterations = null` (기본값) → 반복 제한 없음 (조건 평가 결과를 정확히 따름)
- `max_iterations = 3` (체크박스 ON) → 3회 반복 후 강제 true

**수정 파일**:
- `src/presentation/web/services/workflow_condition_evaluator.py` (396-417줄)

#### Condition 노드 입력값 전달 버그 수정 (Critical)
- Condition 노드가 평가 결과 메타정보를 다음 노드로 전달하는 버그 수정
- 부모 노드의 출력을 그대로 전달하도록 수정
- Condition 노드는 분기만 수행하고 데이터 변환은 하지 않음

**수정 파일**:
- `src/presentation/web/services/node_executors/condition_executor.py` (91-113줄)

#### 커스텀 워커 캐시 무효화 개선
- 커스텀 워커 저장/삭제 후 `WorkflowExecutor` 캐시 무효화 추가
- 새 워커가 즉시 반영되도록 수정

**수정 파일**:
- `src/presentation/web/routers/workflows/dependencies.py` (캐시 무효화 함수 추가)
- `src/presentation/web/routers/custom_workers.py` (저장/삭제 시 캐시 무효화 호출)

#### 세션 관리 버그 수정 (Critical) - 6개 버그 해결

**BUG-002**: 노드별 SDK 세션 ID가 워크플로우 세션에 저장되지 않음
- `WorkflowSession`에 `node_sdk_sessions` 필드 추가
- `update_node_session()` 수정: 워크플로우 세션에도 저장
- 브라우저 새로고침 시 노드 세션 복원 가능

**수정 파일**:
- `src/presentation/web/services/workflow_session_store.py` (26줄)
- `src/presentation/web/services/workflow_executor.py` (160-190줄)

**BUG-001**: Input 노드별 세션 ID 충돌
- localStorage는 워크플로우 세션 ID를 저장 (전체 워크플로우 공유)
- Input 노드별 로컬 상태는 `currentSessionId`로 관리

**수정 파일**:
- `src/presentation/web/frontend/src/components/InputNode.tsx` (209-223줄)

**BUG-003**: 세션 복원 시 노드 SDK 세션 동기화 안 됨
- `execute_workflow()`에 `restore_node_sdk_sessions` 파라미터 추가
- 자동 복원 로직 구현 (워크플로우 세션에서 로드)

**수정 파일**:
- `src/presentation/web/services/workflow_executor.py` (419줄, 478-488줄)

**BUG-004**: 프론트엔드 세션 유효성 검증 누락
- localStorage 구조 변경: 세션 ID + 타임스탬프 저장
- 24시간 TTL 검증 로직 추가
- 만료된 세션 자동 삭제

**수정 파일**:
- `src/presentation/web/frontend/src/components/InputNode.tsx` (216-222줄)
- `src/presentation/web/frontend/src/hooks/useSessionRestore.ts` (71-108줄)

**BUG-005**: 여러 Input 노드 병렬 실행 시 세션 충돌
- BUG-001 수정으로 자동 해결

**BUG-006**: 워크플로우 세션 vs 노드 SDK 세션 개념 혼동
- 문서에 명확한 개념 정의 추가
- 코드 주석에 명시적으로 표기

### Changed

#### 프롬프트 라이브러리 출력 형식 개선
- 전체 46개 프롬프트 수정 (100%)
- "작업 완료 시 필수 조치" 섹션 추가:
  - 1. 상세 작업 보고서 (파일로 저장)
  - 2. 다음 워커를 위한 요약 (마커로 감싸서 텍스트로 출력)
- 표준 마커 사용: `---NEXT_WORKER_OUTPUT_START/END---`
- "올바른 예시"와 "잘못된 예시" 추가

**수정 프롬프트 목록**: `PROMPT_UPDATE_REPORT.md` 참조

#### workflow_designer 프롬프트 출력 형식 정리
- "작업 완료 시 필수 조치" 섹션 삭제 (69줄)
- "출력 규칙" 섹션으로 대체 (11줄)
- UI로 직접 반환됨을 명시
- JSON 형식만 출력하도록 간결화

**수정 파일**:
- `prompts/workflow_designer.txt` (962-1030줄 → 962-972줄)

---

## [4.0.0] - 2025-11-05

### Security

#### BUG-002: Path Traversal (CWE-22) 수정
- `is_safe_path()` 함수가 정의되어 있으나 `browse_directory()`에서 호출되지 않는 문제 수정
- 디렉토리 탐색 시 경로 검증 추가

**수정 파일**:
- `src/presentation/web/routers/filesystem.py`

#### BUG-003: Remote Code Execution (CWE-94) 수정
- Condition 노드의 "custom" 타입에서 `eval()` 직접 사용하는 문제 수정
- AST 기반 화이트리스트 파싱 구현 (`_is_safe_ast_node()`)
- 허용 함수: `len`, `str`, `int`, `float`, `bool`, `abs`, `min`, `max`, `sum`, `round`, `pow`
- 차단: 속성 접근, 메서드 호출, 위험한 함수 호출

**수정 파일**:
- `src/presentation/web/services/workflow_condition_evaluator.py`

**테스트 결과**: ✅ 11/11 통과
- Path Traversal 방어: 4/4 통과
- RCE 방지: 7/7 통과

자세한 내용은 [SECURITY.md](SECURITY.md) 참조

### Added

#### UI/UX 개선
- Worker 노드 출력 추출 설정 UI 추가
- 로그 상세 모달 노드 필터링 기능 추가

---

## 문서 참조

- **보안 가이드**: [SECURITY.md](SECURITY.md)
- **프롬프트 업데이트 보고서**: [PROMPT_UPDATE_REPORT.md](PROMPT_UPDATE_REPORT.md)
- **동적 실행 알고리즘**: [dynamic_execution_algorithm.md](dynamic_execution_algorithm.md)
- **워크플로우 실행 수정 계획**: [workflow_execution_fix_plan.md](workflow_execution_fix_plan.md)
