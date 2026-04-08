# assistant_web

assistant_gui의 메인 구조와 디자인 언어를 웹으로 옮기기 위한 별도 대시보드 디렉토리입니다.

## 현재 구성

- 얼굴 대기 화면과 홈 대시보드 구조를 assistant_gui/main.py 흐름에 맞춰 웹으로 재구성
- 홈 화면의 지도, 날씨 카드, 현재 상태 카드, 메뉴 그리드를 웹에서 동일한 정보 구조로 제공
- 일정, 알람, 복약 확인 페이지를 웹용 CRUD로 추가
- 우편 전달, 음성 테스트, 설정 화면의 기본 구조를 웹으로 분리
- ROS 상태는 WebSocket으로 실시간 반영
- 기존 assistant_gui의 JSON 데이터 파일을 그대로 사용

## 디렉토리

- backend/
  - app/main.py: FastAPI 엔트리포인트
  - app/ros_bridge.py: ROS 토픽 구독/발행 브리지
  - app/weather_service.py: 날씨 조회 서비스
  - app/schemas.py: API 요청/응답 스키마
  - requirements.txt
- frontend/
  - index.html
  - app.js
  - style.css

## 토픽 연동

읽기:
- /assistant/state (가능한 경우)
- /assistant/status_text
- /assistant/orchestrator/status
- /assistant/gui_status
- /assistant/battery_percent
- /assistant/charging
- /battery_state
- /amcl_pose
- /odom

쓰기:
- /assistant/gui_command_text
- /assistant/manual_wake
- (지도 클릭) navigate:x=...,y=... 포맷을 /assistant/gui_command_text 로 발행

## HTTP API

읽기:
- /api/state
- /api/weather
- /api/map
- /api/map/image
- /api/gui-data
- /api/schedules
- /api/alarms
- /api/medications

쓰기:
- POST /api/command
- POST /api/manual-wake
- POST /api/navigate/click
- POST/PUT/DELETE /api/schedules
- POST/PUT/DELETE /api/alarms
- POST/PUT/DELETE /api/medications

## 실행 방법

```bash
cd /home/mythos/assistant_ws/src/assistant/assistant_web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# ROS를 함께 붙일 경우(같은 쉘에서)
source /home/mythos/assistant_ws/install/setup.bash
export ROS_DOMAIN_ID=116

uvicorn app.main:app --app-dir /home/mythos/assistant_ws/src/assistant/assistant_web/backend --host 0.0.0.0 --port 8090

# 또는 TLS 환경변수 기반 실행
python run_server.py

# 로컬 HTTPS(인증서 자동 생성) 실행
./start_https_local.sh
```

브라우저 접속:
- 같은 PC: http://localhost:8090
- 같은 와이파이 스마트폰: http://<서버IP>:8090
- HTTPS 로컬: https://localhost:8443
- HTTPS 와이파이: https://<서버IP>:8443

## 웹 배포 전략 (중요)

1. 로컬/같은 와이파이 전용 (가장 권장)
- 장점: 구성 단순, ROS 접근 쉬움
- 단점: 외부 인터넷에서 직접 접속 불가

2. 외부 정적 호스팅 + 로컬 API
- 프론트는 외부 호스팅 가능
- 하지만 브라우저 보안 정책 때문에 로컬 API를 직접 붙이기 까다로움

3. 외부 접속까지 원하면
- API 서버를 HTTPS + 인증 + 방화벽 포함으로 별도 운영 필요
- ROS 노출 대신 API만 노출하는 구조 필수

## 마이크 권한 주의사항

브라우저 마이크(getUserMedia, Web Speech API)는 보통 secure context가 필요합니다.

- 허용: https://... 또는 http://localhost
- 제한 가능: http://192.168.x.x 같은 일반 LAN 주소

스마트폰에서 마이크까지 안정적으로 쓰려면,
- 같은 와이파이 + HTTPS(로컬 인증서/리버스프록시) 구성이 가장 안전합니다.

권한 안정화 체크리스트:

1. 브라우저에서 페이지 접속 후 `권한 요청` 버튼 1회 실행
2. 주소가 `https://...` 또는 `http://localhost`인지 확인
3. Android Chrome 권한에서 마이크 허용 확인
4. iOS Safari는 설정 > Safari > 마이크 허용 확인
5. 처음 접속 시 자체 서명 인증서 경고를 수동으로 신뢰 처리

## 환경 변수

- ASSISTANT_WEB_HOST (기본 0.0.0.0)
- ASSISTANT_WEB_PORT (기본 8090)
- ASSISTANT_WEB_CORS (쉼표 구분, 기본 *)
- ASSISTANT_WEB_WS_INTERVAL (기본 0.5)
- ASSISTANT_WEATHER_LAT, ASSISTANT_WEATHER_LON
- ASSISTANT_WEATHER_API_KEY 또는 ASSISTANT_SECRETS_FILE
- ASSISTANT_WEB_TLS_CERT (HTTPS 인증서 경로)
- ASSISTANT_WEB_TLS_KEY (HTTPS 키 경로)
