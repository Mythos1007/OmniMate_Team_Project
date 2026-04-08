from __future__ import annotations

import os
import pickle
import time
from pathlib import Path

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, String

try:
    import cv2
    import numpy as np
    from deepface import DeepFace
except Exception as exc:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None
    DeepFace = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class PersonRecognitionNode(Node):
    def __init__(self) -> None:
        super().__init__('person_recognition_node')

        workspace_root = Path(__file__).resolve().parents[4]
        default_db_path = str(workspace_root / 'plus' / 'face_db.pkl')
        default_name_map = '{"1": "기현(남)", "2": "기현(여)", "3": "희정"}'

        self.declare_parameter('camera_topic', '/image_raw/compressed')
        self.declare_parameter('recognized_person_topic', '/assistant/person_recognized')
        self.declare_parameter('enabled_topic', '/assistant/person_greeting/enabled')
        self.declare_parameter('status_topic', '/assistant/status_text')
        self.declare_parameter('face_db_path', default_db_path)
        self.declare_parameter('name_map_json', default_name_map)
        self.declare_parameter('recognition_interval_sec', 1.2)
        self.declare_parameter('publish_cooldown_sec', 12.0)
        self.declare_parameter('distance_threshold', 0.42)
        self.declare_parameter('enabled', False)

        self._enabled = bool(self.get_parameter('enabled').value)
        self._recognition_interval_sec = float(self.get_parameter('recognition_interval_sec').value)
        self._publish_cooldown_sec = float(self.get_parameter('publish_cooldown_sec').value)
        self._distance_threshold = float(self.get_parameter('distance_threshold').value)
        self._last_recognition_at = 0.0
        self._last_published_at: dict[str, float] = {}
        self._db: list[dict[str, object]] = []
        self._name_map = self._parse_name_map(str(self.get_parameter('name_map_json').value))
        self._face_detector = None

        recognized_topic = str(self.get_parameter('recognized_person_topic').value)
        status_topic = str(self.get_parameter('status_topic').value)
        camera_topic = str(self.get_parameter('camera_topic').value)
        enabled_topic = str(self.get_parameter('enabled_topic').value)

        self._recognized_publisher = self.create_publisher(String, recognized_topic, 10)
        self._status_publisher = self.create_publisher(String, status_topic, 10)
        self.create_subscription(Bool, enabled_topic, self._on_enabled_changed, 10)

        if not self._initialize_backend():
            return

        self.create_subscription(CompressedImage, camera_topic, self._on_image, 10)
        self.get_logger().info(f'Person recognition node ready. enabled={self._enabled} db={self._db_path}')

    def _initialize_backend(self) -> bool:
        if cv2 is None or np is None or DeepFace is None:
            self._status_publisher.publish(String(data=f'사람 인식 비활성: {_IMPORT_ERROR}'))
            self.get_logger().warn(f'Person recognition backend unavailable: {_IMPORT_ERROR}')
            return False

        db_path = Path(str(self.get_parameter('face_db_path').value)).expanduser()
        if not db_path.exists():
            self._status_publisher.publish(String(data=f'사람 인식 DB 없음: {db_path}'))
            self.get_logger().warn(f'Face DB not found: {db_path}')
            return False

        try:
            with db_path.open('rb') as handle:
                self._db = pickle.load(handle)
        except Exception as exc:
            self._status_publisher.publish(String(data=f'사람 인식 DB 로드 실패: {exc}'))
            self.get_logger().warn(f'Failed to load face DB: {exc}')
            return False

        cascade_path = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
        self._face_detector = cv2.CascadeClassifier(str(cascade_path))
        self._db_path = str(db_path)
        return True

    def _on_enabled_changed(self, message: Bool) -> None:
        self._enabled = bool(message.data)

    def _on_image(self, message: CompressedImage) -> None:
        if not self._enabled or self._face_detector is None or np is None:
            return

        now = time.monotonic()
        if now - self._last_recognition_at < self._recognition_interval_sec:
            return
        self._last_recognition_at = now

        frame = cv2.imdecode(np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))
        for (x, y, w, h) in faces:
            face_roi = frame[y:y + h, x:x + w]
            name = self._recognize_face(face_roi)
            if not name:
                continue
            last_published = self._last_published_at.get(name, 0.0)
            if now - last_published < self._publish_cooldown_sec:
                continue
            self._last_published_at[name] = now
            self._recognized_publisher.publish(String(data=name))
            self._status_publisher.publish(String(data=f'등록 인물 인식: {name}'))
            self.get_logger().info(f'Recognized registered person: {name}')
            return

    def _recognize_face(self, face_img) -> str | None:
        try:
            face = cv2.resize(face_img, (224, 224))
            representations = DeepFace.represent(
                img_path=face,
                model_name='VGG-Face',
                detector_backend='skip',
                enforce_detection=False,
            )
            vector = np.array(representations[0]['embedding'])
        except Exception:
            return None

        best_distance = 1.0
        best_identity = ''
        for item in self._db:
            embedding = np.array(item.get('embedding', []))
            if embedding.size == 0:
                continue
            distance = 1 - float(np.dot(vector, embedding) / ((np.linalg.norm(vector) * np.linalg.norm(embedding)) + 1e-7))
            if distance < best_distance:
                best_distance = distance
                best_identity = str(item.get('identity', ''))

        if best_distance >= self._distance_threshold or not best_identity:
            return None

        return self._resolve_user_name(best_identity)

    def _resolve_user_name(self, identity: str) -> str:
        basename = os.path.basename(identity)
        parts = basename.split('.')
        if len(parts) >= 2 and parts[1] in self._name_map:
            return self._name_map[parts[1]]
        stem = Path(basename).stem
        return self._name_map.get(stem, stem or '등록 사용자')

    @staticmethod
    def _parse_name_map(raw_value: str) -> dict[str, str]:
        try:
            import json

            data = json.loads(raw_value)
            return {str(key): str(value) for key, value in dict(data).items()}
        except Exception:
            return {}


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = PersonRecognitionNode()
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
