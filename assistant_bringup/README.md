# assistant_bringup

전체 시스템 실행(노드 조합/파라미터/런치)을 담당하는 패키지입니다.

## 디렉토리 구조

- assistant_bringup/
  - launch/: 실행 시나리오별 launch 파일
  - config/: 노드 파라미터 yaml
  - assistant_bringup/tools/: 라이브 음성 스텁 CLI

## 주요 코드 설명

- launch/assistant_core.launch.py
  - 핵심 노드 묶음 실행
- launch/assistant_robot.launch.py
  - 로봇측 중심 실행
- launch/assistant_pc.launch.py
  - PC측 테스트 실행
- config/assistant_audio.yaml
  - 오디오 노드 파라미터(TTS/STT 관련)
- config/assistant_robot.yaml
  - 로봇 오케스트레이터 관련 설정
