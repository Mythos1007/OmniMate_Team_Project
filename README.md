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

### 2-1) 시스템 패키지 먼저 설치 (apt 필요)

```bash
sudo apt update
sudo apt install -y \
  python3-pyaudio \
  portaudio19-dev \
  alsa-utils \
  libatlas-base-dev \
  libopenblas-dev
```

### 2-2) 핵심 Python 패키지 (setuptools에서 정의)

각 패키지의 setup.py에서 자동 설치:
- **assistant_gui**: PySide6, requests, SpeechRecognition, PyYAML
- **assistant_audio**: edge-tts, faster-whisper, requests, sounddevice, vosk
- **assistant_brain**: setuptools 만

### 2-3) 확장 Python 패키지 (공식 스크립트/빌드 시)

```bash
pip install \
  PySide6==6.11.0 \
  requests==2.33.1 \
  SpeechRecognition==3.16.0 \
  edge-tts==7.2.8 \
  faster-whisper==1.0.11 \
  vosk==0.3.45 \
  google-cloud-speech==2.25.0 \
  PyYAML==6.0.2 \
  numpy==1.26.4 \
  scipy==1.15.3 \
  opencv-python==4.8.0.74 \
  mediapipe==0.10.9 \
  face-recognition==1.3.0 \
  face-recognition-models==0.3.0 \
  easyocr==1.7.1 \
  ultralytics==8.4.17 \
  deepface==0.0.99 \
  mtcnn==1.0.0 \
  scikit-image==0.25.2 \
  sounddevice==0.5.5 \
  pandas==2.3.3 \
  pytz==2022.1 \
  python-dateutil==2.9.0.post0
```

### 2-4) 선택 설치 (클라우드/특수 기능)

```bash
# 클라우드 TTS
pip install elevenlabs==1.8.0 cartesia==1.0.0

# AI/ML (대규모 모델, 이미 설치됨)
# pip install tensorflow==2.15.1 torch==2.11.0 torchvision==0.26.0
```

### 2-5) NumPy 호환성 주의

- **mediapipe + NumPy 2.x 호환성 문제**: NumPy를 1.x 로 유지
  ```bash
  pip install 'numpy<2.0'
  ```
- 설치 후 환경 확인:
  ```bash
  python3 -c "import import mediapipe; print(mediapipe.__version__)"
  ```

## 3) 필수 ROS 2 패키지 (apt)

### 3-1) 기본 메시지/서비스 타입

```bash
sudo apt update
sudo apt install -y \
  ros-humble-nav2-msgs \
  ros-humble-geometry-msgs \
  ros-humble-std-msgs \
  ros-humble-std-srvs \
  ros-humble-launch \
  ros-humble-launch-ros \
  ros-humble-sensor-msgs \
  ros-humble-nav-msgs \
  ros-humble-control-msgs \
  ros-humble-diagnostics
```

### 3-2) 선택 설치 (특정 기능)

```bash
# TurtleBot 3 패키지 (로봇 사용 시)
sudo apt install -y \
  ros-humble-turtlebot3 \
  ros-humble-turtlebot3-msgs \
  ros-humble-dynamixel-sdk

# 고급 네비게이션 (경로 계획/SLAM)
sudo apt install -y \
  ros-humble-nav2-core \
  ros-humble-slam-toolbox \
  ros-humble-cartographer
```

### 3-3) 설치 확인

```bash
ros2 pkg list | grep -E "geometry_msgs|nav2_msgs|std_msgs"
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

### 6-1) 빌드

```bash
cd /home/omnimate/OmniMate_ws
colcon build --base-paths src/assistant --symlink-install
source install/setup.bash
```

### 6-2) 빌드 검증

```bash
# 설치된 패키지 확인
ros2 pkg list | grep assistant

# Python 패키지 임포트 확인
python3 -c "import assistant_gui; import assistant_audio; import assistant_brain; print('All imports OK')"

# 마이크/오디오 확인
arecord -l
```

### 6-3) 개별 노드 실행

**Audio 파이프라인:**
```bash
# Wake word 감지
ros2 run assistant_audio wake_word_node

# STT (음성 인식)
ros2 run assistant_audio stt_node

# TTS (음성 합성)
ros2 run assistant_audio tts_node

# 로컬 테스트 (마이크)
ros2 run assistant_audio mic_stt_test
```

**Brain (대화/의도):**
```bash
# 의도 라우팅
ros2 run assistant_brain intent_router_node

# 대화 관리
ros2 run assistant_brain dialog_manager_node
```

**GUI (대시보드):**
```bash
# 메인 GUI
ros2 run assistant_gui assistant_gui_node
```

**Robot (임무 오케스트레이션):**
```bash
# 로봇 오케스트레이터 (배달/내비게이션)
ros2 run assistant_robot omni_orchestrator_node
```

### 6-4) 통합 실행 (Launch 파일)

```bash
# 전체 시스템
ros2 launch assistant_bringup complete.launch.xml

