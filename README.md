# OmniMate Team Project

OmniMate는 TurtleBot 기반 실내 안내 로봇 프로젝트다. 현재 최종본 기준으로 GUI, 음성, 작업 오케스트레이션, 일정 기반 작업, 확인 제스처, TurtleBot 주행 스택을 하나의 ROS 2 워크스페이스로 묶어 운영한다.

이 저장소는 다음 시나리오를 목표로 한다.

- PC에서 GUI와 상위 제어 로직을 실행한다.
- TurtleBot에서는 베이스 주행, 로봇 오디오 입출력, 사람 인식 같은 센서/실기반 노드를 실행한다.
- 사용자는 PC 마이크로 호출어를 말하고, 로봇 스피커로 응답을 듣는다.
- 배달, 복약, 알람 임무는 목적지 도착 후 확인 페이지를 통해 완료된다.

## 1. 현재 최종 동작 요약

현재 코드 기준 핵심 정책은 다음과 같다.

- 메인 실행 관리자: `assistant_robot/orchestrator/omni_orchestrator.py`
- ROS 브리지 노드: `assistant_robot/orchestrator/orchestrator_node.py`
- GUI 메인 앱: `assistant_gui/assistant_gui/main.py`
- 확인 페이지: `assistant_gui/assistant_gui/pages/utility_pages.py`
- 직접 안내 액션 브리지: `assistant_robot/nav_bridge_node.py`

현재 반영된 운영 정책:

- 호출어 입력 기본 경로는 `PC 마이크`다.
- 응답 출력 기본 경로는 `로봇 스피커`다.
- 배달 확인 후 자동으로 home 복귀하지 않는다.
- idle 상태에서 자동으로 home 복귀하지 않는다.
- named place 안내는 기본적으로 `위치 도착`만 요구하고, 각도 정렬은 명시적으로 필요한 장소에만 적용한다.
- 복귀 완료라는 별도 GUI 상태는 보여주지 않고, 끝나면 바로 일반 `대기 중...` 상태로 돌아간다.
- 배달/복약/알람의 확인 페이지는 도착 후 `WAITING_CONFIRMATION` 상태에서만 열린다.

## 2. 전체 로직 구조

### 2-1. 상위 흐름

1. 입력이 들어온다.
2. 명령이 정규화된다.
3. 오케스트레이터가 미션으로 변환한다.
4. 큐와 상태머신이 현재 실행 가능 여부를 판단한다.
5. 네비게이션/알림/복약/배달 실행기가 미션을 수행한다.
6. 도착 후 필요한 임무는 확인 대기 상태로 전환된다.
7. 확인이 끝나면 미션이 완료되고 GUI는 다시 대기 상태로 돌아간다.

### 2-2. 입력 경로

- PC 마이크 호출어: GUI 내부 글로벌 웨이크워드 루프
- 로봇 마이크 호출어: 로봇 측 `assistant_audio` 노드
- 일정/스케줄 입력: `assistant_robot/nodes/scheduler_node.py`
- GUI 직접 안내 버튼: GUI direct navigation client
- 텍스트 명령: `/assistant/command_text`

### 2-3. 상태 축

상태는 두 축으로 나뉜다.

- 대화/입력 상태: `LISTENING`, `PROCESSING`, `RESPONDING` 등
- 작업/로봇 상태: `IDLE`, `EXECUTING`, `WAITING_CONFIRMATION`, `CHARGING` 등

작업 상태는 `assistant_robot/orchestrator/state_machine.py`에서 관리한다.

### 2-4. 확인 임무 로직

배달, 복약, 알람은 공통적으로 다음 순서를 따른다.

1. 목적지 안내 시작
2. 목적지 도착
3. `WAITING_CONFIRMATION` 상태 진입
4. GUI 확인 페이지 표시
5. OK 제스처 또는 수동 OK 버튼으로 확인 완료
6. 현재 위치에서 임무 종료 후 idle 복귀

현재는 확인 완료 후 자동 home 복귀를 하지 않는다.

## 3. 패키지 역할

