from __future__ import annotations

from datetime import datetime

from std_msgs.msg import String

import rclpy
from rclpy.node import Node

from assistant_robot.constants import ASSISTANT_COMMAND_TOPIC
from assistant_robot.services.runtime_data_service import RuntimeDataService
from assistant_robot.services.scheduled_mission_catalog import ScheduledMissionCatalog


class SchedulerNode(Node):
    def __init__(self) -> None:
        super().__init__("scheduler_node")
        self._publisher = self.create_publisher(String, ASSISTANT_COMMAND_TOPIC, 10)
        self._scheduled_catalog = ScheduledMissionCatalog()
        self._runtime_data = RuntimeDataService()
        self._plus_alarms = self._scheduled_catalog.load_entries()
        self._emitted_keys: set[str] = set()
        self.create_timer(1.0, self._tick)
        self.get_logger().info(
            f"Scheduler node ready. loaded_scheduled_missions={len(self._plus_alarms)}"
        )

    def _tick(self) -> None:
        now = datetime.now()
        now_str = now.strftime("%H:%M")
        today_key = now.strftime("%Y-%m-%d")

        for alarm in self._plus_alarms:
            alarm_time = str(alarm.get("time", "")).strip()
            target_place = str(alarm.get("target_place", "")).strip()
            label = str(alarm.get("name", target_place or "scheduled")).strip()
            announcement = str(alarm.get("text", "")).strip()
            if not alarm_time or not target_place or alarm_time != now_str:
                continue

            dedupe_key = f"{today_key}|{alarm_time}|{label}|{target_place}|{announcement}"
            if dedupe_key in self._emitted_keys:
                continue

            mission_type = "medication" if ("약" in label or "약" in announcement or "복약" in announcement) else "alarm"
            scheduler_text = f"[SCHED]|{mission_type}|{label}|{target_place}|{announcement}"
            self._publisher.publish(String(data=scheduler_text))
            self._emitted_keys.add(dedupe_key)
            self.get_logger().info(f"Published scheduled mission: {scheduler_text}")

        for runtime_entry in self._runtime_data.iter_due_runtime_missions(now=now):
            dedupe_key = f"{today_key}|{now_str}|{runtime_entry.mission_type}|{runtime_entry.label}|{runtime_entry.target_location}|{runtime_entry.announcement_text}"
            if dedupe_key in self._emitted_keys:
                continue

            scheduler_text = (
                f"[SCHED]|{runtime_entry.mission_type}|{runtime_entry.label}|"
                f"{runtime_entry.target_location}|{runtime_entry.announcement_text}"
            )
            self._publisher.publish(String(data=scheduler_text))
            self._emitted_keys.add(dedupe_key)
            self.get_logger().info(f"Published runtime mission: {scheduler_text}")

        self._emitted_keys = {
            item for item in self._emitted_keys if item.startswith(today_key)
        }


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = SchedulerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
