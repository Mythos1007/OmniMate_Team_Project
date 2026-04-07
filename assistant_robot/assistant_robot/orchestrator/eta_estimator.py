from __future__ import annotations


class ETAEstimator:
    def estimate_charge_completion_minutes(self, *, battery_level: float, target_level: float = 95.0) -> int:
        if battery_level >= target_level:
            return 0
        remaining = max(0.0, target_level - battery_level)
        return int(round(remaining * 1.2))
