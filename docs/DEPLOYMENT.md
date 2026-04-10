# OmniMate Deployment Guide

이 문서는 현재 최종본 기준으로 `PC`와 `TurtleBot`을 어떻게 나눠 배포하고 실행할지 정리한 운영 문서다.

## 1. 권장 운영 형태

권장 형태는 `PC + TurtleBot 분산 실행`이다.

### PC 역할

- GUI 운영 화면
- 오케스트레이터
- Nav2
- nav bridge
- scheduler
- 상위 명령 흐름 관리

### TurtleBot 역할

- 베이스 구동
- 로봇 스피커 TTS
- 로봇 마이크 STT / wake word
- cmd_vel adapter
- 사람 인식

## 2. 로봇으로 복사할 패키지

TurtleBot 최소 패키지 세트:

- `assistant_interfaces`
- `assistant_commands`
- `assistant_audio`
- `assistant_robot`
- `assistant_bringup`

복사하지 않아도 되는 패키지:

- `assistant_gui`
- `assistant_brain`

단, 로봇 단독 운용이나 별도 디버그가 필요하면 전체 저장소를 그대로 복제해도 된다.

## 3. 복사 예시

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project

ROBOT=user@<robot_ip>
REMOTE_DIR=~/OmniMate_Team_Project

rsync -az assistant_interfaces/ ${ROBOT}:${REMOTE_DIR}/assistant_interfaces/
rsync -az assistant_commands/ ${ROBOT}:${REMOTE_DIR}/assistant_commands/
rsync -az assistant_audio/ ${ROBOT}:${REMOTE_DIR}/assistant_audio/
rsync -az assistant_robot/ ${ROBOT}:${REMOTE_DIR}/assistant_robot/
rsync -az assistant_bringup/ ${ROBOT}:${REMOTE_DIR}/assistant_bringup/
rsync -az secrets.example.json ${ROBOT}:${REMOTE_DIR}/secrets.example.json
```

## 4. 빌드

### PC 빌드

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

### TurtleBot 빌드

```bash
cd ~/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select \
  assistant_interfaces assistant_commands assistant_audio assistant_robot assistant_bringup
source install/setup.bash
```

## 5. 실행 순서

### 5-1. TurtleBot 먼저

```bash
cd ~/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
source install/setup.bash

export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

ros2 launch assistant_bringup assistant_production.launch.py \
  machine_role:=robot \
  ros_domain_id:=142 \
  ros_static_peers:=<PC_IP>
```

### 5-2. PC 실행

```bash
cd /home/omnimate/OmniMate_ws/assistant/OmniMate_Team_Project
source /opt/ros/humble/setup.bash
source install/setup.bash

export ROS_DOMAIN_ID=142
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ASSISTANT_SECRETS_FILE=~/.config/assistant/secrets.json

ros2 launch assistant_bringup assistant_production.launch.py \
  machine_role:=pc \
  ros_domain_id:=142 \
  ros_static_peers:=<ROBOT_IP> \
  map:=/absolute/path/to/map.yaml \
  nav2_params_file:=/absolute/path/to/nav2_burger_narrow.yaml \
  enable_rviz:=false
```

## 6. 현재 운영 정책 체크리스트

실행 후 다음이 맞아야 한다.

- GUI가 열린다.
- PC 마이크 호출어 루프가 동작한다.
- 로봇 스피커로 TTS가 나온다.
- 배달/복약/알람 도착 후 확인창이 뜬다.
- 확인 완료 후 자동 home 복귀하지 않는다.
- 상태 카드는 `복귀 완료`가 아니라 일반 `대기 중...`로 돌아간다.

## 7. 점검 명령

### ROS 토픽 확인

```bash
ros2 topic list | grep assistant
ros2 topic echo /assistant/orchestrator/status --once
```

### 이미지 토픽 확인

```bash
ros2 topic list | grep image
ros2 topic hz /image_raw/compressed
```

### 패키지 확인

```bash
ros2 pkg prefix assistant_gui
ros2 pkg prefix assistant_robot
ros2 pkg prefix assistant_bringup
```

## 8. 자주 틀리는 부분

- `ROS_DOMAIN_ID`가 PC/로봇에서 다름
- `ROS_LOCALHOST_ONLY=1`로 남아 있음
- map 파일 경로가 PC에서 잘못됨
- named place 좌표가 벽에 붙어 있어 near-goal abort 발생
- mediapipe / protobuf 조합이 깨져 제스처 확인이 실패함

## 9. 제스처 인식 권장 버전

```bash
pip install 'numpy<2.0'
pip install protobuf==4.25.3
```

권장 조합:

- `mediapipe==0.10.9`
- `numpy==1.26.4`
- `protobuf==4.25.3`

## 10. 운영 메모

- named place는 기본적으로 위치 도착만 요구한다.
- 각도 정렬이 정말 필요한 장소만 `require_goal_orientation: true`를 명시한다.
- idle 자동 home 복귀는 꺼져 있다.
- 배송 확인 후 자동 home 복귀도 꺼져 있다.
- 사용자가 명시적으로 복귀를 지시했을 때만 복귀한다.