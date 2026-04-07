# assistant_interfaces

프로젝트 공통 ROS 인터페이스(msg/srv/action)를 정의하는 패키지입니다.

## 디렉토리 구조

- assistant_interfaces/
  - msg/: 메시지 정의
    - AssistantIntent.msg
    - AssistantState.msg
    - VoiceTranscript.msg
  - srv/: 서비스 정의
    - GetRobotStatus.srv
  - action/: 액션 정의
    - FollowPerson.action
    - GuideToNamedPlace.action
    - PatrolOnce.action

## 사용 목적

- 노드 간 타입 계약을 통일해 패키지 결합도를 낮춤
- GUI/Brain/Robot/Audio 간 메시지 포맷 일관성 유지
