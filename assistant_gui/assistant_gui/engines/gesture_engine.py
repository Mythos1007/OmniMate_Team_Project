import math
import threading
import time
import os

import cv2
import mediapipe as mp

try:
    from assistant_gui.engines.gpu_vision import bgr_to_rgb, horizontal_flip
except ModuleNotFoundError:
    from engines.gpu_vision import bgr_to_rgb, horizontal_flip

try:
    from assistant_gui.engines.ros_camera_capture import RosCameraCapture
except ModuleNotFoundError:
    from engines.ros_camera_capture import RosCameraCapture


class GestureEngine(threading.Thread):
    """MediaPipe 기반 손 제스처 인식 스레드."""

    def __init__(self, callback_func):
        super().__init__(daemon=True)
        self.cap = None
        self.source_name = ""
        self._open_camera_with_fallback()
        self.callback = callback_func

        self.has_gesture_support = hasattr(mp, "solutions")
        self.mp_hands = None
        self.mp_drawing = None
        self.hands = None
        if self.has_gesture_support:
            self.mp_hands = mp.solutions.hands
            self.mp_drawing = mp.solutions.drawing_utils
            min_det = float(os.getenv("ASSISTANT_GESTURE_MIN_DET_CONF", "0.55") or "0.55")
            min_track = float(os.getenv("ASSISTANT_GESTURE_MIN_TRACK_CONF", "0.55") or "0.55")
            self.hands = self.mp_hands.Hands(
                model_complexity=0,
                min_detection_confidence=min_det,
                min_tracking_confidence=min_track,
            )

        self.is_running = False
        self.last_gesture = "인식 대기 중"
        self._ok_frame_count = 0
        self._ok_hold_frames = int(os.getenv("ASSISTANT_GESTURE_OK_HOLD_FRAMES", "5") or "5")

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
        raise RuntimeError("제스처 카메라를 열 수 없습니다. (turtlebot/webcam)")

    def classify_hand(self, hand_landmarks):
        landmarks = hand_landmarks.landmark

        def get_dist(p1, p2):
            return math.sqrt((landmarks[p1].x - landmarks[p2].x) ** 2 + (landmarks[p1].y - landmarks[p2].y) ** 2)

        thumb_is_high = landmarks[4].y < (landmarks[5].y - 0.05)
        thumb_straight = landmarks[4].y < landmarks[2].y
        index_folded = landmarks[8].y > landmarks[6].y
        middle_folded = landmarks[12].y > landmarks[10].y

        ok_dist = get_dist(4, 8)
        palm_span = max(get_dist(5, 17), 0.01)
        ok_ratio = ok_dist / palm_span
        middle_straight = landmarks[12].y < landmarks[10].y
        ring_straight = landmarks[16].y < landmarks[14].y
        pinky_straight = landmarks[20].y < landmarks[18].y

        if thumb_is_high and thumb_straight and index_folded and middle_folded:
            return "THUMBS_UP"
        # Use a ratio against palm span so OK can still be recognized at different distances.
        if ok_ratio < 0.42 and (middle_straight or ring_straight or pinky_straight):
            return "OK"
        return "SEARCHING"

    def run(self):
        self.is_running = True
        while self.is_running:
            if self.cap is None:
                break
            ret, frame = self.cap.read()
            if not ret:
                continue

            frame = horizontal_flip(frame)
            current_gesture = "인식 대기 중"

            if self.has_gesture_support and self.hands is not None:
                try:
                    rgb_frame = bgr_to_rgb(frame)
                    results = self.hands.process(rgb_frame)
                except Exception:
                    self._ok_frame_count = 0
                    self.last_gesture = "제스처 인식 오류 (수동 확인 버튼 사용)"
                    self.callback(frame, self.last_gesture)
                    time.sleep(0.03)
                    continue
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        detected = self.classify_hand(hand_landmarks)
                        if detected == "OK":
                            self._ok_frame_count += 1
                            if self._ok_frame_count >= self._ok_hold_frames:
                                current_gesture = "OK! 복귀하겠습니다"
                            else:
                                current_gesture = f"OK 확인 중... {self._ok_frame_count}/{self._ok_hold_frames}"
                        else:
                            self._ok_frame_count = 0
                            if detected == "THUMBS_UP":
                                current_gesture = "칭찬해주셔서 감사합니다"
                            else:
                                current_gesture = "인식 중..."
                else:
                    self._ok_frame_count = 0
                    current_gesture = "손을 카메라 중앙에 보여주세요"
            else:
                self._ok_frame_count = 0
                current_gesture = "제스처 API 미지원 (수동 확인 버튼 사용)"

            self.last_gesture = current_gesture
            self.callback(frame, self.last_gesture)
            time.sleep(0.03)

    def stop(self):
        self.is_running = False
        if self.hands is not None:
            try:
                self.hands.close()
            except Exception:
                pass
        if self.cap is not None:
            self.cap.release()
            self.cap = None
