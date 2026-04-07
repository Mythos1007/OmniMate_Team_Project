# assistant_brain

대화 상태 관리, 의도 라우팅, 명령 분배를 담당하는 ROS2 패키지입니다.

## 디렉토리 구조

- assistant_brain/
  - assistant_brain/
    - handlers/: 기능별 처리기(info/motion/navigation/task)
    - dialog_manager_node.py: 상태 머신 기반 대화 흐름 관리
    - intent_router_node.py: 음성 텍스트를 의도로 변환해 퍼블리시
    - command_dispatcher.py: 의도별 디스패치
    - state_machine.py: 상태 전이 규칙
  - tools/: 스텁 실행 도구
  - test/: 단위 테스트

## 주요 코드 설명

- assistant_brain/dialog_manager_node.py
  - wake/transcript/intent 이벤트를 받아 상태를 전이
- assistant_brain/intent_router_node.py
  - 텍스트를 정규 명령으로 변환하고 목적 토픽으로 전달
- assistant_brain/command_dispatcher.py
  - 등록된 핸들러를 통해 명령 실행 흐름 분리
