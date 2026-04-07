import json
import os


class ScheduleManager:
    def __init__(self, filename="schedules.json"):
        self.filename = filename
        self.schedules = self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_data(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.schedules, f, ensure_ascii=False, indent=4)

    def add_item(self, date_str, time_str, todo, place):
        if date_str not in self.schedules:
            self.schedules[date_str] = []
        self.schedules[date_str].append({"time": time_str, "todo": todo, "place": place})
        self.save_data()

    def get_all_dates(self):
        return list(self.schedules.keys())

    def get_schedules_for_date(self, date_str):
        return self.schedules.get(date_str, [])

    def update_item(self, date_str, index, time, todo, place):
        if date_str in self.schedules and len(self.schedules[date_str]) > index:
            self.schedules[date_str][index] = {"time": time, "todo": todo, "place": place}
            self.save_data()
            return True
        return False

    def delete_item(self, date_str, index):
        try:
            if date_str in self.schedules and 0 <= index < len(self.schedules[date_str]):
                del self.schedules[date_str][index]
                if not self.schedules[date_str]:
                    del self.schedules[date_str]
                self.save_data()
                return True
            return False
        except Exception:
            return False
