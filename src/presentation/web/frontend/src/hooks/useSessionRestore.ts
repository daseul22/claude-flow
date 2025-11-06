/**
 * 세션 복원 커스텀 훅
 *
 * 앱 시작 시 세션 자동 복원 및 프로젝트 로드
 * - localStorage에서 세션 ID 및 프로젝트 경로 복원
 * - 워크플로우 세션 복원 (노드, 엣지, 로그)
 * - 실행 중인 세션은 스트림 자동 재접속
 */

import { useEffect, useRef } from 'react'
import { useWorkflowStore } from '../stores/workflowStore'
import {
  selectProject,
  loadProjectWorkflowByName,
  listProjectWorkflows,
  getWorkflowSession,
} from '../lib/api'

const STORAGE_KEY_PROJECT_PATH = 'claude-flow-last-project-path'
const STORAGE_KEY_SESSION_ID = 'claude-flow-workflow-session-id'

interface UseSessionRestoreOptions {
  /**
   * 프로젝트 경로 변경 핸들러
   */
  onProjectPathChange: (path: string) => void

  /**
   * 워크플로우 파일명 변경 핸들러
   */
  onWorkflowFileNameChange: (fileName: string) => void

  /**
   * 토스트 추가 핸들러
   */
  addToast: (type: 'success' | 'error' | 'warning' | 'info', message: string) => void

  /**
   * 초기 로드 완료 플래그 (App.tsx에서 전달)
   */
  initialLoadDone?: React.MutableRefObject<boolean>
}

/**
 * 세션 복원 커스텀 훅
 */
