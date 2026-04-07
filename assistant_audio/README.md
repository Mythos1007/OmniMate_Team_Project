# assistant_audio

음성 입력/출력(STT/TTS) 및 웨이크워드 처리를 담당하는 ROS2 패키지입니다.

## 디렉토리 구조

- assistant_audio/
  - assistant_audio/
    - input_providers/: 버튼/텍스트 입력 소스
    - providers/: STT/TTS 백엔드 구현
    - stt_node.py: 음성 인식 노드
    - tts_node.py: 음성 합성 노드
    - wake_word_node.py: 웨이크워드 노드
  - tools/: 로컬 테스트 CLI

## 주요 코드 설명

- assistant_audio/providers/stt_provider.py
  - STT 백엔드 추상화 및 구현(mock/pocketsphinx/whisper)
- assistant_audio/providers/tts_provider.py
  - TTS 백엔드 추상화 및 구현(edge/speech-dispatcher/elevenlabs/cartesia)
  - 공용 시크릿 파일(`ASSISTANT_SECRETS_FILE`) 지원
- assistant_audio/stt_node.py
  - `/assistant/wake` 이벤트를 받아 전사 결과를 발행
- assistant_audio/tts_node.py
  - `/assistant/speak`를 구독해 TTS 백엔드로 출력

## 시크릿/환경변수

- 공용 시크릿 파일 우선순위
  - `ASSISTANT_TTS_SECRETS_FILE`
  - `ASSISTANT_SECRETS_FILE`
  - 기본값: `~/.config/assistant/secrets.json`
- 주요 키
  - `elevenlabs_api_key`, `elevenlabs_voice_id`
  - `cartesia_api_key`, `cartesia_voice_id`

## 실행 엔트리포인트

- wake_word_node
- stt_node
- tts_node
- tts_smoke_test
- mic_stt_test
- mic_echo_test
