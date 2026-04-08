# OmniMate Assistant 워크스페이스

이 저장소는 `assistant` 디렉토리부터 버전 관리합니다.

- 현재 git root: `/home/mythos/assistant_ws/src/assistant`
- 원격 저장소: `https://github.com/Mythos1007/OmniMate_Team_Project.git`

## 1) 권장 개발 환경

- OS: Ubuntu 22.04 LTS
- ROS 2: Humble Hawksbill
- Python: 3.10.x (Humble 기본)
- Colcon: 0.15+

## 2) 필수 Python 패키지

아래 패키지를 활성 환경(venv 등)에 설치하세요.

```bash
pip install \
  PySide6==6.7.2 \
  requests==2.32.3 \
  SpeechRecognition==3.10.4 \
  edge-tts==6.1.13 \
  faster-whisper==1.0.3 \
  PyYAML==6.0.2 \
  numpy==1.26.4 \
  opencv-python==4.10.0.84
```

선택 설치(클라우드 TTS SDK 직접 사용 시):

```bash
pip install elevenlabs==1.8.0 cartesia==1.0.0
```

## 3) 필수 ROS 2 패키지(apt)

```bash
sudo apt update
sudo apt install -y \
  ros-humble-nav2-msgs \
  ros-humble-geometry-msgs \
  ros-humble-std-msgs \
  ros-humble-std-srvs \
  ros-humble-launch \
  ros-humble-launch-ros
```

## 4) API 키 보안 관리 (공용 시크릿 1개)

실제 키는 코드/깃에 넣지 않고 로컬 공용 시크릿 파일 1개에서 관리합니다.

- 공용 시크릿 파일 경로: `~/.config/assistant/secrets.json`
- 예시 파일: `secrets.example.json`
- 이 파일은 프로젝트 폴더 안이 아니라 각자 PC의 홈 디렉터리 아래에 만들어야 합니다.

설정 방법:

```bash
mkdir -p ~/.config/assistant
cp secrets.example.json ~/.config/assistant/secrets.json
```

로컬에서 바로 생성하고 편집까지 여는 명령:

```bash
mkdir -p ~/.config/assistant \
  && cp /home/mythos/assistant_ws/src/assistant/secrets.example.json ~/.config/assistant/secrets.json \
  && ${EDITOR:-nano} ~/.config/assistant/secrets.json
```

예시 내용을 한 번에 생성하려면:

```bash
mkdir -p ~/.config/assistant
cat > ~/.config/assistant/secrets.json <<'EOF'
{
  "weather_api_key": "",
  "elevenlabs_api_key": "",
  "elevenlabs_voice_id": "",
  "cartesia_api_key": "",
  "cartesia_voice_id": ""
}
EOF
${EDITOR:-nano} ~/.config/assistant/secrets.json
```

필수 키 항목:

- `weather_api_key`
- `elevenlabs_api_key`
- `elevenlabs_voice_id`
- `cartesia_api_key`
- `cartesia_voice_id`

환경변수 연결:

```bash
export ASSISTANT_SECRETS_FILE=~/.config/assistant/secrets.json
```

API 발급 링크:

- KMA 날씨 API: https://www.data.go.kr/data/15084084/openapi.do
- ElevenLabs API: https://elevenlabs.io/app/settings/api-keys
- Cartesia API: https://play.cartesia.ai/

## 5) 패키지/디렉토리 구조 설명

### `assistant_audio`

- 역할: Wake word, STT, TTS 파이프라인
- 주요 디렉토리:
  - `assistant_audio/input_providers`: 입력 소스(버튼/텍스트)
  - `assistant_audio/providers`: STT/TTS 백엔드 구현
  - `assistant_audio/tools`: 로컬 테스트 CLI
  - `assistant_audio/stt_node.py`, `assistant_audio/tts_node.py`, `assistant_audio/wake_word_node.py`: ROS2 노드 엔트리

### `assistant_brain`

