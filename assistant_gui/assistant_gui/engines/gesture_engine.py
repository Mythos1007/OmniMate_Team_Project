import math
import threading
import time
import os

import cv2
import mediapipe as mp


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
            self.hands = self.mp_hands.Hands(
                model_complexity=0,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7,
            )

        self.is_running = False
        self.last_gesture = "인식 대기 중"

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
        ring_straight = landmarks[16].y < landmarks[14].y

        if thumb_is_high and thumb_straight and index_folded and middle_folded:
            return "칭찬해주셔서 감사합니다"
        if ok_dist < 0.05 and ring_straight:
            return "OK! 복귀하겠습니다"
        return "인식 중..."

    def run(self):
        self.is_running = True
        while self.is_running:
            if self.cap is None:
                break
            ret, frame = self.cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            current_gesture = "인식 대기 중"

            if self.has_gesture_support and self.hands is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        current_gesture = self.classify_hand(hand_landmarks)
            else:
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
