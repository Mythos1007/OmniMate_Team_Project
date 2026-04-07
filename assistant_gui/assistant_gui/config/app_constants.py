EDGE_TTS_VOICES = [
    "ko-KR-SunHiNeural",
    "ko-KR-SuJinNeural",
    "ko-KR-InJoonNeural",
    "ko-KR-BongJinNeural",
    "ko-KR-GookMinNeural",
    "ko-KR-HyunsuNeural",
    "ko-KR-JiMinNeural",
    "ko-KR-SeoHyunNeural",
]

TTS_SCENARIO_DEFAULTS = [
    ("wakeword_prompt", "호출어 응답", "네, 부르셨나요? 말씀해주세요."),
    ("wakeword_only_mode", "호출어 테스트 모드", "호출어 테스트 모드입니다. 명령 처리는 비활성화되어 있어요."),
    ("schedule_query", "일정 조회", "일정 조회 요청을 확인했어요. 현재 일정을 확인해볼게요."),
    ("alarm_set", "알람 설정", "알람 설정 요청을 확인했어요."),
    ("alarm_query", "알람 조회", "저장된 알람을 확인해볼게요."),
    ("medication_query", "복약 조회", "복약 정보를 확인해드릴게요."),
    ("cancel", "취소/중지", "요청을 취소했어요."),
    ("weather", "날씨 안내", "현재 날씨 정보를 안내해드릴게요."),
    ("where_status", "이동 상태 안내", "지금 {장소}로 가고 있어요."),
    ("delivery_request", "배달/배송 요청", "{장소} 배달 요청을 확인했어요."),
    ("navigation_request", "이동 요청", "{장소}로 안내를 시작할게요."),
    ("unknown", "이해 실패", "요청을 이해하지 못했어요. 다시 말씀해주세요."),
]
