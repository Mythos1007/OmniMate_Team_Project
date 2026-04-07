from __future__ import annotations

from datetime import datetime

from assistant_robot.interfaces.weather_provider import BaseWeatherProvider, WeatherData


class MockWeatherProvider(BaseWeatherProvider):
    def __init__(self, weather: WeatherData | None = None) -> None:
        self.weather = weather or WeatherData(
            temperature_c=23.0,
            condition="흐림",
            humidity_percent=55,
            rain_probability_percent=40,
            location_name="인천",
            summary="흐리고 약한 바람이 붑니다",
            observed_at=datetime.utcnow(),
        )

    def get_current_weather(self, *, location_name: str | None = None) -> WeatherData:
        if location_name:
            self.weather.location_name = location_name
        return self.weather