- 역할: 대화/의도 라우팅 및 상태 흐름 제어
- 주요 디렉토리:
  - `assistant_brain/handlers`: 명령 핸들러(정보/모션/네비/작업)
  - `assistant_brain/tools`: 스텁/보조 실행 도구
  - `dialog_manager_node.py`, `intent_router_node.py`: 핵심 노드

### `assistant_bringup`

- 역할: 런치 및 설정 묶음
- 주요 디렉토리:
  - `launch`: 실행 시나리오별 launch 파일
  - `config`: 노드 파라미터 yaml
  - `assistant_bringup/tools`: 라이브 음성 스텁 CLI

### `assistant_commands`

- 역할: 음성 명령 정규화/스키마/동의어 처리
- 주요 디렉토리:
  - `assistant_commands/command_schema.py`: 표준 명령 모델
  - `assistant_commands/command_normalizer.py`, `llm_normalizer.py`: 명령 정규화
  - `assistant_commands/command_executor.py`: 실행 연결부

### `assistant_gui`

- 역할: 대시보드, 지도, 상태 표시, 사용자 인터랙션
- 주요 디렉토리:
  - `assistant_gui/pages`: 홈/일정/설정/유틸/음성/날씨 페이지
  - `assistant_gui/engines`: 날씨/배터리/OCR/알람/스케줄 엔진
  - `assistant_gui/face`: 표정 렌더링/상태/애니메이션
  - `assistant_gui/integrations`: ROS 상태 브리지
  - `assistant_gui/map_view.py`, `assistant_gui/path_planner.py`: 지도 및 경로 표시

### `assistant_interfaces`

- 역할: 프로젝트 공통 메시지/서비스/액션 인터페이스
- 주요 디렉토리:
  - `msg`: 커스텀 메시지
  - `srv`: 서비스 정의
  - `action`: 액션 정의

### `assistant_robot`

- 역할: 로봇측 오케스트레이션, 임무 큐, 실행기, 안전 로직
- 주요 디렉토리:
  - `assistant_robot/nodes`: ROS2 노드 엔트리
  - `assistant_robot/orchestrator`: 큐/디스패처/상태머신
  - `assistant_robot/executors`: 임무별 실행기
  - `assistant_robot/adapters`: 실제/모의 어댑터
  - `assistant_robot/services`: TTS/스케줄/인사 등 서비스 계층
  - `assistant_robot/models`: 도메인 모델

## 6) 빌드/실행

```bash
cd /home/mythos/assistant_ws
colcon build --base-paths src/assistant
source install/setup.bash
```

대표 실행 예시:

```bash
# GUI
ros2 run assistant_gui assistant_gui_node

# Brain
ros2 run assistant_brain intent_router_node
ros2 run assistant_brain dialog_manager_node

# Audio
ros2 run assistant_audio wake_word_node
ros2 run assistant_audio stt_node
ros2 run assistant_audio tts_node

# Robot Orchestrator
ros2 run assistant_robot omni_orchestrator_node
```

## 6-1) 런타임 환경변수(자주 쓰는 항목)

- `ASSISTANT_SECRETS_FILE`: 공용 시크릿 파일 경로
- `ASSISTANT_ENABLE_ROS_BRIDGE`: GUI에서 ROS 브리지 활성화 (`1/true`)
- `ASSISTANT_FACE_VOICE_LOOP`: GUI 음성 루프 활성화 (`1/true`)
- `ASSISTANT_VOICE_ONLY_FACE_MODE`: 음성 전용 얼굴 화면 고정 모드 (`1/true`)
- `ASSISTANT_ROBOT_IP`: GUI/PC가 붙을 원격 로봇 IP. 미지정 시 현재 기본값은 `192.168.96.23`
- `ASSISTANT_TURTLEBOT_IP`: 기존 호환용 로봇 IP 이름. 없으면 `ASSISTANT_ROBOT_IP`를 우선 사용

## 7) 문서/주석 정리 원칙

- 공개 저장소 기준으로 민감정보(실키/토큰) 하드코딩 금지
- 복잡한 로직에만 짧고 명확한 주석 유지
- 테스트/빌드 산출물(`__pycache__`, `.pyc`, `.pytest_cache`) 커밋 금지
