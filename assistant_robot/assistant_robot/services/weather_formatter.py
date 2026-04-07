from __future__ import annotations

from assistant_robot.interfaces.weather_provider import WeatherData


class WeatherFormatter:
    """기능: 같은 날씨 데이터를 GUI용/TTS용 표현으로 분리 변환한다."""

    def format_for_gui(self, weather: WeatherData) -> str:
        humidity = f"습도 {weather.humidity_percent}%" if weather.humidity_percent is not None else "습도 정보 없음"
        return f"{weather.temperature_c:.0f}도 | {weather.condition} | {humidity}"

    def build_tts_payload(self, weather: WeatherData) -> dict[str, object]:
        # 기능: TTS 메시지 템플릿에서 바로 쓸 placeholder payload를 만든다.
        summary = weather.summary or weather.condition
        payload: dict[str, object] = {
            "temperature": int(round(weather.temperature_c)),
            "weather_summary": summary,
        }
        if weather.rain_probability_percent is not None:
            payload["rain_probability"] = weather.rain_probability_percent
        if weather.humidity_percent is not None:
            payload["humidity"] = weather.humidity_percent
        if weather.location_name:
            payload["location_name"] = weather.location_name
        return payload

    def format_for_tts(self, weather: WeatherData) -> str:
        payload = self.build_tts_payload(weather)
        sentence = f"현재 기온은 {payload['temperature']}도이고, 날씨는 {payload['weather_summary']}입니다."
        if "rain_probability" in payload:
            sentence += f" 강수 확률은 {payload['rain_probability']}퍼센트입니다."
        return sentence
