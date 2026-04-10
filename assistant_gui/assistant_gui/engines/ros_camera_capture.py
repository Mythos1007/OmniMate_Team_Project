from __future__ import annotations

import threading
import time
import uuid
from typing import Optional

import cv2
import numpy as np

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CompressedImage, Image
except Exception:
    rclpy = None
    Node = object
    qos_profile_sensor_data = None
    CompressedImage = None
    Image = None


class RosCameraCapture:
    """OpenCV-like capture wrapper for ROS image topics."""

    def __init__(
        self,
        *,
        image_topic: str = "",
        compressed_topic: str = "",
    ) -> None:
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._released = False
        self._ready = False
        self._node = None

        if rclpy is None or CompressedImage is None or Image is None:
            return

        try:
            if not rclpy.ok():
                rclpy.init()
            self._node = _RosCameraNode(
                image_topic=image_topic.strip(),
                compressed_topic=compressed_topic.strip(),
                on_frame=self._on_frame,
            )
            self._ready = True
            self._spin_thread = threading.Thread(target=self._spin_loop, daemon=True)
            self._spin_thread.start()
        except Exception:
            self._node = None
            self._ready = False

    def isOpened(self) -> bool:
        return bool(self._ready and not self._released)

    def set(self, _prop_id: int, _value: float) -> bool:
        return True

    def read(self):
        if not self.isOpened():
            return False, None
        with self._frame_lock:
            if self._latest_frame is None:
                return False, None
            frame = self._latest_frame.copy()
        return True, frame

    def has_frame(self) -> bool:
        with self._frame_lock:
            return self._latest_frame is not None

    def wait_for_first_frame(self, timeout_sec: float) -> bool:
        deadline = time.monotonic() + max(0.1, float(timeout_sec))
        while time.monotonic() < deadline:
            if self.has_frame():
                return True
            time.sleep(0.03)
        return False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:
                pass
            self._node = None

    def _on_frame(self, frame: np.ndarray) -> None:
        with self._frame_lock:
            self._latest_frame = frame

    def _spin_loop(self) -> None:
        while not self._released and self._node is not None and rclpy is not None and rclpy.ok():
            try:
                rclpy.spin_once(self._node, timeout_sec=0.05)
            except Exception:
                time.sleep(0.05)


class _RosCameraNode(Node):
    def __init__(self, *, image_topic: str, compressed_topic: str, on_frame):
        super().__init__(f"assistant_gui_ros_camera_capture_{uuid.uuid4().hex[:8]}")
        self._on_frame = on_frame

        image_topics, compressed_topics = self._build_candidate_topics(
            image_topic=image_topic,
            compressed_topic=compressed_topic,
        )

        for topic in compressed_topics:
            self.create_subscription(
                CompressedImage,
                topic,
                self._on_compressed,
                qos_profile_sensor_data,
            )
        for topic in image_topics:
            self.create_subscription(
                Image,
                topic,
                self._on_raw,
                qos_profile_sensor_data,
            )

    @staticmethod
    def _build_candidate_topics(*, image_topic: str, compressed_topic: str) -> tuple[list[str], list[str]]:
        def _normalize(topic: str) -> str:
            token = str(topic or "").strip()
            if not token:
                return ""
            return token if token.startswith("/") else f"/{token}"

        raw_set: set[str] = set()
        compressed_set: set[str] = set()

        configured_raw = _normalize(image_topic)
        configured_compressed = _normalize(compressed_topic)

        if configured_raw:
            raw_set.add(configured_raw)
            compressed_set.add(f"{configured_raw.rstrip('/')}/compressed")
        if configured_compressed:
            compressed_set.add(configured_compressed)
            if configured_compressed.endswith("/compressed"):
                raw_set.add(configured_compressed[: -len("/compressed")])

        defaults_raw = (
            "/image_raw",
            "/camera/image_raw",
            "/v4l2_camera/image_raw",
            "/camera/color/image_raw",
            "/usb_cam/image_raw",
        )
        for topic in defaults_raw:
            raw_set.add(topic)
            compressed_set.add(f"{topic}/compressed")

        return sorted(raw_set), sorted(compressed_set)

    def _on_compressed(self, msg) -> None:
        try:
            np_arr = np.frombuffer(msg.data, dtype=np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if image is not None:
                self._on_frame(image)
        except Exception:
            return

    def _on_raw(self, msg) -> None:
        try:
            width = int(msg.width)
            height = int(msg.height)
            if width <= 0 or height <= 0:
                return

            encoding = str(msg.encoding).lower()
            data = np.frombuffer(msg.data, dtype=np.uint8)

            if encoding == "bgr8":
                image = data.reshape((height, width, 3))
            elif encoding == "rgb8":
                image = data.reshape((height, width, 3))
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            elif encoding in {"mono8", "8uc1"}:
                gray = data.reshape((height, width))
                image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                return

            self._on_frame(image)
        except Exception:
            return
