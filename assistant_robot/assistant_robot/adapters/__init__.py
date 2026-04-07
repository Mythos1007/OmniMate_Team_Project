from assistant_robot.adapters.dev_tts_provider import DevTTSProvider
from assistant_robot.adapters.existing_weather_adapter import ExistingWeatherAdapter
from assistant_robot.adapters.mock_confirmation_service import MockConfirmationService
from assistant_robot.adapters.mock_face_service import MockFaceRecognitionService
from assistant_robot.adapters.mock_intent_parser import MockIntentParser
from assistant_robot.adapters.mock_navigation_controller import MockNavigationController
from assistant_robot.adapters.mock_ocr_service import MockOCRService
from assistant_robot.adapters.mock_seat_resolver import MockSeatResolver
from assistant_robot.adapters.mock_tts_provider import MockTTSProvider
from assistant_robot.adapters.mock_weather_provider import MockWeatherProvider
from assistant_robot.adapters.prod_tts_provider import DemoProdTTSProvider

__all__ = [
    "DemoProdTTSProvider",
    "DevTTSProvider",
    "ExistingWeatherAdapter",
    "MockConfirmationService",
    "MockFaceRecognitionService",
    "MockIntentParser",
    "MockNavigationController",
    "MockOCRService",
    "MockSeatResolver",
    "MockTTSProvider",
    "MockWeatherProvider",
]
