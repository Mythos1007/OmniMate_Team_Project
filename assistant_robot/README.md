# assistant_robot

ROS2 Jazzy 기반 비서/안내 로봇의 중앙 오케스트레이션 패키지입니다.
핵심 목표는 "기능을 한 파일에 섞지 않고" 모듈/노드/어댑터로 분리해서, 나중에 조원 코드가 와도 adapter 교체만으로 바로 붙일 수 있게 만드는 것

## 1. 아키텍처 한눈에 보기

- Command Intake Layer
  - 음성/GUI/스케줄 입력을 CommandRequest로 표준화
  - 관련 코드: assistant_robot/interfaces/intent_parser.py, assistant_robot/adapters/mock_intent_parser.py
- Mission Queue / Scheduler Layer
  - pending 미션 저장, priority/scheduled_for/expires_at 고려
  - 관련 코드: assistant_robot/orchestrator/mission_queue.py, assistant_robot/services/schedule_service.py
- Orchestrator / Dispatcher Layer
  - 중앙 정책 엔진, 단일 active mission 관리, dispatch/tick 처리
  - 관련 코드: assistant_robot/orchestrator/omni_orchestrator.py, assistant_robot/orchestrator/mission_dispatcher.py
- Robot State Machine
  - 상위 상태 단일 관리, GUI 메시지 중앙 생성
  - 관련 코드: assistant_robot/orchestrator/state_machine.py
- Skill / Executor Layer
  - 배송/호출/알람/복약/날씨TTS/복귀 동작 분리
  - 관련 코드: assistant_robot/executors/
- Adapter / Interface Layer
  - OCR/얼굴/손인식/내비/TTS/날씨/Intent를 인터페이스 기반으로 연결
  - 관련 코드: assistant_robot/interfaces/, assistant_robot/adapters/

## 2. 현재 구현된 핵심 정책

- 동시에 실행되는 mission은 1개만 허용
- 새 이동 명령은 현재 작업 중이어도 queue 등록 가능
- LOW_BATTERY_RESTRICTED 상태에서는 새 이동 명령 intake 차단
- LOW_BATTERY_RESTRICTED 상태에서도 weather_tts 같은 non-move 명령 허용
- LOW_BATTERY_RESTRICTED 상태에서도 status_brief(`어디가?`) 같은 non-move 명령 허용
- 현재 미션 종료 후 다음 pending 자동 dispatch
- 저전력 제한 중 현재 미션 완료 시 return_to_base 미션 자동 삽입
- 음성 다중 명령은 첫 번째 유효 명령만 채택, 나머지는 rejection TTS 출력
- 얼굴 인사 overlay는 메인 미션을 중단하지 않으며 cooldown 적용

## 3. TTS 중앙 문구 관리

- 문구 파일
  - assistant_robot/resources/tts_messages.yaml
  - assistant_robot/resources/tts_messages_dev.yaml
  - assistant_robot/resources/tts_messages_demo.yaml
- 문구 조회 서비스
  - assistant_robot/services/tts_script_manager.py
- 실제 출력 서비스
  - assistant_robot/services/tts_manager.py
- 설계 포인트
  - key 기반 조회
  - placeholder 치환
  - 없는 key fallback
  - 다중 후보 문구 round-robin 선택

## 4. 날씨 재사용 구조

- 기존 GUI 날씨 엔진 재사용 어댑터
  - assistant_robot/adapters/existing_weather_adapter.py
- 날씨 표현 분리
  - GUI용: assistant_robot/services/weather_formatter.py::format_for_gui
  - TTS용 payload: assistant_robot/services/weather_formatter.py::build_tts_payload
- 날씨 음성 실행기
  - assistant_robot/executors/weather_tts_executor.py

## 5. 주요 폴더 설명

- assistant_robot/models: DTO/데이터 모델
- assistant_robot/interfaces: 외부 기능 연동 계약(Protocol/ABC)
- assistant_robot/adapters: mock 및 실제 연동 어댑터
- assistant_robot/executors: 미션별 step 실행기
- assistant_robot/orchestrator: 정책/큐/디스패처/상태머신
- assistant_robot/services: 공용 서비스(TTS, 스케줄, 날씨 포맷, 인사)
- assistant_robot/nodes: ROS2 브리지 노드
- assistant_robot/resources: TTS 문구 리소스
- assistant_robot/config: 앱/미션/스케줄/TTS 설정 파일
- tests: mock 기반 통합 테스트

## 6. 빠른 실행

패키지 루트: src/assistant/assistant_robot

- 데모 실행
  - python3 -m assistant_robot.demo
- 테스트 실행
  - python3 -m pytest -v tests

## 6-1. 음성 명령 예시

- 옴니야 회의실 A로 가줘
  - 이동 호출 미션(CALL) 등록
- 옴니야 오늘 날씨 알려줘
  - non-move 날씨 안내 미션(WEATHER_TTS) 등록
- 옴니야 어디가?
  - non-move 상태 질의 미션(STATUS_BRIEF) 등록
  - 이동 중이면 현재 향하는 목적지를, 대기 중이면 현재 위치를 TTS로 안내

## 7. ROS2 엔트리포인트

setup.py의 console_scripts에 아래가 등록되어 있습니다.

- omni_orchestrator_node
- wakeword_node
- stt_node
- intent_parser_node
- scheduler_node
- gui_bridge_node
- battery_monitor_node
- assistant_robot_demo

## 8. 조원 코드 연결 가이드

교체 순서만 지키면 됩니다.

1. interfaces 계약 확인
   - 예: BaseWeatherProvider, BaseTTSProvider, BaseNavigationController
2. adapters에 실제 구현 추가
   - 예: azure_tts_provider.py, real_navigation_controller.py
3. demo.py 또는 orchestrator_node.py 조립부에서 mock -> 실제 adapter로 교체
4. 테스트를 같은 시나리오로 재실행

## 9. 테스트 커버리지(현재)

- test_queue.py
  - 우선순위/스케줄/만료 큐 동작
- test_battery_policy.py
  - 저전력 이동 차단 + non-move 허용
- test_orchestrator.py
  - 실행 중 queue 적재
  - 완료 후 자동 다음 dispatch
  - 다중 음성 첫 명령 채택
  - greeting overlay 비중단
- test_weather_tts.py
  - 날씨 문장 포맷 + weather executor
- test_tts_script_manager.py
  - key 조회, placeholder, fallback, 다중 문구 선택

## 10. 운영 시 주의 포인트

- 현재 많은 adapter는 mock/placeholder 상태입니다.
- TODO 주석 위치를 기준으로 실제 기능 모듈을 연결하세요.
- state_machine의 status_message_for_gui를 GUI 기준 문체로 계속 다듬으면 운용성이 좋아집니다.
