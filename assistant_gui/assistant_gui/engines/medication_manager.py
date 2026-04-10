import json
import os
from datetime import datetime


class MedicationManager:
    def __init__(self, filename: str = "medications.json", on_save=None):
        self.filename = filename
        self._on_save = on_save
        self.meds = []
        self.last_run_date = datetime.now().strftime("%Y-%m-%d")
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # Backward compatibility: old file shape can be a plain list.
                    if isinstance(data, list):
                        self.meds = data
                        self.last_run_date = datetime.now().strftime("%Y-%m-%d")
                    else:
                        self.meds = data.get("meds", [])
                        self.last_run_date = data.get("last_run_date", datetime.now().strftime("%Y-%m-%d"))
            except Exception as exc:
                print(f"데이터 로드 에러: {exc}")
                self.meds = []
        else:
            self.meds = []

        self.check_daily_reset()
        self.sort_meds()
        return self.meds

    def check_daily_reset(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_run_date != today:
            for med in self.meds:
                med["active"] = False
            self.last_run_date = today
            self.save_data()

    def save_data(self):
        save_dict = {
            "last_run_date": self.last_run_date,
            "meds": self.meds,
        }
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(save_dict, f, ensure_ascii=False, indent=4)
        if callable(self._on_save):
            try:
                self._on_save(save_dict)
            except Exception:
                pass

    def sort_meds(self):
        self.meds.sort(key=lambda x: x.get("time", "00:00"))

    def add_med(self, time_str: str, name: str, pill: str):
        self.meds.append({"time": time_str, "name": name, "pill": pill, "active": False})
        self.sort_meds()
        self.save_data()

    def update_med(self, index: int, time_str: str, name: str, pill: str):
        if 0 <= index < len(self.meds):
            self.meds[index].update({"time": time_str, "name": name, "pill": pill})
            self.sort_meds()
            self.save_data()
            return True
        return False

    def delete_med(self, index: int):
        if 0 <= index < len(self.meds):
            del self.meds[index]
            self.save_data()
            return True
        return False