### `assistant_audio`

- wake word
- STT
- TTS
- 로봇/PC 오디오 입출력 토픽 관리

### `assistant_brain`

- 대화 상태
- 의도 라우팅
- 명령 해석 흐름

### `assistant_commands`

- 명령 스키마
- 정규화
- intent 관련 공통 모델

### `assistant_gui`

- 대시보드
- 지도/경로 표시
- 직접 안내 버튼
- 제스처 확인 화면
- 로컬 음성 루프
- 설정/일정/알람/복약 UI

### `assistant_interfaces`

- ROS 2 msg / srv / action 정의

### `assistant_robot`

- 오케스트레이터
- 작업 큐
- 상태머신
- 배달/복약/알람/복귀 executor
- nav bridge
- cmd_vel adapter
- 사람 인식

### `assistant_bringup`

- launch 파일
- 파라미터 yaml
- named place / nav2 config

## 4. 권장 운영 구성

현재 최종본 기준 권장 운영 방식은 `분산 실행`이다.

### PC에서 실행

- GUI
- orchestrator
- nav bridge
- scheduler
- Nav2 bringup
- RViz(optional)

### TurtleBot에서 실행

- TurtleBot base bringup
- robot wake word / STT / TTS
- cmd_vel adapter
- person recognition(optional)

현재 권장 launch는 `assistant_bringup/launch/assistant_production.launch.py`다.

## 5. PC / TurtleBot 패키지 분리

## PC에 있어야 하는 패키지

권장: 전체 저장소 그대로 사용

최소 실행 세트:

- `assistant_interfaces`
- `assistant_commands`
- `assistant_brain`
- `assistant_audio`
- `assistant_robot`
- `assistant_gui`
- `assistant_bringup`

이유:

- GUI가 메인 운영 화면이다.
- orchestrator와 nav bridge가 PC에서 실행된다.
- distributed production launch가 PC 측에서 `assistant_robot` 노드를 실행한다.

## TurtleBot에 옮겨야 하는 패키지

분산 운영 최소 세트:

- `assistant_interfaces`
- `assistant_commands`
- `assistant_audio`
- `assistant_robot`
- `assistant_bringup`

보통 TurtleBot에는 `assistant_gui`, `assistant_brain`은 필수가 아니다.

## 6. 필수 환경

- Ubuntu 22.04
- ROS 2 Humble
- Python 3.10
- `colcon`
- TurtleBot3 / Nav2 사용 환경

### Python 호환성 고정

현재 제스처/MediaPipe 안정성 기준 권장 버전:

```bash
pip install 'numpy<2.0'
pip install protobuf==4.25.3
```

현재 확인된 제스처 조합:

- `mediapipe==0.10.9`
- `numpy==1.26.4`
- `protobuf==4.25.3`

## 7. 빌드

저장소 루트에서 빌드한다.

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

부분 빌드 예시:

```bash
colcon build --symlink-install --packages-select assistant_gui
colcon build --symlink-install --packages-select assistant_robot assistant_bringup assistant_gui
```

## 8. 실행 방법

### 8-1. 단일 PC 테스트

로컬에서 GUI + brain + robot core를 한 PC에서 간단히 확인할 때:

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch assistant_bringup assistant_core.launch.py
```

이 모드는 로컬 통합 테스트용이다. 실제 TurtleBot 분산 운영 기본 경로는 아니다.

### 8-2. 권장 분산 운영

#### PC

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
source install/setup.bash

export ASSISTANT_SECRETS_FILE=~/.config/assistant/secrets.json

ros2 launch assistant_bringup assistant_production.launch.py \
  machine_role:=pc \
  ros_domain_id:=142 \
  ros_static_peers:=192.168.96.23 \
  map:=/absolute/path/to/map.yaml \
  nav2_params_file:=/absolute/path/to/nav2_burger_narrow.yaml \
  enable_rviz:=false
```

#### TurtleBot

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch assistant_bringup assistant_production.launch.py \
  machine_role:=robot \
  ros_domain_id:=142 \
  ros_static_peers:=<PC_IP>
