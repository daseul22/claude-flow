# Claude Flow Code Reference

**프로젝트**: Claude Flow v4.0.0
**작성일**: 2025-11-05
**목적**: 핵심 클래스, 함수, 아키텍처 패턴, 워크플로우 실행 엔진의 상세 가이드

---

## 📚 관련 문서

- **[문서 INDEX](INDEX.md)** - 모든 문서의 전체 목록
- **[아키텍처](architecture.md)** - 시스템 설계 및 컴포넌트
- **[데이터베이스](database.md)** - 데이터 모델 및 스키마
- **[API 레퍼런스](api.md)** - REST API 엔드포인트
- **[프로젝트 문서](../CLAUDE.md)** - 프로젝트 개요 및 명령어

---

## 목차

1. [아키텍처 개요](#아키텍처-개요)
2. [도메인 모델 (Domain Layer)](#도메인-모델-domain-layer)
3. [인프라 레이어 (Infrastructure Layer)](#인프라-레이어-infrastructure-layer)
4. [워크플로우 실행 엔진 (Services Layer)](#워크플로우-실행-엔진-services-layer)
5. [API 레이어 (Presentation Layer)](#api-레이어-presentation-layer)
6. [설정 및 로깅](#설정-및-로깅)
7. [주요 알고리즘](#주요-알고리즘)
8. [코드 컨벤션 및 패턴](#코드-컨벤션-및-패턴)

---

## 아키텍처 개요

### Clean Architecture (4-레이어)

```
┌─────────────────────────────────────────┐
│     Presentation Layer (Web UI)          │  REST API (FastAPI)
│     - routers/     (API 엔드포인트)     │  React Frontend
│     - services/    (비즈니스 로직)      │
│     - schemas/     (Pydantic 모델)      │
├─────────────────────────────────────────┤
│     Application Layer                    │  (현재 비어있음)
│     (비즈니스 규칙 - 향후 이동)        │
├─────────────────────────────────────────┤
│     Infrastructure Layer                 │  외부 시스템 통합
│     - claude/      (Claude SDK)          │  Config, Logging, Storage
│     - config/      (설정 로드)           │
│     - logging/     (로깅)                │
│     - storage/     (파일 저장소)         │
│     - errors/      (에러 정의)           │
├─────────────────────────────────────────┤
│     Domain Layer                         │  핵심 도메인 모델
│     - models/      (AgentConfig, Message)│
└─────────────────────────────────────────┘
```

### 디자인 패턴 사용

| 패턴 | 위치 | 목적 |
|------|------|------|
| **Clean Architecture** | 전체 | 계층 분리, 의존성 역전 |
| **Strategy Pattern** | `WorkflowNodeExecutor` | 노드 타입별 실행기 선택 |
| **Template Method Pattern** | `SDKExecutor` | SDK 실행 템플릿화 |
| **Facade Pattern** | `WorkflowExecutor` | 복잡한 워크플로우 오케스트레이션 단순화 |
| **Repository Pattern** | `CustomWorkerRepository` | 파일 저장소 추상화 |
| **Observer Pattern** | SSE 스트리밍 | 실시간 이벤트 전송 |
| **Dependency Injection** | 전체 | 느슨한 결합 |

---

## 도메인 모델 (Domain Layer)

### 1. AgentConfig (에이전트 설정)

**파일**: `src/domain/models/agent.py`

```python
@dataclass
class AgentConfig:
    """
    에이전트(Worker) 설정 도메인 모델

    Worker의 역할, 시스템 프롬프트, 사용 가능한 도구, Claude 모델을 정의합니다.
    JSON 직렬화/역직렬화를 지원합니다.

    Attributes:
        name (str): 에이전트 식별자 (예: 'backend_coder', 'bug_fixer')
            - 프롬프트 파일명과 일치 (확장자 제외)
            - config/agent_config.json에 정의됨

        role (str): 에이전트 역할 설명 (예: '백엔드 개발 전문가')
            - UI에서 표시됨
            - 사용자가 Worker를 선택할 때 참고

        system_prompt (str): 시스템 프롬프트 또는 파일 경로
            - 파일 경로: 'prompts/backend_coder.txt'
            - WorkerAgent가 자동으로 파일 로드
            - 프로젝트 루트 기준 경로 해석

        allowed_tools (List[str]): 사용 가능한 도구 목록
            - 예: ['read', 'write', 'edit', 'bash', 'glob', 'grep']
            - Claude Agent SDK에서 지원하는 도구만 사용 가능
            - 보안: 필요한 도구만 명시적으로 허용

        model (str): Claude 모델명
            - 기본값: 'claude-sonnet-4-5-20250929'
            - 예: 'claude-haiku-4-5-20251001', 'claude-opus'
            - v4.0.0부터는 각 Worker마다 다른 모델 사용 가능

        thinking (bool): Thinking 모드 활성화 여부
            - True: 복잡한 추론이 필요한 Worker에 권장
            - False: 단순 작업은 비활성화로 성능 향상
            - claude-sonnet 이상에서만 지원

    Examples:
        >>> config = AgentConfig(
        ...     name='backend_coder',
        ...     role='백엔드 개발 전문가',
        ...     system_prompt='prompts/backend_coder.txt',
        ...     allowed_tools=['read', 'write', 'bash'],
        ...     model='claude-sonnet-4-5-20250929',
        ...     thinking=True
        ... )
        >>> config.to_dict()
        {'name': 'backend_coder', ...}
    """
    name: str
    role: str
    system_prompt: str
    allowed_tools: List[str]
    model: str = "claude-sonnet-4-5-20250929"
    thinking: bool = False

    def to_dict(self) -> dict:
        """JSON 직렬화용 딕셔너리 변환"""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        """딕셔너리에서 AgentConfig 객체 생성"""
        ...


class AgentRole(str, Enum):
    """에이전트 역할 (Enum) - 참고용"""
    MANAGER = "manager"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
```

---

### 2. Message (대화 메시지)

**파일**: `src/domain/models/message.py`

```python
@dataclass
class Message:
    """
    대화 메시지 도메인 모델

    Worker 간 통신, 세션 저장, 로그 기록에 사용되는 메시지 모델입니다.
    타임스탬프를 자동으로 기록합니다.

    Attributes:
        role (str): 메시지 발신자 역할
            - 'user': 사용자 입력 (워크플로우 시작점)
            - 'agent': Worker 에이전트 응답
            - 'manager': Manager 에이전트 (현재 미사용)
            - 'system': 시스템 메시지 (오류, 진행 상황)

        content (str): 메시지 본문
            - Worker 응답: 코드, 분석 결과, 보고서 등
            - 사용자 입력: 초기 입력 또는 Human-in-the-Loop 응답

        agent_name (str, optional): 에이전트 이름 (role='agent'일 경우)
            - 예: 'backend_coder', 'bug_fixer'
            - 세션 이력에서 어떤 Worker가 응답했는지 추적

        timestamp (datetime): 메시지 생성 시각
            - 기본값: datetime.now()
            - ISO 8601 형식으로 저장/로드

    Examples:
        >>> msg = Message(
        ...     role='user',
        ...     content='사용자 초기 입력'
        ... )
        >>> msg_dict = msg.to_dict()
        >>> msg2 = Message.from_dict(msg_dict)
    """
    role: str
    content: str
    agent_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """JSON 직렬화 (timestamp를 ISO 형식으로 변환)"""
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """JSON 역직렬화 (ISO timestamp 파싱)"""
        ...


class Role(str, Enum):
    """메시지 역할 (Enum)"""
    USER = "user"
    AGENT = "agent"
    MANAGER = "manager"
    SYSTEM = "system"
```

---

## 인프라 레이어 (Infrastructure Layer)

### 1. Claude SDK 통합

#### 1.1 WorkerAgent (Worker 인스턴스)

**파일**: `src/infrastructure/claude/worker_client.py`

```python
class WorkerAgent:
    """
    실제 작업을 수행하는 Worker 에이전트

    Claude Agent SDK를 사용하여 Claude Code의 모든 기능
    (파일 읽기/쓰기, bash 실행, grep 등)을 프로그래밍 방식으로 호출합니다.

    **세션 재활용**: 같은 노드를 여러 번 실행할 때 컨텍스트 유지
    **Human-in-the-Loop**: Worker가 사용자 입력을 요청할 수 있음

    Attributes:
        config (AgentConfig): 에이전트 설정
        project_dir (str, optional): 프로젝트 디렉토리 (CLAUDE.md 로드용)
        system_prompt (str): 로드된 시스템 프롬프트 (파일 또는 문자열)
        last_session_id (str, optional): 마지막 실행의 세션 ID

    Methods:
        query(): Worker에게 작업 전달 (스트리밍 응답, resume_session_id로 세션 재개 지원)
    """

    def __init__(
        self,
        config: AgentConfig,
        project_dir: Optional[str] = None
    ):
        """
        WorkerAgent 초기화

        Args:
            config: AgentConfig 객체
            project_dir: 프로젝트 디렉토리 경로
                - 사용 목적: CLAUDE.md 자동 로드
                - 선택 사항: None이면 프로젝트 CLAUDE.md 미로드
        """
        ...

    def _load_system_prompt(self) -> str:
        """
        시스템 프롬프트 로드

        우선순위:
        1. config.system_prompt가 파일이면 파일 로드
        2. 그렇지 않으면 문자열 그대로 사용
        3. 프로젝트 컨텍스트 추가 (project_dir 지정 시)

        Returns:
            str: 최종 시스템 프롬프트

        Raises:
            (None - 파일 없으면 경고 로깅하고 기본값 사용)
        """
        ...

    async def query(
        self,
        task: str,
        system_prompt: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        thinking: bool = False,
        resume_session_id: Optional[str] = None,
        user_input_callback: Optional[Callable] = None,
    ) -> AsyncIterator[dict]:
        """
        Worker에게 작업 전달 및 스트리밍 응답 수신

        Claude Agent SDK를 사용하여 비동기 스트리밍으로 응답받습니다.
        응답은 여러 개의 텍스트 블록으로 나뉘어 전달될 수 있습니다.

        Args:
            task (str): Worker에게 전달할 작업 프롬프트
                - 예: "다음 코드의 버그를 찾고 수정해주세요:\n[코드]"

            system_prompt (str, optional): 오버라이드 시스템 프롬프트
                - 기본값: self.system_prompt (config에서 로드된 값)
                - 사용 목적: 런타임에 프롬프트 동적 변경

            allowed_tools (List[str], optional): 오버라이드 도구 목록
                - 기본값: self.config.allowed_tools
                - 예: ['read', 'write', 'edit', 'bash']

            model (str, optional): 오버라이드 모델명
                - 기본값: self.config.model
                - 런타임에 다른 모델로 변경 가능

            thinking (bool): Thinking 모드 활성화
                - True: 복잡한 추론 수행
                - False: 빠른 응답 (기본값)

            resume_session_id (str, optional): 이전 세션 ID (세션 재활용)
                - 지정 시: 해당 세션의 컨텍스트 유지
                - None: 새로운 세션 시작
                - 사용 목적: 워크플로우 노드별 컨텍스트 유지

            user_input_callback (Callable, optional): 사용자 입력 콜백
                - Human-in-the-Loop 지원
                - Worker가 @ASK_USER: 패턴 출력 시 호출

        Yields:
            dict: 스트리밍 응답 (텍스트 블록 단위)
                - 예: {'text': '응답 내용', 'session_id': '...'}

        Raises:
            ValueError: 모델이나 도구가 지원되지 않음
            Exception: SDK 실행 오류

        Examples:
            >>> agent = WorkerAgent(config)
            >>> async for chunk in agent.query("버그를 찾아주세요"):
            ...     print(chunk['text'])

            # 세션 재활용 (컨텍스트 유지)
            >>> async for chunk in agent.query("다음 단계를 수행해주세요",
            ...     resume_session_id='session-123'):
            ...     print(chunk['text'])
        """
        ...
```

#### 1.2 SDKExecutor (SDK 실행 래퍼)

**파일**: `src/infrastructure/claude/sdk_executor.py`

```python
class SDKExecutionConfig:
    """SDK 실행 설정"""
    task: str
    system_prompt: str
    allowed_tools: List[str]
    model: str
    thinking: bool
    resume_session_id: Optional[str]
    user_input_callback: Optional[Callable]


class WorkerSDKExecutor:
    """
    Template Method Pattern 구현

    Claude Agent SDK 실행을 추상화한 실행 래퍼입니다.

    Methods:
        query(): 설정에 따라 SDK 실행 및 응답 처리
    """

    async def query(self, config: SDKExecutionConfig) -> AsyncIterator[dict]:
        """
        SDK 호출 및 응답 처리 (Template Method)

        내부 단계:
        1. 설정 검증 (validate_config)
        2. SDK 호출 (call_sdk)
        3. 응답 처리 (process_response)
        4. 토큰 추출 (extract_token_usage)

        Returns:
            AsyncIterator[dict]: 처리된 응답
        """
        ...


class WorkerResponseHandler:
    """
    응답 파싱 및 토큰 사용량 추출

    Methods:
        extract_token_usage(): 응답에서 토큰 사용량 파싱
        parse_response(): 응답 타입 결정 (AssistantMessage, ResultMessage 등)
    """

    @staticmethod
    def extract_token_usage(response: dict) -> dict:
        """
        응답에서 토큰 사용량 추출

        Args:
            response (dict): Claude SDK 응답

        Returns:
            dict: {'input_tokens': int, 'output_tokens': int}
        """
        ...
```

---

### 2. 설정 로더

**파일**: `src/infrastructure/config/loader.py`

```python
@dataclass
class SystemConfig:
    """
    시스템 설정 데이터 모델

    config/system_config.json에서 로드되는 설정입니다.
    Attributes는 JSON 필드와 1:1 대응됩니다.

    Attributes:
        manager_model (str): Manager 에이전트 모델
        max_history_messages (int): 세션별 최대 메시지 개수
        max_turns (int): 최대 대화 턴 수
        enable_caching (bool): 응답 캐싱 활성화
        worker_retry_enabled (bool): Worker 재시도 활성화
        worker_retry_max_attempts (int): 최대 재시도 횟수
        log_level (str): 로깅 레벨
        enable_structured_logging (bool): 구조화 로깅 활성화

    Methods:
        get(key, default=None): 딕셔너리 스타일 접근
        __getitem__(key): 배열 스타일 접근
    """
    ...


class JsonConfigLoader:
    """
    JSON 설정 로더

    config/agent_config.json (Worker 설정)과
    config/system_config.json (시스템 설정)을 로드합니다.

    v4.0.0부터 prompts/ 디렉토리 자동 스캔 기능 추가:
    - YAML Front Matter 파싱 (메타데이터)
    - 자동 Worker 등록 (agent_config.json 수동 등록 불필요)

    Methods:
        load_agent_configs(): Worker 설정 로드 (자동 스캔 포함)
        load_system_config(): 시스템 설정 로드
        _scan_prompts_directory(): prompts/ 디렉토리 자동 스캔
        _parse_prompt_metadata(): YAML Front Matter 파싱
    """

    def load_agent_configs(self, auto_scan: bool = True) -> List[AgentConfig]:
        """
        Worker 설정 로드 (하이브리드 방식)

        우선순위:
        1. config/agent_config.json (수동 등록, 최우선)
        2. prompts/ 디렉토리 (자동 스캔, v4.0.0+)
        3. 사용자 정의 프롬프트 (메타데이터 포함)

        Args:
            auto_scan (bool): prompts/ 디렉토리 자동 스캔 여부

        Returns:
            List[AgentConfig]: AgentConfig 객체 목록

        Example:
            config_loader = JsonConfigLoader()
            agents = config_loader.load_agent_configs()
            # Result: 내장 Worker + 자동 스캔 Worker 통합
        """
        ...

    def _scan_prompts_directory(self) -> List[AgentConfig]:
        """
        prompts/ 디렉토리에서 .txt 파일 자동 스캔

        각 .txt 파일은 다음과 같이 처리됩니다:
        1. YAML Front Matter 파싱 (선택 사항)
        2. 메타데이터 추출 (role, allowed_tools, model, thinking)
        3. AgentConfig 자동 생성

        YAML Front Matter 형식:
        ```
        ---
        role: 에이전트 역할
        allowed_tools:
          - read
          - write
        model: claude-sonnet-4-5-20250929
        thinking: true
        ---
        프롬프트 내용...
        ```

        기본값 (메타데이터 없을 경우):
        - role: '{파일명} 전문가'
        - allowed_tools: ['read', 'write', 'edit', 'glob', 'grep']
        - model: 'claude-sonnet-4-5-20250929'
        - thinking: true

        Returns:
            List[AgentConfig]: 스캔된 Worker 설정
        """
        ...

    def _parse_prompt_metadata(self, content: str) -> tuple[dict, str]:
        """
        프롬프트 파일에서 YAML Front Matter 파싱

        프롬프트의 첫 부분이 --- ... --- 사이의 YAML이면 파싱합니다.

        Args:
            content (str): 프롬프트 전체 내용

        Returns:
            tuple: (메타데이터 dict, 프롬프트 본문 str)

        Example:
            metadata, body = loader._parse_prompt_metadata(file_content)
            # metadata = {'role': '...', 'allowed_tools': [...]}
            # body = '프롬프트 본문...'
        """
        ...
```

---

### 3. 로깅

**파일**: `src/infrastructure/logging/structured_logger.py`

```python
class StructuredLogger:
    """
    구조화 로깅 (structlog 기반)

    세션별 파일 핸들러를 자동으로 관리합니다.
    각 세션의 로그는 별도 파일로 저장됩니다.

    Usage:
        logger = get_logger(__name__)
        logger.info("메시지", key=value)  # 구조화된 로깅
    """

    @staticmethod
    def add_session_file_handlers(session_id: str, project_path: Optional[str] = None) -> None:
        """
        세션별 파일 핸들러 추가

        로그 파일 경로: ~/.claude-flow/{project}/logs/{session_id}.log

        Args:
            session_id: 세션 ID
            project_path: 프로젝트 경로 (로그 디렉토리 결정)
        """
        ...

    @staticmethod
    def remove_session_file_handlers(session_id: str) -> None:
        """세션 종료 시 핸들러 제거"""
        ...
```

---

## 워크플로우 실행 엔진 (Services Layer)

### 1. WorkflowExecutor (메인 오케스트레이터)

**파일**: `src/presentation/web/services/workflow_executor.py`

```python
class WorkflowExecutor:
    """
    워크플로우 실행 엔진 (Facade Pattern)

    워크플로우의 복잡한 실행 로직을 단순화합니다:
    - 노드 위상 정렬
    - 병렬 실행 처리
    - 세션 관리 (컨텍스트 유지)
    - 취소 요청 처리
    - 실시간 이벤트 스트리밍 (SSE)

    **세션 관리**:
    - node_sessions: 노드별 현재 활성 SDK 세션 ID
    - node_session_history: 노드별 모든 세션 이력
    - 사용자가 과거 세션 선택 및 복원 가능

    **상태 관리**:
    - cancelled_sessions: 취소된 세션 추적
    - user_input_queues: Human-in-the-Loop 지원

    Attributes:
        config_loader (JsonConfigLoader): Agent 설정 로더
        agent_configs (List[AgentConfig]): 로드된 Agent 설정
        agent_config_map (Dict): Agent 이름 → 설정 매핑
        custom_worker_names (Set[str]): 커스텀 Worker 이름 집합
        project_path (str, optional): 프로젝트 경로
    """

    def __init__(
        self,
        config_loader: JsonConfigLoader,
        project_path: Optional[str] = None
    ):
        """
        WorkflowExecutor 초기화

        Args:
            config_loader: JsonConfigLoader 인스턴스
            project_path: 프로젝트 디렉토리 경로
                - 사용 목적: 커스텀 Worker 로드, 세션 로그 저장
        """
        ...

    def _get_agent_config(self, agent_name: str) -> AgentConfig:
        """
        Agent 설정 조회

        agent_name으로 Agent를 찾고, 없으면 명확한 에러 메시지 제공합니다.

        Args:
            agent_name (str): Agent 이름

        Returns:
            AgentConfig: Agent 설정

        Raises:
            ValueError: Agent를 찾을 수 없음
                - 사용 가능한 Agent 목록 제시
                - 커스텀 Worker의 경우 추가 안내
        """
        ...

    def cancel_session(self, session_id: str) -> None:
        """
        세션 취소 요청

        취소 플래그를 설정합니다. 워크플로우는 다음 기회에 중단됩니다.

        Args:
            session_id: 취소할 세션 ID
        """
        ...

    async def execute_workflow(
        self,
        workflow: Workflow,
        initial_input: str,
        session_id: str,
        project_path: Optional[str] = None,
        start_node_id: Optional[str] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        워크플로우 실행 (스트리밍, 병렬 실행 지원)

        내부 단계:
        1. 세션 초기화 (파일 핸들러, Queue, 상태)
        2. 그래프 분석 (위상 정렬, 병렬 그룹 계산)
        3. 노드 실행 (입력→Worker→조건→병합)
        4. 이벤트 스트리밍 (각 단계별 SSE 이벤트 전송)
        5. 정리 (핸들러 제거, 세션 종료)

        Args:
            workflow (Workflow): 실행할 워크플로우 객체
            initial_input (str): 초기 입력 데이터
                - Input 노드에 전달되는 초기값
            session_id (str): 세션 ID
                - 로그 파일명, 취소 추적에 사용
            project_path (str, optional): 프로젝트 디렉토리 경로
            start_node_id (str, optional): 시작 노드 ID
                - 지정 시 해당 Input 노드에서만 시작
                - 재개 실행 시 사용

        Yields:
            WorkflowNodeExecutionEvent: 실행 이벤트
                - event_type: 'node_start', 'node_output', 'node_complete', 'workflow_complete'
                - node_id, output, timestamp 포함

        Raises:
            ValueError: 워크플로우 설정 오류
            asyncio.CancelledError: 세션 취소됨

        Examples:
            >>> executor = WorkflowExecutor(config_loader)
            >>> async for event in executor.execute_workflow(
            ...     workflow=my_workflow,
            ...     initial_input="사용자 입력",
            ...     session_id="session-123"
            ... ):
            ...     print(f"{event.event_type}: {event.node_id}")
        """
        ...

    async def execute_single_node_continue(
        self,
        node_id: str,
        additional_prompt: str,
        project_path: Optional[str] = None,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        단일 노드에 추가 프롬프트 전송 (주도적 대화)

        이전에 실행된 노드의 세션을 재개하고 추가 작업을 요청합니다.
        워크플로우 재실행 없이 Worker와의 대화를 계속합니다.

        Args:
            node_id (str): 대화를 계속할 노드 ID
            additional_prompt (str): 추가 프롬프트
            project_path (str, optional): 프로젝트 경로

        Yields:
            WorkflowNodeExecutionEvent: 실행 이벤트

        Raises:
            ValueError: 노드를 찾을 수 없거나 이전 세션 없음

        Example:
            >>> # Backend Coder 노드의 마지막 코드를 수정하도록 요청
            >>> async for event in executor.execute_single_node_continue(
            ...     node_id='worker_1',
            ...     additional_prompt='코드의 에러 처리를 강화해주세요'
            ... ):
            ...     print(event.output)
        """
        ...
```

### 2. WorkflowNodeExecutor (노드 실행 오케스트레이터)

**파일**: `src/presentation/web/services/workflow_node_executor.py`

```python
class WorkflowNodeExecutor:
    """
    워크플로우 노드 실행 오케스트레이터 (Strategy Pattern)

    노드 타입에 따라 적절한 NodeExecutor에 실행을 위임합니다.
    각 노드 타입(Input, Worker, Condition, Merge)별로 별도의 Executor 클래스 사용.

    Attributes:
        input_executor (InputNodeExecutor): Input 노드 실행기
        worker_executor (WorkerNodeExecutor): Worker 노드 실행기
        condition_executor (ConditionNodeExecutor): Condition 노드 실행기
        merge_executor (MergeNodeExecutor): Merge 노드 실행기
    """

    async def execute(
        self,
        node: WorkflowNode,
        edges: List[WorkflowEdge],
        node_outputs: Dict[str, str],
        initial_input: str,
        session_id: str,
    ) -> WorkflowNodeExecutionEvent:
        """
        노드 타입에 따라 실행 위임

        node.type에 따라 다른 executor 호출:
        - 'input': InputNodeExecutor
        - 'worker': WorkerNodeExecutor
        - 'condition': ConditionNodeExecutor
        - 'merge': MergeNodeExecutor

        Args:
            node: 실행할 노드
            edges: 엣지 목록
            node_outputs: 이전 노드들의 출력 (key=node_id, value=output)
            initial_input: 워크플로우 초기 입력
            session_id: 세션 ID

        Returns:
            WorkflowNodeExecutionEvent: 실행 결과

        Raises:
            ValueError: 노드 타입 미지원
        """
        ...
```

### 3. 노드 실행기들 (Strategy Pattern)

**파일**: `src/presentation/web/services/node_executors/`

#### 3.1 BaseNodeExecutor (추상 베이스)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class BaseNodeExecutor(ABC):
    """
    노드 실행기 베이스 클래스 (Abstract Base Class)

    모든 노드 타입별 Executor는 이 클래스를 상속하고
    execute() 메서드를 구현합니다.

    Methods:
        execute(): 노드 실행 (추상 메서드)
    """

    @abstractmethod
    async def execute(
        self,
        node: WorkflowNode,
        node_outputs: dict[str, str],
        initial_input: str,
        session_id: str,
        edges: list[WorkflowEdge],
        all_nodes: list[WorkflowNode],
        condition_evaluator: ConditionEvaluatorProtocol,
        template_renderer: TemplateRendererProtocol,
    ) -> AsyncIterator[WorkflowNodeExecutionEvent]:
        """
        노드 실행 (구현 필수)

        Args:
            node: 실행할 노드
            node_outputs: 이전 노드 출력들 (node_id → output)
            initial_input: 초기 입력
            session_id: 세션 ID
            edges: 엣지 목록
            all_nodes: 모든 노드 목록
            condition_evaluator: 조건 평가기 인스턴스
            template_renderer: 템플릿 렌더러 인스턴스

        Yields:
            WorkflowNodeExecutionEvent: 노드 실행 이벤트 (스트리밍)
                - event_type: 'node_start', 'node_output', 'node_complete'
                - output: 노드 출력 (node_complete 시)
                - timestamp: 실행 시각
        """
        ...
```

#### 3.2 InputNodeExecutor

```python
class InputNodeExecutor(BaseNodeExecutor):
    """
    Input 노드 실행기

    워크플로우의 시작점입니다.
    초기 입력을 그대로 출력합니다.

    실행 로직:
    1. node_outputs에 ('input_node_id', initial_input) 저장
    2. WorkflowNodeExecutionEvent 반환

    Output:
    - initial_input과 동일
    """
    ...
```

#### 3.3 WorkerNodeExecutor

```python
class WorkerNodeExecutor(BaseNodeExecutor):
    """
    Worker 노드 실행기

    실제 작업을 수행하는 노드입니다.
    Claude Agent SDK를 호출하여 Worker에게 작업을 전달합니다.

    **주요 기능**:
    - 템플릿 렌더링: node.data.task_template을 Jinja2로 렌더링
    - 세션 재활용: 동일 노드의 이전 세션 ID 사용
    - Human-in-the-Loop: @ASK_USER: 패턴 감지 시 사용자 입력 요청
    - 출력 추출: 마커 기반 부분 출력 추출

    node.data 필드:
    - agent_name (str): Worker 이름 (예: 'backend_coder')
    - task_template (str): Jinja2 템플릿
        - {{input}}: 초기 입력
        - {{node_<id>}}: 다른 노드의 출력 (예: {{node_1}})
        - {{parent}}: 부모 노드의 출력 (부모가 1개인 경우만)
    - allowed_tools (List[str]): 도구 목록 (오버라이드)
    - thinking (bool): Thinking 모드 (오버라이드)
    - output_extraction (Dict, optional): 출력 추출 설정
        - strategy: 'full', 'last_block', 'between_markers'
        - start_marker, end_marker: between_markers 사용 시

    실행 로직:
    1. 부모 노드 출력 수집
    2. task_template 렌더링 (변수 치환)
    3. WorkerAgent.query() 호출
    4. 스트리밍 응답 수집
    5. Human-in-the-Loop 처리 (@ASK_USER 감지)
    6. 출력 추출 (선택 사항)
    7. 세션 ID 저장 (재활용용)

    Output 추출:
    1. 사용자 지정 마커 (OutputExtractionConfig)
    2. 자동 마커 (---NEXT_WORKER_OUTPUT_START/END---)
    3. 전체 텍스트 (기본값)

    Example:
        >>> node = WorkflowNode(
        ...     id='worker_1',
        ...     type='worker',
        ...     data={
        ...         'agent_name': 'backend_coder',
        ...         'task_template': '다음을 분석해주세요:\n{{input}}',
        ...         'output_extraction': {
        ...             'strategy': 'between_markers',
        ...             'start_marker': '<!-- RESULT -->',
        ...             'end_marker': '<!-- /RESULT -->'
        ...         }
        ...     }
        ... )
    """

    async def execute(self, ...):
        """
        Worker 노드 실행

        Returns:
            WorkflowNodeExecutionEvent with output
        """
        ...
```

#### 3.4 ConditionNodeExecutor

```python
class ConditionNodeExecutor(BaseNodeExecutor):
    """
    Condition 노드 실행기 (분기)

    조건을 평가하고 true/false 경로를 결정합니다.
    반복문은 node_id별 iteration_count로 추적합니다.

    node.data 필드:
    - condition_type (str): 조건 타입
        - 'contains': 텍스트 포함 검사
        - 'regex': 정규식 매칭
        - 'length': 텍스트 길이 비교
        - 'custom': AST 기반 안전한 식 평가
        - 'llm': LLM을 사용한 조건 평가
    - condition_value (str): 조건값 (type별로 해석)
    - condition_target (str): 대상 노드 ID (일반적으로 직전 노드)

    엣지 레이블:
    - "true": 조건이 참일 때의 엣지
    - "false": 조건이 거짓일 때의 엣지

    Output:
    - true 또는 false (다음 노드 선택용)
    """
    ...
```

#### 3.5 MergeNodeExecutor

```python
class MergeNodeExecutor(BaseNodeExecutor):
    """
    Merge 노드 실행기 (병합)

    여러 분기의 출력을 하나로 병합합니다.

    node.data 필드:
    - merge_strategy (str): 병합 전략
        - 'concatenate': 모든 입력 연결
        - 'first': 첫 번째 입력
        - 'last': 마지막 입력
        - 'custom': 커스텀 로직

    Output:
    - merge_strategy에 따라 결정
    """
    ...
```

---

### 4. WorkflowGraphManager (그래프 분석)

**파일**: `src/presentation/web/services/workflow_graph_manager.py`

```python
class WorkflowGraphManager:
    """
    워크플로우 그래프 관리자

    노드와 엣지를 분석하여:
    - 실행 순서 결정 (위상 정렬)
    - 병렬 실행 그룹 계산
    - 순환 참조 감지

    Methods:
        get_parent_nodes(node_id): 부모 노드 조회
        get_child_nodes(node_id): 자식 노드 조회
        topological_sort(start_node_id): 위상 정렬
        get_execution_groups(start_node_id): 병렬 실행 그룹 계산
        check_cycles(): 순환 참조 감지
    """

    def topological_sort(
        self,
        start_node_id: str | None = None
    ) -> List[WorkflowNode]:
        """
        워크플로우 노드 위상 정렬 (Topological Sort)

        **알고리즘**: Kahn's Algorithm (BFS 기반)

        단계:
        1. 각 노드의 입차 수 계산 (in-degree)
        2. 입차 수가 0인 노드부터 시작
        3. 방문 노드의 자식 입차 수 감소
        4. 입차 수가 0이 되는 노드 추가 방문

        특성:
        - 순환 참조 감지: 모든 노드를 방문하지 못하면 순환 참조 존재
        - 시간 복잡도: O(V + E)
        - V: 노드 수, E: 엣지 수

        Args:
            start_node_id (str, optional): 시작 노드 ID
                - 지정 시 해당 Input 노드에서만 시작
                - 재개 실행 시 사용

        Returns:
            List[WorkflowNode]: 실행 순서대로 정렬된 노드

        Raises:
            ValueError: 순환 참조 존재 또는 Input 노드 없음

        Example:
            >>> manager = WorkflowGraphManager(nodes, edges)
            >>> sorted_nodes = manager.topological_sort()
            >>> for node in sorted_nodes:
            ...     print(f"실행 순서: {node.id}")
        """
        ...

    def get_execution_groups(
        self,
        start_node_id: str | None = None
    ) -> List[List[str]]:
        """
        병렬 실행 그룹 계산

        같은 그룹에 속한 노드들은 병렬로 실행 가능합니다.

        **알고리즘**:
        1. BFS로 노드 방문
        2. 같은 깊이의 노드를 한 그룹으로
        3. 부모 노드 모두 완료된 노드만 추가

        **예시**:
        ```
        Input → Worker1 → Condition
                        ├→ Worker2 (true)
                        └→ Worker3 (false) → Merge
        ```

        그룹:
        1. [Input]
        2. [Worker1]
        3. [Condition]
        4. [Worker2, Worker3]  ← 병렬 실행 가능
        5. [Merge]

        Returns:
            List[List[str]]: 각 그룹에 속한 노드 ID 목록
        """
        ...

    def check_cycles(self) -> bool:
        """
        순환 참조 감지

        DFS를 사용하여 순환 참조 존재 여부를 확인합니다.

        Returns:
            bool: True if cycle exists
        """
        ...
```

---

### 5. WorkflowTemplateRenderer (Jinja2 렌더링)

**파일**: `src/presentation/web/services/workflow_template_renderer.py`

```python
class WorkflowTemplateRenderer:
    """
    워크플로우 템플릿 렌더러

    Worker 노드의 task_template을 Jinja2를 사용하여 렌더링합니다.
    변수 치환, 조건문, 반복문 등 Jinja2의 모든 기능 지원.

    **변수 치환**:
    - {{input}}: 워크플로우 초기 입력
    - {{node_<id>}}: 특정 노드의 출력 (예: {{node_reviewer}})
    - {{parent}}: 부모 노드의 출력 (부모가 1개인 경우만)

    **예시**:
    ```
    분석 대상:
    {{input}}

    이전 코드 리뷰 결과:
    {{node_reviewer}}

    위의 피드백을 반영하여 코드를 개선해주세요.
    ```

    Methods:
        render_task_template(): task_template 렌더링
    """

    def render_task_template(
        self,
        template: str,
        node_id: str,
        node_outputs: Dict[str, str],
        initial_input: str,
    ) -> str:
        """
        Worker 노드의 작업 템플릿 렌더링

        Args:
            template (str): 렌더링할 템플릿 (Jinja2 형식)
            node_id (str): 현재 노드 ID
            node_outputs (Dict[str, str]): 이전 노드 출력 매핑
            initial_input (str): 워크플로우 초기 입력

        Returns:
            str: 렌더링된 최종 프롬프트

        Raises:
            jinja2.UndefinedError: 정의되지 않은 변수 참조
            jinja2.TemplateSyntaxError: 템플릿 문법 오류

        Example:
            >>> renderer = WorkflowTemplateRenderer()
            >>> template = "코드를 분석하세요: {{input}}"
            >>> node_outputs = {}
            >>> result = renderer.render_task_template(
            ...     template=template,
            ...     node_id='worker_1',
            ...     node_outputs=node_outputs,
            ...     initial_input='def foo(): pass'
            ... )
            >>> # result = "코드를 분석하세요: def foo(): pass"
        """
        ...
```

---

### 6. WorkflowConditionEvaluator (조건 평가)

**파일**: `src/presentation/web/services/workflow_condition_evaluator.py`

```python
class WorkflowConditionEvaluator:
    """
    워크플로우 조건 평가기

    Condition 노드와 Merge 노드의 조건을 평가합니다.
    보안: 위험한 eval() 함수 대신 AST 기반 화이트리스트 사용.

    Methods:
        execute_condition_node(): Condition 노드 평가
        execute_merge_node(): Merge 노드 평가
    """

    async def execute_condition_node(
        self,
        node: WorkflowNode,
        node_outputs: Dict[str, str],
        edges: List[WorkflowEdge],
        session_id: str,
    ) -> tuple[str, str]:
        """
        Condition 노드 실행

        조건을 평가하고 true/false 경로를 결정합니다.

        **조건 타입**:
        1. **'contains'**: 텍스트 포함 검사
           - condition_value: 찾을 문자열
           - 예: output에 "error"가 포함되는가?

        2. **'regex'**: 정규식 매칭
           - condition_value: 정규식 패턴
           - 예: /^Error:/ 패턴 매칭

        3. **'length'**: 문자열 길이 비교
           - condition_value: "< 100", "> 500" 등
           - 예: 출력 길이가 100자 이상인가?

        4. **'custom'**: AST 기반 식 평가 (보안)
           - condition_value: 평가할 식
           - 예: "len(output) > 100 and 'error' not in output"
           - 지원 함수: len, str, int, float, abs, min, max, sum, round, pow
           - 차단: 속성 접근(__), 메서드 호출, import, exec 등

        5. **'llm'**: LLM을 사용한 동적 평가
           - condition_value: LLM에 제시할 질문
           - Claude가 yes/no로 답변

        Args:
            node (WorkflowNode): Condition 노드
            node_outputs (Dict): 이전 노드 출력
            edges (List[WorkflowEdge]): 엣지 목록
            session_id (str): 세션 ID

        Returns:
            tuple[str, str]: ("true" | "false", output_text)

        Raises:
            ValueError: 조건 평가 실패
            SyntaxError: custom 식이 안전하지 않음

        Example:
            >>> node = WorkflowNode(
            ...     id='condition_1',
            ...     type='condition',
            ...     data={
            ...         'condition_type': 'contains',
            ...         'condition_value': 'error',
            ...         'condition_target': 'worker_1'
            ...     }
            ... )
            >>> path, _ = await evaluator.execute_condition_node(
            ...     node, node_outputs, edges, 'session-1'
            ... )
            >>> # path = 'true' or 'false'
        """
        ...
```

---

## API 레이어 (Presentation Layer)

### REST API 엔드포인트

**파일**: `src/presentation/web/routers/workflows/`

#### 1. 워크플로우 실행

```
POST /api/workflows/execute
```

요청:
```json
{
    "workflow": { ... },
    "initial_input": "사용자 입력",
    "session_id": "session-123"
}
```

응답: Server-Sent Events (SSE) 스트리밍
```
data: {"event_type": "node_start", "node_id": "input_1", ...}
data: {"event_type": "node_output", "node_id": "worker_1", "output": "..."}
data: {"event_type": "node_complete", "node_id": "worker_1", ...}
data: {"event_type": "workflow_complete", "status": "success", ...}
```

#### 2. 세션 조회

```
GET /api/workflows/sessions/{session_id}
```

세션의 모든 로그 및 실행 결과 반환.

#### 3. 주도적 대화 (Continue Node)

```
POST /api/workflows/nodes/{node_id}/continue
```

요청:
```json
{
    "additional_prompt": "추가 작업 요청"
}
```

이전 세션을 재개하여 추가 프롬프트 처리.

---

## 설정 및 로깅

### 설정 파일

#### 1. `config/agent_config.json`

```json
[
    {
        "name": "backend_coder",
        "role": "백엔드 개발 전문가",
        "system_prompt": "prompts/backend_coder.txt",
        "allowed_tools": ["read", "write", "edit", "bash", "glob", "grep"],
        "model": "claude-sonnet-4-5-20250929",
        "thinking": true
    }
]
```

#### 2. `config/system_config.json`

```json
{
    "manager_model": "claude-sonnet-4-5-20250929",
    "max_history_messages": 20,
    "enable_caching": true,
    "worker_retry_enabled": true,
    "log_level": "INFO"
}
```

### 로그 파일 구조

```
~/.claude-flow/
├── {프로젝트명}/
│   ├── logs/
│   │   ├── {session_id}.log          # 세션별 로그
│   │   └── system.log                # 시스템 로그
│   ├── workflows/
│   │   └── {workflow_id}.json        # 저장된 워크플로우
│   ├── sessions/
│   │   └── {session_id}.json         # 세션 상태 저장
│   └── reports/
│       └── {timestamp}_{node_id}_*.txt # 노드 실행 보고서
│
├── custom_workers/
│   └── {worker_name}.txt             # 커스텀 Worker 프롬프트
│
└── templates/
    └── {template_id}.json            # 사용자 템플릿
```

---

## 주요 알고리즘

### 1. Kahn's Algorithm (위상 정렬)

**목적**: DAG(Directed Acyclic Graph)의 노드를 선형 순서로 정렬

**시간 복잡도**: O(V + E), V=노드, E=엣지

```python
def topological_sort(nodes, edges):
    # 1. 입차 수 계산
    in_degree = {node.id: 0 for node in nodes}
    for edge in edges:
        in_degree[edge.target] += 1

    # 2. 입차 수 0인 노드부터 시작
    queue = [n for n in nodes if in_degree[n.id] == 0]
    result = []

    # 3. BFS로 방문
    while queue:
        current = queue.pop(0)
        result.append(current)

        # 4. 자식 노드의 입차 수 감소
        for edge in edges:
            if edge.source == current.id:
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(node_map[edge.target])

    # 5. 순환 참조 감지
    if len(result) != len(nodes):
        raise ValueError("순환 참조 존재")

    return result
```

### 2. Human-in-the-Loop 패턴

**목적**: Worker가 사용자 입력을 요청할 때 대화 계속

**플로우**:
1. Worker 출력에서 `@ASK_USER:` 패턴 감지
2. Frontend에서 AskUserModal 표시
3. 사용자 입력 → Queue에 추가
4. Worker가 Queue에서 읽고 대화 재개

**코드**:
```python
# Worker 프롬프트에서 사용
"사용자에게 필요한 정보를 요청하려면 다음과 같이 작성하세요:"
"@ASK_USER: 추가 사항이 있으신가요?"

# SDK Executor에서 감지
if "@ASK_USER:" in response:
    user_answer = await user_input_callback()
    # Worker 재개
```

### 3. 출력 추출 (Output Extraction)

**목적**: Worker의 전체 출력에서 필요한 부분만 추출

**전략**:

1. **전체 텍스트 (full)**: 모든 텍스트 블록 합치기
2. **마지막 블록 (last_block)**: 마지막 텍스트 블록만
3. **마커 사이 (between_markers)**: 시작/종료 마커 사이의 텍스트

**예시**:

```python
# Worker 프롬프트 지시
"결과를 다음 마커로 감싸주세요:"
"<!-- RESULT -->
[결과 내용]
<!-- /RESULT -->"

# 출력 추출 설정
output_extraction = {
    "strategy": "between_markers",
    "start_marker": "<!-- RESULT -->",
    "end_marker": "<!-- /RESULT -->"
}

# 자동 마커 (표준)
"---NEXT_WORKER_OUTPUT_START---
[다음 Worker를 위한 핵심 출력]
---NEXT_WORKER_OUTPUT_END---"
```

---

## 코드 컨벤션 및 패턴

### Python 코드 스타일

**포맷터**: Black (line-length: 100)
```bash
black src/ --line-length 100
```

**린터**: Ruff
```bash
ruff check src/
```

**타입 힌팅**: mypy (점진적 적용)
```bash
mypy src/
```

### Docstring 스타일

**Google Style Docstring**:

```python
def execute_workflow(
    workflow: Workflow,
    initial_input: str,
    session_id: str,
) -> AsyncIterator[WorkflowNodeExecutionEvent]:
    """
    워크플로우 실행 (한 문장 요약)

    여러 줄의 상세 설명...
    내부 동작 원리, 주의 사항 등

    Args:
        workflow (Workflow): 실행할 워크플로우
            - 검증: WorkflowValidator.validate() 필수
        initial_input (str): 초기 입력 데이터
            - 제약: max_input_length 초과 불가
        session_id (str): 세션 ID
            - 형식: UUID 또는 custom string

    Yields:
        WorkflowNodeExecutionEvent: 실행 이벤트
            - event_type: 'node_start', 'node_output', 'node_complete', 'workflow_complete'
            - 각 이벤트의 구조 설명

    Raises:
        ValueError: 워크플로우 설정 오류
            - 원인: Input 노드 미존재
        asyncio.CancelledError: 세션 취소됨

    Examples:
        >>> executor = WorkflowExecutor(config_loader)
        >>> async for event in executor.execute_workflow(workflow, input_text, 'session-1'):
        ...     print(event.event_type)

    Note:
        - 비동기 함수이므로 await/async for 사용 필수
        - SSE 스트리밍으로 실시간 이벤트 전송
    """
    ...
```

### 에러 처리

```python
# 명확한 에러 메시지 (사용 가능한 옵션 제시)
def _get_agent_config(self, agent_name: str) -> AgentConfig:
    config = self.agent_config_map.get(agent_name)
    if not config:
        available = list(self.agent_config_map.keys())
        raise ValueError(
            f"Agent '{agent_name}'를 찾을 수 없습니다.\n"
            f"사용 가능한 Agent: {', '.join(available)}"
        )
    return config
```

### 로깅 패턴

```python
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# 구조화 로깅
logger.info("세션 시작", session_id=session_id, workflow_id=workflow.id)
logger.warning("문제 발생", node_id=node.id, reason="timeout")
logger.error("실행 실패", node_id=node.id, exc_info=True)
```

---

## 주요 클래스 간 관계도

```
┌─────────────────────────────────────────────────────────────┐
│                   WorkflowExecutor (Facade)                 │
│  - workflow 실행 오케스트레이션                              │
│  - 세션 관리, 취소 처리, 실시간 이벤트                      │
└──────────────┬──────────────────────────────────────────────┘
               │
      ┌────────┴────────┐
      │                 │
      v                 v
┌──────────────────┐  ┌────────────────────────────┐
│ WorkflowGraph    │  │ WorkflowNodeExecutor       │
│ Manager          │  │ (Strategy Pattern)         │
│                  │  │                            │
│ - topo sort      │  │ ├→ InputNodeExecutor      │
│ - parallel group │  │ ├→ WorkerNodeExecutor     │
│ - cycle check    │  │ ├→ ConditionNodeExecutor  │
└──────────────────┘  │ └→ MergeNodeExecutor      │
                      └──────────┬─────────────────┘
                                 │
                    ┌────────────┼────────────────┐
                    │            │                │
                    v            v                v
            ┌──────────────┐  ┌─────────────┐  ┌────────────────┐
            │ WorkerAgent  │  │ Template    │  │ Condition      │
            │              │  │ Renderer    │  │ Evaluator      │
            │ - query()    │  │             │  │                │
            │ - session    │  │ - Jinja2    │  │ - custom eval  │
            │ - HitL       │  │ - variables │  │ - LLM eval     │
            └──────────────┘  └─────────────┘  └────────────────┘
                    │
                    v
            ┌──────────────┐
            │ Claude SDK   │
            │ (agentic)    │
            │              │
            │ - tools      │
            │ - streaming  │
            │ - hooks      │
            └──────────────┘
```

---

## 확장 가이드

### 새로운 Worker 추가

1. **프롬프트 파일 생성**: `prompts/{worker_name}.txt`
   ```
   ---
   role: 워커 역할
   allowed_tools:
     - read
     - write
   model: claude-sonnet-4-5-20250929
   thinking: true
   ---

   프롬프트 내용...
   ```

2. **자동 등록**: 서버 재시작 후 자동으로 UI에 표시됨

### 새로운 노드 타입 추가

1. 스키마 정의: `src/presentation/web/schemas/workflow_nodes.py`
2. Executor 구현: `src/presentation/web/services/node_executors/{type}_executor.py`
3. WorkflowNodeExecutor에 등록
4. React 컴포넌트 추가

---

**작성자**: Code Documenter Agent
**최종 수정**: 2025-11-05
