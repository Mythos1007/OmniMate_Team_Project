import threading
import time
import os

import cv2
import easyocr

try:
    from assistant_gui.engines.delivery_target_catalog import (
        DELIVERY_TARGET_KEYWORDS,
        match_delivery_target,
    )
except ModuleNotFoundError:
    from engines.delivery_target_catalog import DELIVERY_TARGET_KEYWORDS, match_delivery_target


class OcrEngine(threading.Thread):
    """웹캠 프레임에서 부서명을 OCR로 감지하는 백그라운드 스레드."""

    _reader_lock = threading.Lock()
    _shared_reader = None
    _warmup_started = False
    _warmup_error = None

    def __init__(self, callback_func):
        super().__init__(daemon=True)
        self.cap = None
        self.source_name = ""
        self.reader = None
        self.callback = callback_func
        self.is_running = False

        self.current_mode = "SCANNING"
        self.temp_target = ""
        self.is_processing = False
        self.OFFICE_KEYWORDS = list(DELIVERY_TARGET_KEYWORDS)

    @classmethod
    def _load_shared_reader(cls):
        with cls._reader_lock:
            if cls._shared_reader is not None:
                return cls._shared_reader
            cls._shared_reader = easyocr.Reader(["ko", "en"], gpu=False)
            cls._warmup_error = None
            return cls._shared_reader

    @classmethod
    def _warmup_task(cls):
        try:
            cls._load_shared_reader()
        except Exception as exc:
            cls._warmup_error = str(exc)

    @classmethod
    def start_reader_warmup(cls):
        with cls._reader_lock:
            if cls._shared_reader is not None or cls._warmup_started:
                return
            cls._warmup_started = True
        threading.Thread(target=cls._warmup_task, daemon=True).start()

    def _try_open(self, source, name):
        cap = cv2.VideoCapture(source)
        if cap is not None and cap.isOpened():
            self.cap = cap
            self.source_name = name
            return True
        if cap is not None:
            cap.release()
        return False

    def _open_camera_with_fallback(self):
        # 우선순위: 터틀봇 스트림 URL -> 터틀봇 인덱스(기본 1) -> 노트북 웹캠(0)
        tb_url = os.getenv("ASSISTANT_TURTLEBOT_CAMERA_URL", "").strip()
        tb_index_raw = os.getenv("ASSISTANT_TURTLEBOT_CAMERA_INDEX", "1").strip()
        try:
            tb_index = int(tb_index_raw)
        except ValueError:
            tb_index = 1

        if tb_url and self._try_open(tb_url, "turtlebot-url"):
            return
        if self._try_open(tb_index, f"turtlebot-index-{tb_index}"):
            return
        if self._try_open(0, "laptop-webcam"):
            return
        raise RuntimeError("터틀봇/노트북 카메라를 모두 열지 못했습니다.")

    def run(self):
        self.is_running = True
        last_scan_time = 0.0

        try:
            self.callback(None, "INITIALIZING", "카메라 연결 중...")
            self._open_camera_with_fallback()
            self.callback(None, "INITIALIZING", f"OCR 모델 준비 중... ({self.source_name})")
            self.reader = self._load_shared_reader()
            self.callback(None, "SCANNING", self.source_name)
        except Exception as exc:
            self.is_running = False
            self.callback(None, "ERROR", str(exc))
            return

        while self.is_running:
            if self.cap is None:
                break
            ret, frame = self.cap.read()
            if not ret:
                continue

            display_img = cv2.resize(frame, (640, 480))
            h, w, _ = display_img.shape

            rw, rh = 640, 480
            rt, rb = (h // 2 - rh // 2), (h // 2 + rh // 2)
            rl, rr = (w // 2 - rw // 2), (w // 2 + rw // 2)

            if self.current_mode == "SCANNING" and not self.is_processing:
                if time.time() - last_scan_time > 1.2:
                    self.is_processing = True
                    last_scan_time = time.time()
                    roi = cv2.cvtColor(display_img[rt:rb, rl:rr], cv2.COLOR_BGR2GRAY)
                    threading.Thread(target=self._ocr_task, args=(roi,), daemon=True).start()

            color = (0, 255, 0) if self.current_mode == "SCANNING" else (0, 165, 255)
            cv2.rectangle(display_img, (rl, rt), (rr, rb), color, 3)

            self.callback(display_img, self.current_mode, self.temp_target)
            time.sleep(0.03)

    def _ocr_task(self, roi):
        if self.reader is None:
            self.is_processing = False
            return
        try:
            results = self.reader.readtext(roi, detail=0)
            text = "".join(results).replace(" ", "")
            match = match_delivery_target(text)
            if match:
                self.temp_target = match
                self.current_mode = "CONFIRMING"
        finally:
            self.is_processing = False

    def stop(self):
        self.is_running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
