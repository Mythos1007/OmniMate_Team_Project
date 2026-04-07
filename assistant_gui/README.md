# assistant_gui

사용자 대시보드, 지도/경로 표시, 상태 시각화를 담당하는 GUI 패키지입니다.

## 디렉토리 구조

- assistant_gui/
  - assistant_gui/
    - pages/: 화면 단위 위젯(홈/일정/설정/음성/날씨)
    - engines/: 날씨/배터리/OCR/스케줄/알람 엔진
    - face/: 표정 렌더링 및 상태 제어
    - integrations/: ROS 상태 브리지
    - main.py: GUI 앱 진입점
    - map_view.py: 지도 렌더링/클릭 좌표 변환/경로 오버레이
    - path_planner.py: 지도 기반 경로 계산

## 주요 코드 설명

- assistant_gui/main.py
  - 전체 페이지/헤더/엔진 초기화 및 전역 UI 흐름 제어
  - FaceController 공유 + 음성 루프(wakeword/command) 상태 제어
- assistant_gui/pages/home_page.py
  - 지도 상호작용, 상태 카드, 단축 액션 처리
- assistant_gui/map_view.py
  - 좌표계 변환, 경로 시각화, 실시간 경로 재계산
- assistant_gui/path_planner.py
  - 장애물 맵 생성 및 A* 기반 경로 계획
- assistant_gui/engines/weather_engine.py
  - 날씨/대기질 조회, 공용 시크릿 파일 기반 키 로딩

## 실행 엔트리포인트

- `assistant_gui_node`
- `assistant_gui_face_demo`

## 런타임 환경변수

- `ASSISTANT_ENABLE_ROS_BRIDGE`: ROS 상태 브리지 활성화 (`1/true`)
- `ASSISTANT_FACE_VOICE_LOOP`: GUI 내부 음성 루프 활성화 (`1/true`)
- `ASSISTANT_VOICE_ONLY_FACE_MODE`: 수동 조작 전 얼굴 페이지 고정 (`1/true`)
- `ASSISTANT_FACE_COMMAND_TIMEOUT_SEC`: 명령 입력 타임아웃(초)
- `ASSISTANT_FACE_COMMAND_SILENCE_RETRIES`: 무음 재시도 횟수

## 설정 저장 키(QSettings)

- `ui/theme`
- `runtime/status_poll_ms`
- `runtime/face_fps`
- `voice/default_backend`
- `voice/edge_voice`
- `voice/wakeword_reply_only`
