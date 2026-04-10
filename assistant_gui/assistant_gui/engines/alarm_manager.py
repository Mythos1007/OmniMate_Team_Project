import json
import os


class AlarmManager:
    def __init__(self, filename: str = "alarms.json", on_save=None):
        self.filename = filename
        self._on_save = on_save
        self.alarms = []
        self.load_data()

    def load_data(self):
        """파일에서 데이터를 새로 읽어와 self.alarms에 덮어쓴다."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.alarms = json.load(f)
                    if not isinstance(self.alarms, list):
                        self.alarms = []
                    print(f"파일 로드 성공: {len(self.alarms)}개")
            except Exception as exc:
                print(f"로드 중 에러: {exc}")
                self.alarms = []
        else:
            self.alarms = []
        return self.alarms

    def save_data(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.alarms, f, ensure_ascii=False, indent=4)
            if callable(self._on_save):
                try:
                    self._on_save(self.alarms)
                except Exception:
                    pass
        except Exception as exc:
            print(f"알람 저장 오류: {exc}")

    def add_alarm(self, alarm: dict):
        self.alarms.append(alarm)
        self.save_data()

    def update_alarm(self, index: int, alarm: dict):
        if 0 <= index < len(self.alarms):
            self.alarms[index] = alarm
            self.save_data()
            return True
        return False

    def delete_alarm(self, index: int):
        if 0 <= index < len(self.alarms):
            self.alarms.pop(index)
            self.save_data()
            return True
        return False

    def check_now(self):
        import datetime

        now = datetime.datetime.now()
        if now.second != 0:
            return None

        curr_time = now.strftime("%H:%M")
        days_list = ["월", "화", "수", "목", "금", "토", "일"]
        curr_day = days_list[now.weekday()]

        for alarm in self.alarms:
            if alarm.get("active") and alarm.get("time") == curr_time:
                days = alarm.get("days", [])
                if (not days) or (curr_day in days):
                    return alarm
        return None
