from __future__ import annotations

import json

from assistant_robot.services.runtime_data_service import RuntimeDataService


def test_runtime_data_service_reads_live_schedule_alarm_and_medication_summaries(tmp_path) -> None:
    schedule_path = tmp_path / 'schedules.json'
    alarm_path = tmp_path / 'alarms.json'
    medication_path = tmp_path / 'medications.json'

    schedule_path.write_text(
        json.dumps({"2026-04-08": [{"time": "09:00", "todo": "팀 미팅", "place": "로비"}]}, ensure_ascii=False),
        encoding='utf-8',
    )
    alarm_path.write_text(
        json.dumps([{"time": "07:30", "days": [], "target": "민수", "place": "집", "memo": "기상", "active": True}], ensure_ascii=False),
        encoding='utf-8',
    )
    medication_path.write_text(
        json.dumps({"last_run_date": "2026-04-08", "meds": [{"time": "08:00", "name": "민수", "pill": "혈압약", "active": False}]}, ensure_ascii=False),
        encoding='utf-8',
    )

    service = RuntimeDataService(
        schedule_path=schedule_path,
        alarm_path=alarm_path,
        medication_path=medication_path,
    )

    assert "팀 미팅" in service.build_schedule_summary("오늘 일정 알려줘")
    assert "07:30" in service.build_alarm_summary("오늘 알람 알려줘")
    assert "혈압약" in service.build_medication_summary("복약 확인해줘")


def test_runtime_data_service_can_add_schedule_alarm_and_medication(tmp_path) -> None:
    service = RuntimeDataService(
        schedule_path=tmp_path / 'schedules.json',
        alarm_path=tmp_path / 'alarms.json',
        medication_path=tmp_path / 'medications.json',
    )

    schedule_message = service.add_schedule_from_text('내일 오후 3시 팀 미팅 일정 추가해줘 장소는 회의실 A')
    alarm_message = service.add_alarm_from_text('오전 7시 알람 맞춰줘 메모는 기상')
    medication_message = service.add_medication_from_text('오전 8시 혈압약 복약 추가해줘')

    assert '추가' in schedule_message
    assert '알람' in alarm_message
    assert '복약 일정' in medication_message
    assert service.load_schedules()
    assert service.load_alarms()
    assert service.load_medications()
