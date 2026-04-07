from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .face_models import BlinkState, FaceBaseState, MouthState, TempExpression


@dataclass(slots=True)
class AssetInfo:
    key: str
    requested_name: str
    resolved_name: str
    path: Path | None
    exists: bool
    fallback_used: bool
    viewbox_ok: bool | None
    warning: str


class FaceAssetRepository:
    """표정 자산 경로 조회 + 검증 메타데이터 제공."""

    # TODO(asset): 신규 에셋 팩 표준 뷰박스(512)를 유지 기능.
    EXPECTED_VIEWBOX = "0 0 512 512"

    def __init__(self, root_dir: Path | None = None, *, expected_viewbox: str | None = None) -> None:
        base = Path(__file__).resolve().parents[1]
        self._faces_dir = root_dir or (base / "assets" / "faces")
        self._expected_viewbox = expected_viewbox or self.EXPECTED_VIEWBOX

    @property
    def faces_dir(self) -> Path:
        return self._faces_dir

    @property
    def expected_viewbox(self) -> str:
        return self._expected_viewbox

    def _candidate(self, filename: str) -> Path | None:
        path = self._faces_dir / filename
        return path if path.exists() else None

    def _validate_viewbox(self, path: Path | None) -> tuple[bool | None, str]:
        if path is None:
            return None, ""
        if path.suffix.lower() != ".svg":
            return None, ""
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None, "asset-read-failed"

        marker = "viewBox="
        idx = text.find(marker)
        if idx < 0:
            return False, f"missing-viewBox(expected={self._expected_viewbox})"

        q_idx = idx + len(marker)
        if q_idx >= len(text):
            return False, f"invalid-viewBox(expected={self._expected_viewbox})"

        quote = text[q_idx]
        if quote not in {'\"', "'"}:
            return False, f"invalid-viewBox(expected={self._expected_viewbox})"

        end = text.find(quote, q_idx + 1)
        if end < 0:
            return False, f"invalid-viewBox(expected={self._expected_viewbox})"

        value = text[q_idx + 1 : end].strip()
        if value == self._expected_viewbox:
            return True, ""
        return False, f"viewBox-mismatch(found={value}, expected={self._expected_viewbox})"

    def _build_info(self, key: str, requested_name: str, candidates: list[str]) -> AssetInfo:
        requested_path = self._candidate(requested_name)
        resolved_path = requested_path
        resolved_name = requested_name
        fallback_used = False

        if resolved_path is None:
            for name in candidates[1:]:
                p = self._candidate(name)
                if p is not None:
                    resolved_path = p
                    resolved_name = name
                    fallback_used = True
                    break

        exists = resolved_path is not None
        viewbox_ok, warning = self._validate_viewbox(resolved_path)

        if not exists:
            warning = f"missing-asset(requested={requested_name})"
        elif fallback_used and not warning:
            warning = f"fallback-used({requested_name}->{resolved_name})"

        return AssetInfo(
            key=key,
            requested_name=requested_name,
            resolved_name=resolved_name,
            path=resolved_path,
            exists=exists,
            fallback_used=fallback_used,
            viewbox_ok=viewbox_ok,
            warning=warning,
        )

    def get_base_asset_info(self, state: FaceBaseState) -> AssetInfo:
        mapping = {
            FaceBaseState.IDLE: ["neutral_base.svg"],
            FaceBaseState.LISTENING: ["listening_base.svg", "neutral_base.svg"],
            FaceBaseState.THINKING: ["thinking_base.svg", "neutral_base.svg"],
            FaceBaseState.NAVIGATING: ["navigating_base.svg", "neutral_base.svg"],
            FaceBaseState.WAITING_CONFIRMATION: ["waiting_confirmation_base.svg", "neutral_base.svg"],
            FaceBaseState.CHARGING: ["charging_base.svg", "neutral_base.svg"],
            FaceBaseState.LOW_BATTERY: ["low_battery_base.svg", "neutral_base.svg"],
            FaceBaseState.ERROR: ["error_base.svg", "neutral_base.svg"],
            FaceBaseState.EMERGENCY_STOP: ["emergency_stop_base.svg", "error_base.svg", "neutral_base.svg"],
        }
        names = mapping[state]
        return self._build_info("base", names[0], names)

    def get_temp_asset_info(self, expression: TempExpression) -> AssetInfo:
        mapping = {
            TempExpression.NONE: None,
            TempExpression.HAPPY: "happy_temp.svg",
            TempExpression.GREETING: "greeting_temp.svg",
            TempExpression.APOLOGETIC: "apologetic_temp.svg",
            TempExpression.SURPRISED: "surprised_temp.svg",
        }
        filename = mapping[expression]
        if filename is None:
            return AssetInfo("temp", "<none>", "<none>", None, True, False, None, "")
        return self._build_info("temp", filename, [filename])

    def get_blink_asset_info(self, blink_state: BlinkState) -> AssetInfo:
        mapping = {
            BlinkState.OPEN: None,
            BlinkState.CLOSED_1: "blink_1.svg",
            BlinkState.CLOSED_2: "blink_2.svg",
        }
        filename = mapping[blink_state]
        if filename is None:
            return AssetInfo("blink", "<none>", "<none>", None, True, False, None, "")
        return self._build_info("blink", filename, [filename])

    def get_mouth_asset_info(self, mouth_state: MouthState) -> AssetInfo:
        mapping = {
            MouthState.IDLE: "mouth_0.svg",
            MouthState.FRAME_1: "mouth_1.svg",
            MouthState.FRAME_2: "mouth_2.svg",
            MouthState.FRAME_3: "mouth_3.svg",
        }
        return self._build_info("mouth", mapping[mouth_state], [mapping[mouth_state]])

    def get_base_asset(self, state: FaceBaseState) -> Path | None:
        return self.get_base_asset_info(state).path

    def get_temp_asset(self, expression: TempExpression) -> Path | None:
        return self.get_temp_asset_info(expression).path

    def get_blink_asset(self, blink_state: BlinkState) -> Path | None:
        return self.get_blink_asset_info(blink_state).path

    def get_mouth_asset(self, mouth_state: MouthState) -> Path | None:
        return self.get_mouth_asset_info(mouth_state).path

    def debug_asset_name(self, path: Path | None) -> str:
        return path.name if path is not None else "<none>"