```

`assistant_production.launch.py`는 내부적으로 다음 구성을 사용한다.

- PC: GUI + orchestrator + nav_bridge + scheduler + Nav2
- TurtleBot: robot audio + TurtleBot base + cmd_vel adapter + person recognition

## 9. TurtleBot로 패키지 옮기는 방법

현재 최종본 기준으로 TurtleBot에는 아래 디렉토리만 옮기면 된다.

- `assistant_interfaces/`
- `assistant_commands/`
- `assistant_audio/`
- `assistant_robot/`
- `assistant_bringup/`

예시:

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project

rsync -az assistant_interfaces/ user@<robot_ip>:~/OmniMate_Team_Project/assistant_interfaces/
rsync -az assistant_commands/ user@<robot_ip>:~/OmniMate_Team_Project/assistant_commands/
rsync -az assistant_audio/ user@<robot_ip>:~/OmniMate_Team_Project/assistant_audio/
rsync -az assistant_robot/ user@<robot_ip>:~/OmniMate_Team_Project/assistant_robot/
rsync -az assistant_bringup/ user@<robot_ip>:~/OmniMate_Team_Project/assistant_bringup/
```

TurtleBot에서 빌드:

```bash
cd ~/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select \
  assistant_interfaces assistant_commands assistant_audio assistant_robot assistant_bringup
source install/setup.bash
```

## 10. 현재 운영 기준 핵심 설정

### 음성

- 입력: PC 마이크
- 출력: 로봇 스피커
- GUI 저장 설정이 남아 있어도 시작 시 운영 모드에 맞게 다시 정렬된다.

### 안내 / 도착 판정

- GUI 도착 반경과 nav bridge proximity 반경은 현재 `0.10m`
- named place는 기본적으로 각도 정렬 없이 위치 도착만 본다.

### 확인 로직

- 배송 / 복약 / 알람은 도착 후 확인 페이지를 띄운다.
- OK 제스처가 불안정하면 수동 확인 버튼으로 완료 가능하다.
- 확인 후 현재 위치에서 idle로 복귀한다.

### 복귀 정책

- idle 자동 home 복귀 없음
- 배송 확인 후 자동 home 복귀 없음
- 사용자가 명시적으로 복귀를 지시했을 때만 복귀

## 11. 자주 쓰는 환경변수

- `ASSISTANT_SECRETS_FILE`
- `ASSISTANT_NAMED_PLACES_FILE`
- `ASSISTANT_ENABLE_ROS_BRIDGE`
- `ASSISTANT_FACE_VOICE_LOOP`
- `ASSISTANT_VOICE_ONLY_FACE_MODE`
- `ASSISTANT_NAV_REQUIRE_GOAL_ORIENTATION`
- `ASSISTANT_RETURN_SKIP_DISTANCE_M`

## 12. 트러블슈팅

### 제스처 인식이 계속 실패할 때

확인 순서:

1. `mediapipe`, `numpy`, `protobuf` 버전 확인
2. GUI 재실행
3. `/image_raw/compressed` 토픽 수신 여부 확인
4. 수동 OK 버튼으로 확인 경로 자체가 정상인지 확인

권장 버전:

```bash
pip install 'numpy<2.0'
pip install protobuf==4.25.3
```

### 확인창이 안 뜰 때

확인창은 도착 후 `WAITING_CONFIRMATION` 상태에서만 뜬다. 따라서 다음을 먼저 봐야 한다.

- 목표점까지 실제로 도착했는가
- Nav2가 near-goal abort를 내지 않았는가
- named place 좌표가 벽/협소 구역에 너무 붙어 있지 않은가
- 목적지 각도 정렬이 불필요하게 요구되지 않는가

### ROS 통신이 안 될 때

PC와 TurtleBot 둘 다 아래를 맞춘다.

```bash
export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

## 13. 추가 운영 문서

배포 패키지, 실행 순서, rsync 예시, 점검 체크리스트는 아래 문서를 본다.

- `docs/DEPLOYMENT.md`