# GUI + Audio 만
ros2 launch assistant_bringup gui_audio.launch.xml

# 음성 테스트 모드
ros2 launch assistant_bringup voice_test.launch.xml
```

## 7) 런타임 환경변수(자주 쓰는 항목)

- `ASSISTANT_SECRETS_FILE`: 공용 시크릿 파일 경로
- `ASSISTANT_ENABLE_ROS_BRIDGE`: GUI에서 ROS 브리지 활성화 (`1/true`)
- `ASSISTANT_FACE_VOICE_LOOP`: GUI 음성 루프 활성화 (`1/true`)
- `ASSISTANT_VOICE_ONLY_FACE_MODE`: 음성 전용 얼굴 화면 고정 모드 (`1/true`)
- `ASSISTANT_ROBOT_IP`: GUI/PC가 붙을 원격 로봇 IP. 미지정 시 현재 기본값은 `192.168.96.23`
- `ASSISTANT_TURTLEBOT_IP`: 기존 호환용 로봇 IP 이름. 없으면 `ASSISTANT_ROBOT_IP`를 우선 사용

## 8) 트러블슈팅

### 8-1) 음성 인식 (STT) 문제

**증상:** "speech_recognition 패키지가 없어 음성 인식을 실행할 수 없습니다"
```bash
# 해결
pip install SpeechRecognition vosk google-cloud-speech
```

**증상:** 마이크가 감지되지 않음
```bash
# 마이크 장치 확인
arecord -l

# 시스템 오디오 테스트
arecord -f dat test.wav && aplay test.wav

# pyaudio 설치 (시스템 권한 필요)
sudo apt install python3-pyaudio portaudio19-dev
```

### 8-2) mediapipe 호환성 문제

**증상:** `ImportError: cannot import name '_ARRAY_API'` 또는 `numpy.core.multiarray not found`
```bash
# NumPy 버전 고정
pip install 'numpy<2.0'
```

### 8-3) GUI 시작 오류

**증상:** `ModuleNotFoundError: No module named 'PySide6'`
```bash
# PySide6와 의존성 재설치
pip install PySide6==6.11.0
pip install --upgrade --force-reinstall PySide6
```

**증상:** GUI 창이 안 나타짐 (X11 / 원격 디스플레이)
```bash
# X11 권한 확인
echo $DISPLAY

# 필요시 명시
export DISPLAY=:0
```

### 8-4) ROS 2 빌드 오류

**증상:** `Package 'ament_cmake_python' not found`
```bash
# ROS 2 환경 재로드
source /opt/ros/humble/setup.bash
```

**증상:** `colcon: command not found`
```bash
# colcon 설치
sudo apt install python3-colcon-common-extensions
```

### 8-5) 환경변수 확인

```bash
# 모든 환경변수 확인
env | grep ASSISTANT

# 특정 변수
echo $ASSISTANT_SECRETS_FILE
echo $ASSISTANT_ROBOT_IP
```

### 8-6) 설치 검증 스크립트

```bash
#!/bin/bash
echo "=== OmniMate Assistant 설치 검증 ==="

echo "[1] Python 패키지 확인..."
python3 -c "
import sys
packages = ['PySide6', 'rclpy', 'requests', 'PyYAML', 'opencv_cv2', 'numpy', 
           'mediapipe', 'speech_recognition', 'edge_tts', 'vosk']
missing = []
for pkg in packages:
    try:
        __import__(pkg.replace('_', '-'))
    except ImportError:
        missing.append(pkg)
if missing:
    print(f'❌ 누락: {missing}')
else:
    print('✅ 모든 핵심 패키지 OK')
"

echo "[2] ROS 2 패키지 확인..."
ros2 pkg list | grep -q assistant_gui && echo "✅ assistant_gui OK" || echo "❌ assistant_gui 미설치"

echo "[3] 마이크 확인..."
arecord -l > /dev/null 2>&1 && echo "✅ 마이크 감지됨" || echo "❌ 마이크 미감지"

echo "[4] 환경변수 확인..."
[ -n "$ASSISTANT_SECRETS_FILE" ] && echo "✅ ASSISTANT_SECRETS_FILE 설정됨" || echo "⚠️  ASSISTANT_SECRETS_FILE 미설정"

echo "=== 검증 완료 ==="
```

## 9) 문서/주석 정리 원칙

- 공개 저장소 기준으로 민감정보(실키/토큰) 하드코딩 금지
- 복잡한 로직에만 짧고 명확한 주석 유지
- 테스트/빌드 산출물(`__pycache__`, `.pyc`, `.pytest_cache`) 커밋 금지
