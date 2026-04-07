from __future__ import annotations

from datetime import datetime
import importlib

from assistant_robot.interfaces.weather_provider import BaseWeatherProvider, WeatherData


class ExistingWeatherAdapter(BaseWeatherProvider):
    def __init__(self, engine: object | None = None) -> None:
        self._engine = engine
        if self._engine is None:
            try:
                weather_module = importlib.import_module("assistant_gui.weather")
            except ModuleNotFoundError:
                weather_module = None
            WeatherEngine = getattr(weather_module, "WeatherEngine", None) if weather_module is not None else None
            if WeatherEngine is not None:
                self._engine = WeatherEngine()
                # TODO: Connect lifecycle ownership to the GUI process if the existing engine already runs elsewhere.
                if hasattr(self._engine, "start"):
                    self._engine.start()

    def get_current_weather(self, *, location_name: str | None = None) -> WeatherData:
        if self._engine is None:
            raise RuntimeError("Existing weather engine is not available")
        temp_text = str(getattr(self._engine, "temp", "0")).replace("°", "")
        try:
            temperature = float(temp_text)
        except ValueError:
            temperature = 0.0
        return WeatherData(
            temperature_c=temperature,
            condition=str(getattr(self._engine, "desc", "확인중")),
            humidity_percent=None,
            rain_probability_percent=None,
            location_name=location_name,
            summary=str(getattr(self._engine, "desc", "확인중")),
            observed_at=datetime.utcnow(),
        )
