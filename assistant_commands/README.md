# assistant_commands

음성 명령을 표준 명령 구조(CanonicalCommand)로 정규화하는 라이브러리 패키지입니다.

## 디렉토리 구조

- assistant_commands/
  - assistant_commands/
    - command_schema.py: 표준 명령 타입 정의
    - command_normalizer.py: 규칙 기반 정규화
    - llm_normalizer.py: LLM 기반 정규화 보조
    - parser_utils.py: 텍스트 전처리/인자 파싱
    - synonyms.py: 동의어/패턴 사전
    - command_executor.py: 명령 실행 연결
  - test/: 명령 정규화 테스트

## 주요 코드 설명

- assistant_commands/command_normalizer.py
  - 자연어 텍스트를 표준 명령 이름으로 매핑
- assistant_commands/parser_utils.py
  - 숫자/시간/측정치 등 인자 파싱 유틸
- assistant_commands/command_schema.py
  - 전체 시스템이 공유하는 명령 데이터 구조
