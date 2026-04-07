from __future__ import annotations

from assistant_robot.interfaces.ocr_service import BaseOCRService, OCRResult


class MockOCRService(BaseOCRService):
    def extract_delivery_target(self, raw_input: str) -> OCRResult:
        # TODO: Replace with OCR parsing pipeline when the real OCR service is available.
        parts = raw_input.split("@")
        target_user = parts[0].strip() if parts else None
        target_location = parts[1].strip() if len(parts) > 1 else None
        return OCRResult(target_user=target_user, target_location=target_location, confidence=0.9, raw_text=raw_input)
