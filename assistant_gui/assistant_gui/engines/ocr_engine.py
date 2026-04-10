import threading
import time
import os
import json
import subprocess
import tempfile
from pathlib import Path

import cv2

try:
    import torch
except Exception:
    torch = None

try:
    from assistant_gui.engines.gpu_vision import bgr_to_gray
except ModuleNotFoundError:
    from engines.gpu_vision import bgr_to_gray

try:
    from assistant_gui.engines.delivery_target_catalog import (
        load_delivery_target_lookup,
        match_delivery_target_from_lookup,
    )
except ModuleNotFoundError:
    from engines.delivery_target_catalog import load_delivery_target_lookup, match_delivery_target_from_lookup

try:
    from assistant_gui.engines.ros_camera_capture import RosCameraCapture
except ModuleNotFoundError:
    from engines.ros_camera_capture import RosCameraCapture


class OcrEngine(threading.Thread):
    """웹캠 프레임에서 부서명을 OCR로 감지하는 백그라운드 스레드."""

    _reader_lock = threading.Lock()
    _shared_backend = None
    _warmup_started = False
    _warmup_error = None
    _helper_lock = threading.Lock()

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
        self._delivery_lookup = load_delivery_target_lookup()

    @staticmethod
    def _ocr_helper_python() -> str | None:
        configured = os.getenv("ASSISTANT_OCR_PYTHON", "").strip()
        if configured and Path(configured).exists():
            return configured
        default_helper = Path.home() / "OmniMate_ws" / ".venv-yolo" / "bin" / "python"
        if default_helper.exists():
            return str(default_helper)
        return None

    @classmethod
    def _should_use_gpu(cls) -> bool:
        configured = os.getenv("ASSISTANT_OCR_USE_GPU", "auto").strip().lower()
        if configured in {"1", "true", "yes", "on"}:
            return True
        if configured in {"0", "false", "no", "off"}:
            return False
        return bool(torch is not None and torch.cuda.is_available())

    @classmethod
    def _ocr_helper_script(cls) -> Path:
        return Path(__file__).resolve().with_name("ocr_helper.py")

    @classmethod
    def _start_helper_backend(cls):
        helper_python = cls._ocr_helper_python()
        helper_script = cls._ocr_helper_script()
        if not helper_python or not helper_script.exists():
            raise RuntimeError("OCR helper Python 환경을 찾지 못했습니다.")

        process = subprocess.Popen(
            [helper_python, str(helper_script), "--stdio", f"--gpu={'1' if cls._should_use_gpu() else '0'}"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )

        ready = process.stdout.readline().strip() if process.stdout is not None else ""
        if ready != "READY":
            error_output = ""
            if process.stderr is not None:
                error_output = process.stderr.readline().strip()
            process.terminate()
            raise RuntimeError(error_output or "OCR helper 초기화에 실패했습니다.")
        return process

    @classmethod
    def _load_shared_backend(cls):
        with cls._reader_lock:
            if cls._shared_backend is not None:
                return cls._shared_backend
            helper_python = cls._ocr_helper_python()
            if helper_python:
                try:
                    cls._shared_backend = cls._start_helper_backend()
                    cls._warmup_error = None
                    return cls._shared_backend
                except Exception as exc:
                    cls._warmup_error = str(exc)
            try:
                import easyocr

                cls._shared_backend = easyocr.Reader(["ko", "en"], gpu=cls._should_use_gpu())
                cls._warmup_error = None
                return cls._shared_backend
            except Exception as exc:
                cls._warmup_error = str(exc)
                raise

    @classmethod
    def _read_text_with_backend(cls, backend, roi) -> list[str]:
        if hasattr(backend, "readtext"):
            return list(backend.readtext(roi, detail=0))

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            cv2.imwrite(str(temp_path), roi)
            with cls._helper_lock:
                if backend.stdin is None or backend.stdout is None:
                    raise RuntimeError("OCR helper 입출력 파이프가 비정상입니다.")
                backend.stdin.write(json.dumps({"image_path": str(temp_path)}, ensure_ascii=False) + "\n")
                backend.stdin.flush()
                response_raw = backend.stdout.readline().strip()
            response = json.loads(response_raw) if response_raw else {}
            if response.get("error"):
                raise RuntimeError(str(response.get("error")))
            texts = response.get("texts", [])
            if not isinstance(texts, list):
                return []
            return [str(text) for text in texts if str(text).strip()]
        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def _warmup_task(cls):
        try:
            cls._load_shared_backend()
        except Exception as exc:
            cls._warmup_error = str(exc)

    @classmethod
    def start_reader_warmup(cls):
        with cls._reader_lock:
            if cls._shared_backend is not None or cls._warmup_started:
                return
            cls._warmup_started = True
        threading.Thread(target=cls._warmup_task, daemon=True).start()

    def _try_open(self, source, name):
        if isinstance(source, str) and source.startswith("ros:"):
            topic = source[4:].strip()
            compressed_topic = ""
            image_topic = ""
            if topic.endswith("/compressed"):
                compressed_topic = topic
                image_topic = topic[: -len("/compressed")]
            else:
                image_topic = topic
                compressed_topic = f"{topic}/compressed"

            cap = RosCameraCapture(image_topic=image_topic, compressed_topic=compressed_topic)
            wait_sec = float(os.getenv("ASSISTANT_TURTLEBOT_CAMERA_WAIT_SEC", "1.2") or "1.2")
            if cap.isOpened() and cap.wait_for_first_frame(wait_sec):
                self.cap = cap
                self.source_name = name
                return True
            cap.release()
            return False

        candidates = [(source, None)]
        if isinstance(source, int) and hasattr(cv2, "CAP_V4L2"):
            candidates.append((source, cv2.CAP_V4L2))

        for candidate, backend in candidates:
            cap = cv2.VideoCapture(candidate) if backend is None else cv2.VideoCapture(candidate, backend)
            if cap is None:
                continue
            if cap.isOpened():
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
                self.cap = cap
                self.source_name = name
                return True
            cap.release()
        return False

    def _open_camera_with_fallback(self):
        # 우선순위: 터틀봇 ROS 토픽 -> 터틀봇 스트림 URL -> 터틀봇 인덱스 -> 노트북 웹캠
        tb_topic = os.getenv("ASSISTANT_TURTLEBOT_CAMERA_TOPIC", "/image_raw/compressed").strip()
        tb_url = os.getenv("ASSISTANT_TURTLEBOT_CAMERA_URL", "").strip()
        tb_index_raw = os.getenv("ASSISTANT_TURTLEBOT_CAMERA_INDEX", "1").strip()
        pc_index_raw = os.getenv("ASSISTANT_PC_CAMERA_INDEX", "0").strip()
        try:
            tb_index = int(tb_index_raw)
        except ValueError:
            tb_index = 1
        try:
            pc_index = int(pc_index_raw)
        except ValueError:
            pc_index = 0

        if tb_topic and self._try_open(f"ros:{tb_topic}", f"turtlebot-topic-{tb_topic}"):
            return

        if tb_url and self._try_open(tb_url, "turtlebot-url"):
            return

        tried_indexes: list[tuple[int, str]] = []
        for index, label in (
            (tb_index, f"turtlebot-index-{tb_index}"),
            (pc_index, f"pc-index-{pc_index}"),
            (0, "laptop-webcam"),
            (2, "pc-index-2"),
        ):
            if any(prev_index == index for prev_index, _ in tried_indexes):
                continue
            tried_indexes.append((index, label))
            if self._try_open(index, label):
                return
        raise RuntimeError("터틀봇/노트북 카메라를 모두 열지 못했습니다.")

    def run(self):
        self.is_running = True
        last_scan_time = 0.0

        try:
            self.callback(None, "INITIALIZING", "카메라 연결 중...")
            self._open_camera_with_fallback()
            self.callback(None, "INITIALIZING", f"OCR 모델 준비 중... ({self.source_name})")
            self.reader = self._load_shared_backend()
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

            display_img = frame.copy()
            h, w = display_img.shape[:2]
            rt, rb = 0, h
            rl, rr = 0, w

            if self.current_mode == "SCANNING" and not self.is_processing:
                if time.time() - last_scan_time > 1.2:
                    self.is_processing = True
                    last_scan_time = time.time()
                    roi = bgr_to_gray(display_img[rt:rb, rl:rr])
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
            results = self._read_text_with_backend(self.reader, roi)
            text = "".join(results).replace(" ", "")
            match = match_delivery_target_from_lookup(text, self._delivery_lookup)
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
