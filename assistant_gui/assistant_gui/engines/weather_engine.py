import threading
import time
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from PySide6.QtCore import QObject, Signal


class WeatherEngine(QObject, threading.Thread):
    weather_updated = Signal()

    @staticmethod
    def _resolve_secrets_file_path() -> Path:
        configured = os.getenv("ASSISTANT_WEATHER_SECRETS_FILE", "").strip()
        if configured:
            return Path(configured).expanduser()
        shared_configured = os.getenv("ASSISTANT_SECRETS_FILE", "").strip()
        if shared_configured:
            return Path(shared_configured).expanduser()
        return Path.home() / ".config" / "assistant" / "secrets.json"

    @classmethod
    def _load_api_key(cls) -> str:
        env_key = os.getenv("ASSISTANT_WEATHER_API_KEY", "").strip()
        if env_key:
            return env_key

        secrets_file = cls._resolve_secrets_file_path()
        if not secrets_file.exists():
            return ""
        try:
            loaded = json.loads(secrets_file.read_text(encoding="utf-8"))
        except Exception:
            return ""
        if not isinstance(loaded, dict):
            return ""
        return str(loaded.get("weather_api_key", "")).strip()

    def __init__(self):
        QObject.__init__(self)
        threading.Thread.__init__(self, daemon=True)
        # 보안상 API 키는 코드에 하드코딩하지 않고 외부 설정에서만 로드 기능.
        self.api_key = self._load_api_key()
        self.nx, self.ny = "54", "124"  # 인천 고잔동 좌표
        self.lat, self.lon = 37.3886, 126.6424  # 인천 고잔동 위경도

        self.temp, self.icon, self.desc = "--°", "⏳", "확인중"
        self.air = "보통"
        self.forecast_hourly = []  # 시간별 예보
        self.forecast_weekly = []  # 주간 예보

    @staticmethod
    def _label_from_pm10(pm10: float) -> str:
        # 환경부 PM10 기준(좋음/보통/나쁨/매우나쁨)
        if pm10 <= 30:
            return "좋음"
        if pm10 <= 80:
            return "보통"
        if pm10 <= 150:
            return "나쁨"
        return "매우나쁨"

    @staticmethod
    def _label_from_pm25(pm25: float) -> str:
        # 환경부 PM2.5 기준(좋음/보통/나쁨/매우나쁨)
        if pm25 <= 15:
            return "좋음"
        if pm25 <= 35:
            return "보통"
        if pm25 <= 75:
            return "나쁨"
        return "매우나쁨"

    def update_air_quality(self):
        # Open-Meteo 공기질 API는 키가 필요 없어 배포/개발 환경에서 바로 사용 가능하다.
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": "pm10,pm2_5",
            "timezone": "Asia/Seoul",
        }

        res = requests.get(url, params=params, timeout=10).json()
        current = res.get("current", {})
        pm10 = current.get("pm10")
        pm25 = current.get("pm2_5")

        if pm10 is None and pm25 is None:
            return

        # 두 지표 중 더 나쁜 등급을 사용해 사용자에게 보수적으로 표기.
        labels = []
        if pm10 is not None:
            labels.append(self._label_from_pm10(float(pm10)))
        if pm25 is not None:
            labels.append(self._label_from_pm25(float(pm25)))

        severity = {"좋음": 0, "보통": 1, "나쁨": 2, "매우나쁨": 3}
        self.air = max(labels, key=lambda x: severity.get(x, 1))

    def get_weather_info(self, sky, pty):
        if pty in ["1", "4"]:
            return "🌧️", "비/소나기"
        if pty == "2":
            return "🌧️❄️", "진눈깨비"
        if pty == "3":
            return "❄️", "눈"
        if sky == "1":
            return "☀️", "맑음"
        if sky == "3":
            return "⛅", "구름많음"
        return "☁️", "흐림"

    def update_weather(self):
        try:
            self.update_air_quality()

            if not self.api_key:
                self.temp, self.icon, self.desc = "--°", "⚠️", "날씨 API 키 미설정"
                self.forecast_hourly = []
                self.forecast_weekly = []
                self.weather_updated.emit()
                return

            now = datetime.now()
            base_dt = now - timedelta(hours=1) if now.minute < 45 else now
            base_date = base_dt.strftime("%Y%m%d")
            base_time = base_dt.strftime("%H30")

            # [1] 초단기예보 (현재 기온 및 시간별)
            url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtFcst"
            params = {
                "serviceKey": self.api_key,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": self.nx,
                "ny": self.ny,
                "numOfRows": 1000,
            }

            res = requests.get(url, params=params, timeout=10).json()
            if res.get("response", {}).get("header", {}).get("resultCode") == "00":
                items = res["response"]["body"]["items"]["item"]
                fcst_dict = {}
                for item in items:
                    t = item["fcstTime"]
                    if t not in fcst_dict:
                        fcst_dict[t] = {}
                    fcst_dict[t][item["category"]] = item["fcstValue"]

                sorted_times = sorted(fcst_dict.keys())
                if sorted_times:
                    curr_t = sorted_times[0]
                    self.temp = f"{fcst_dict[curr_t].get('T1H', '--')}°"
                    self.icon, self.desc = self.get_weather_info(
                        fcst_dict[curr_t].get("SKY", "1"),
                        fcst_dict[curr_t].get("PTY", "0"),
                    )

                    self.forecast_hourly = []
                    for t in sorted_times[:6]:
                        v = fcst_dict[t]
                        ico, _ = self.get_weather_info(v.get("SKY", "1"), v.get("PTY", "0"))
                        hour_str = f"{t[:2]}:00"
                        temp_str = v.get('T1H', '--')
                        self.forecast_hourly.append({"time": hour_str, "icon": ico, "temp": temp_str})

            # [2] 단기예보 (주간 예보용)
            url_short = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
            params_short = {
                "serviceKey": self.api_key,
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": "0500",
                "nx": self.nx,
                "ny": self.ny,
                "numOfRows": 1000,
            }

            res_s = requests.get(url_short, params=params_short, timeout=10).json()
            if res_s.get("response", {}).get("header", {}).get("resultCode") == "00":
                s_items = res_s["response"]["body"]["items"]["item"]
                daily_data = {}
                for item in s_items:
                    d = item["fcstDate"]
                    if d not in daily_data:
                        daily_data[d] = {"TMN": "--", "TMX": "--", "SKY": "1", "PTY": "0"}
                    if item["category"] in ["TMN", "TMX", "SKY", "PTY"]:
                        daily_data[d][item["category"]] = item["fcstValue"]

                sorted_days = sorted(daily_data.keys())
                self.forecast_weekly = []
                target_days = sorted_days[1:]
                for d in target_days[:3]:
                    v = daily_data[d]
                    ico, _ = self.get_weather_info(v["SKY"], v["PTY"])
                    date_str = f"{d[4:6]}/{d[6:8]}"
                    temp_range = f"{v['TMN']}°/{v['TMX']}°"
                    self.forecast_weekly.append({
                        "date": date_str,
                        "icon": ico,
                        "temp_range": temp_range,
                    })

            # Signal 발신
            self.weather_updated.emit()
        except Exception as e:
            print(f"Weather Update Error: {e}")

    def run(self):
        # 즉시 첫 업데이트
        self.update_weather()

        # 30분마다 갱신
        while True:
            time.sleep(1800)
            self.update_weather()
