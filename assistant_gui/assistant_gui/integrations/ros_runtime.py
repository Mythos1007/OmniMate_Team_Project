from __future__ import annotations

import threading

try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    ROS_RUNTIME_AVAILABLE = True
except ImportError:
    ROS_RUNTIME_AVAILABLE = False


class SharedRosRuntime:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor: MultiThreadedExecutor | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._nodes: dict[int, object] = {}

    def add_node(self, node: object) -> bool:
        if not ROS_RUNTIME_AVAILABLE:
            return False
        with self._lock:
            self._ensure_started_locked()
            key = id(node)
            if key in self._nodes:
                return True
            assert self._executor is not None
            self._executor.add_node(node)  # type: ignore[arg-type]
            self._nodes[key] = node
        return True

    def remove_node(self, node: object) -> None:
        if not ROS_RUNTIME_AVAILABLE:
            return
        with self._lock:
            key = id(node)
            executor = self._executor
            if executor is not None and key in self._nodes:
                try:
                    executor.remove_node(node)  # type: ignore[arg-type]
                except Exception:
                    pass
                self._nodes.pop(key, None)
            try:
                node.destroy_node()  # type: ignore[attr-defined]
            except Exception:
                pass
            if not self._nodes:
                self._stop_locked()

    def _ensure_started_locked(self) -> None:
        if self._executor is not None:
            return
        if not rclpy.ok():
            rclpy.init()
        self._executor = MultiThreadedExecutor(num_threads=3)
        self._running = True
        self._thread = threading.Thread(target=self._spin_loop, daemon=True)
        self._thread.start()

    def _stop_locked(self) -> None:
        executor = self._executor
        self._executor = None
        self._thread = None
        self._running = False
        if executor is not None:
            try:
                executor.shutdown()
            except Exception:
                pass

    def _spin_loop(self) -> None:
        while True:
            with self._lock:
                executor = self._executor
                running = self._running
            if not running or executor is None or not rclpy.ok():
                return
            try:
                executor.spin_once(timeout_sec=0.1)
            except Exception as exc:
                print(f"[SharedRosRuntime] spin error: {exc}")
                with self._lock:
                    self._stop_locked()
                return


_SHARED_RUNTIME = SharedRosRuntime()


def get_shared_ros_runtime() -> SharedRosRuntime:
    return _SHARED_RUNTIME