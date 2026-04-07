from assistant_robot.interfaces.confirmation_service import BaseConfirmationService
from assistant_robot.interfaces.face_service import BaseFaceRecognitionService, RecognizedFace
from assistant_robot.interfaces.intent_parser import BaseIntentParser, IntentParseResult
from assistant_robot.interfaces.navigation_controller import (
    BaseNavigationController,
    NavigationHandle,
    NavigationState,
)
from assistant_robot.interfaces.ocr_service import BaseOCRService, OCRResult
from assistant_robot.interfaces.seat_resolver import BaseSeatResolver
from assistant_robot.interfaces.tts_provider import BaseTTSProvider, TTSRequest
from assistant_robot.interfaces.weather_provider import BaseWeatherProvider, WeatherData

__all__ = [
    "BaseConfirmationService",
    "BaseFaceRecognitionService",
    "BaseIntentParser",
    "BaseNavigationController",
    "BaseOCRService",
    "BaseSeatResolver",
    "BaseTTSProvider",
    "IntentParseResult",
    "NavigationHandle",
    "NavigationState",
    "OCRResult",
    "RecognizedFace",
    "TTSRequest",
    "WeatherData",
]