export function useSessionRestore({
  onProjectPathChange,
  onWorkflowFileNameChange,
  addToast,
  initialLoadDone: externalInitialLoadDone,
}: UseSessionRestoreOptions) {
  const { loadWorkflow, restoreFromSession } = useWorkflowStore()
  const internalInitialLoadDone = useRef(false)

  // 외부에서 전달된 ref가 있으면 사용, 없으면 내부 ref 사용
  const initialLoadDone = externalInitialLoadDone || internalInitialLoadDone

  useEffect(() => {
    // 이미 로드되었으면 스킵
    if (initialLoadDone.current) return
    initialLoadDone.current = true

    const loadLastProject = async () => {
      // 1. 세션 복원 시도 (우선순위 높음 - 세션에 프로젝트 경로 포함)
      const lastSessionId = localStorage.getItem(STORAGE_KEY_SESSION_ID)
      if (lastSessionId) {
        try {
          console.log('🔄 세션 복원 시도:', lastSessionId)
          const session = await getWorkflowSession(lastSessionId)

          // 1️⃣ 프로젝트 경로 복원 (세션 → localStorage 순서)
          let restoredProjectPath: string | null = null

          // 1-1. 세션에서 프로젝트 경로 복원 시도
          if (session.project_path) {
            try {
              const result = await selectProject(session.project_path)
              restoredProjectPath = result.project_path
              onProjectPathChange(result.project_path)
              localStorage.setItem(STORAGE_KEY_PROJECT_PATH, result.project_path)
              console.log(`✅ 세션에서 프로젝트 경로 복원: ${session.project_path}`)
            } catch (err) {
              console.warn('세션 프로젝트 경로 복원 실패:', err)
            }
          }

          // 1-2. 세션에 없으면 localStorage에서 복원 시도
          if (!restoredProjectPath) {
            const lastProjectPath = localStorage.getItem(STORAGE_KEY_PROJECT_PATH)
            if (lastProjectPath) {
              try {
                const result = await selectProject(lastProjectPath)
                restoredProjectPath = result.project_path
                onProjectPathChange(result.project_path)
                console.log(`✅ localStorage에서 프로젝트 경로 복원: ${lastProjectPath}`)
              } catch (err) {
                console.warn('localStorage 프로젝트 경로 복원 실패:', err)
                localStorage.removeItem(STORAGE_KEY_PROJECT_PATH)
              }
            }
          }

          if (!restoredProjectPath) {
            console.warn('⚠️  프로젝트 경로 복원 실패 - 사용자가 수동으로 선택해야 함')
          }

          // 2️⃣ 워크플로우 세션 복원 (기존 로그 복원 - 모든 세션)
          restoreFromSession(session)
          // 워크플로우 파일명도 복원 (자동 저장을 위해 필수)
          const fileName = session.workflow_file_name || `${session.workflow.name}.json`
          onWorkflowFileNameChange(fileName)
          console.log('✅ 세션 복원 완료:', session.session_id, '| 워크플로우:', fileName)

          // 2-1️⃣ 파일 시스템에서 최신 워크플로우 다시 로드 (수정사항 반영)
          // 프로젝트 경로가 복원된 경우에만 시도
          if (restoredProjectPath) {
            try {
              const latestWorkflow = await loadProjectWorkflowByName(fileName)
              // 노드와 엣지만 최신 파일로 교체 (로그는 유지)
              const store = useWorkflowStore.getState()
              store.setNodes(latestWorkflow.workflow.nodes)
              store.setEdges(latestWorkflow.workflow.edges)
              store.setWorkflowName(latestWorkflow.workflow.name)
              store.setWorkflowDescription(latestWorkflow.workflow.description || '')
              console.log('✅ 최신 워크플로우 반영 완료 (파일 시스템)')
            } catch (err) {
              console.warn('⚠️  최신 워크플로우 로드 실패, 세션 워크플로우 사용:', err)
            }
          } else {
            console.log('ℹ️  프로젝트 경로 없음 - 세션 워크플로우 사용')
          }

          // 3️⃣ 실행 중인 세션만 스트림 재접속 (완료 확인)
          const hasWorkflowComplete = session.logs.some(
            (log: any) => log.event_type === 'workflow_complete'
          )
          const hasWorkflowError = session.logs.some(
            (log: any) => log.event_type === 'workflow_error'
          )
          const isActuallyRunning =
            !hasWorkflowComplete && !hasWorkflowError && session.status === 'running'

          if (isActuallyRunning) {
            console.log('🔌 실행 중인 세션 감지 - 스트림 자동 재접속 시작')

            // 실행 상태 활성화 (UI 표시 및 중지 버튼 활성화)
            const store = useWorkflowStore.getState()
            store.startExecution(session.current_node_id)  // 실행 중인 노드로 startExecution 호출
            store.setCurrentSessionId(lastSessionId)

            // 현재 로그 개수 확인 (중복 방지용)
            const lastEventIndex = session.logs.length > 0 ? session.logs.length - 1 : undefined

            // 동적으로 executeWorkflow import 및 호출
            import('../lib/api').then(({ executeWorkflow }) => {
              const abortController = new AbortController()

              executeWorkflow(
                session.workflow,
                session.initial_input,
                // onEvent
                (event) => {
                  // Zustand store에 이벤트 전달 (restoreFromSession과 동일한 로직)
                  const {
                    event_type,
                    node_id,
                    data: eventData,
                    timestamp,
                    elapsed_time,
                    token_usage,
                  } = event
                  const store = useWorkflowStore.getState()

                  switch (event_type) {
                    case 'node_start':
                      store.setCurrentNode(node_id)
                      if (timestamp) {
                        store.setNodeStartTime(node_id, new Date(timestamp).getTime())
                      }
                      if (eventData.input) {
                        store.setNodeInput(node_id, eventData.input)
                      }
                      store.addLog(
                        node_id,
                        'start',
                        `▶️  ${eventData.agent_name || eventData.node_type || 'Unknown'} 실행 시작`
                      )
                      break

                    case 'node_output':
                      // log_type이 'output'인 경우만 다음 노드로 전달
                      if (eventData.log_type === 'output') {
                        store.addNodeOutput(node_id, eventData.chunk)
                      }
                      // 모든 chunk를 로그에 추가 (InputNode.tsx와 동일한 로직)
                      if (eventData.chunk && eventData.chunk.trim().length > 0) {
                        // chunk_type에 따라 로그 타입 결정
                        const chunkType = eventData.chunk_type || 'text'
                        let logType: 'input' | 'execution' | 'output' = 'output'

                        if (chunkType === 'input') {
                          logType = 'input'
                        } else if (chunkType === 'thinking' || chunkType === 'tool') {
                          logType = 'execution'
                        } else {
                          logType = 'output'
                        }

                        store.addLog(node_id, logType, eventData.chunk)
                      }
                      break

                    case 'node_complete':
                      console.log('[SessionRestore] 스트림 재접속 - node_complete 이벤트:', {
                        node_id,
                        elapsed_time,
                        token_usage,
                      })

                      if (elapsed_time !== undefined) {
                        store.setNodeCompleted(node_id, elapsed_time, token_usage)
                      }
                      let completeMsg = `✅ ${
                        eventData.agent_name || eventData.node_type || 'Unknown'
                      } 완료`
                      if (elapsed_time !== undefined) {
                        completeMsg += ` (${elapsed_time.toFixed(1)}초)`
                      }
                      if (token_usage && token_usage.total_tokens > 0) {
                        completeMsg += ` [${token_usage.total_tokens.toLocaleString()} tokens]`
                      }
                      store.addLog(node_id, 'complete', completeMsg)
                      break

                    case 'node_error':
                      if (eventData.error) {
                        store.setNodeError(node_id, eventData.error)
                      }
                      store.addLog(node_id, 'error', `❌ ${eventData.error || 'Unknown error'}`)
                      break

                    case 'node_session_created':
                      // 노드별 SDK 세션 ID가 생성되었을 때
                      console.log('[SessionRestore] 노드 세션 생성:', {
                        node_id,
                        session_id: eventData.session_id,
                        agent_name: eventData.agent_name,
                      })
                      // 로그에 기록 (선택적)
                      store.addLog(
                        node_id,
                        'execution',
                        `🔗 세션 생성: ${eventData.session_id?.substring(0, 8)}... (${
                          eventData.agent_name
                        })`
                      )
                      break

                    case 'workflow_complete':
                      store.addLog('', 'complete', eventData.message || '🎉 워크플로우 실행 완료')
                      store.setCurrentNode(null)
                      store.stopExecution()
                      // 워크플로우 완료 시 세션 ID 제거
                      localStorage.removeItem(STORAGE_KEY_SESSION_ID)
                      console.log('[SessionRestore] 워크플로우 완료 - 세션 ID 제거')
                      break
                  }
                },
                // onComplete
                () => {
                  console.log('✅ 스트림 재접속 완료 - 워크플로우 실행 완료')
                  useWorkflowStore.getState().stopExecution()
                  // 워크플로우 완료 시 세션 ID 제거
                  localStorage.removeItem(STORAGE_KEY_SESSION_ID)
                  console.log('[SessionRestore] 스트림 재접속 완료 - 세션 ID 제거')
                },
                // onError
                (error) => {
                  console.error('❌ 스트림 재접속 실패:', error)
                  useWorkflowStore.getState().stopExecution()
                  addToast('error', `스트림 재접속 실패: ${error}`)
                },
                // signal
                abortController.signal,
                // sessionId (재접속용)
                lastSessionId,
                // lastEventIndex (중복 방지용)
                lastEventIndex
              )
                .then((returnedSessionId) => {
                  console.log('✅ 스트림 재접속 성공:', returnedSessionId)
                  addToast('success', '실시간 스트림이 재개되었습니다')
                })
                .catch((err) => {
                  console.error('❌ 스트림 재접속 중 에러:', err)
                  addToast('error', `스트림 재접속 실패: ${err.message}`)
                })
            })
          } else if (hasWorkflowComplete) {
            // 세션이 이미 완료된 경우
            console.log('✅ 세션이 이미 완료되었습니다 - 스트림 재접속 스킵')
            addToast('info', '이전 워크플로우 실행 결과가 복원되었습니다')
          } else if (hasWorkflowError) {
            // 세션이 에러로 종료된 경우
            console.log('❌ 세션이 에러로 종료되었습니다 - 스트림 재접속 스킵')
            addToast('warning', '이전 워크플로우 실행 중 에러가 발생했습니다')
          }

          // 세션 복원 성공 시 워크플로우 로드 스킵
          return
        } catch (err) {
          console.warn('세션 복원 실패 (세션 삭제됨 또는 만료):', err)
          localStorage.removeItem(STORAGE_KEY_SESSION_ID)
        }
      }

      // 2. 세션 복원 실패 시 localStorage에서 프로젝트 경로 복원
      const lastProjectPath = localStorage.getItem(STORAGE_KEY_PROJECT_PATH)
      if (lastProjectPath) {
        try {
          // 백엔드에 프로젝트 선택
          const result = await selectProject(lastProjectPath)
          onProjectPathChange(result.project_path)
          console.log(`✅ localStorage에서 프로젝트 경로 복원: ${lastProjectPath}`)

          // 워크플로우 목록 로드
          try {
            const workflowsResult = await listProjectWorkflows()

            if (workflowsResult.workflows.length > 0) {
              // 첫 번째 워크플로우 로드
              const firstWorkflow = workflowsResult.workflows[0]
              const workflowData = await loadProjectWorkflowByName(firstWorkflow.name)
              loadWorkflow(workflowData.workflow)
              onWorkflowFileNameChange(firstWorkflow.name)
              console.log(`✅ 워크플로우 자동 로드: ${firstWorkflow.name}`)
            }
          } catch (err) {
            console.warn('워크플로우 자동 로드 실패:', err)
          }
        } catch (err) {
          console.warn('프로젝트 자동 로드 실패:', err)
          // 실패 시 localStorage 정리
          localStorage.removeItem(STORAGE_KEY_PROJECT_PATH)
        }
      }
    }

    loadLastProject()
  }, [loadWorkflow, restoreFromSession, addToast, onProjectPathChange, onWorkflowFileNameChange])
}
