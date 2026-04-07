# assistant_brain

대화 상태 관리, 의도 분류/라우팅, 명령 분배를 담당하는 ROS2 패키지입니다.

## 디렉토리 구조

- assistant_brain/
  - assistant_brain/
    - handlers/: 기능별 처리기(info/motion/navigation/task)
    - dialog_manager_node.py: 상태 머신 기반 대화 흐름 관리
    - intent_router_node.py: 전사 텍스트 분류 + 카테고리 라우팅
    - intent_rules.py: 키워드 기반 의도 규칙
    - chat_responder.py: chat 카테고리 응답 생성
    - command_dispatcher.py: command 처리 디스패치
    - state_machine.py: 상태 전이 규칙
  - tools/: 스텁 실행 도구
  - test/: 단위 테스트

## 주요 코드 설명

- assistant_brain/dialog_manager_node.py
  - wake/transcript/intent 이벤트를 받아 상태를 전이
- assistant_brain/intent_router_node.py
  - `CommandNormalizer` 우선 분류 후 실패 시 `intent_rules`로 보강 분류
  - `command/query/chat` 카테고리로 분기해 처리
- assistant_brain/command_dispatcher.py
  - 등록된 핸들러를 통해 명령 실행 흐름 분리

## 토픽/서비스 인터페이스

- subscribe
  - `/assistant/transcript` (`assistant_interfaces/msg/VoiceTranscript`)
- publish
  - `/assistant/intent` (`assistant_interfaces/msg/AssistantIntent`)
  - `/assistant/speak` (`std_msgs/msg/String`)
  - `/assistant/status_text` (`std_msgs/msg/String`)
- client
  - `/assistant/get_robot_status` (`assistant_interfaces/srv/GetRobotStatus`)

## 실행 엔트리포인트

- `dialog_manager_node`
- `intent_router_node`
- `stub_demo_cli`
