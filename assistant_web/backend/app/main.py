from __future__ import annotations

import asyncio
import ast
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .config import load_settings
from .ros_bridge import RosBridge
from .schemas import (
    AlarmToggleRequest,
    AlarmUpsertRequest,
    CommandRequest,
    CommandResponse,
    HealthResponse,
    MedicationToggleRequest,
    MedicationUpsertRequest,
    NavigateClickRequest,
    ScheduleUpsertRequest,
    StateResponse,
    WeatherResponse,
)
from .weather_service import WeatherService


settings = load_settings()
ros_bridge = RosBridge()
weather = WeatherService(lat=settings.lat, lon=settings.lon)

app = FastAPI(title="OmniMate Web Control")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
GUI_PACKAGE_DIR = Path(__file__).resolve().parents[3] / "assistant_gui" / "assistant_gui"
GUI_ASSETS_DIR = GUI_PACKAGE_DIR / "assets"
FACE_ASSETS_DIR = GUI_ASSETS_DIR / "faces"
SCHEDULES_PATH = GUI_PACKAGE_DIR / "schedules.json"
ALARMS_PATH = GUI_PACKAGE_DIR / "alarms.json"
MEDICATIONS_PATH = GUI_PACKAGE_DIR / "medications.json"
DATA_LOCK = Lock()

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
if GUI_ASSETS_DIR.exists():
    app.mount("/gui-assets", StaticFiles(directory=GUI_ASSETS_DIR), name="gui-assets")


@app.on_event("startup")
async def _on_startup() -> None:
    ros_bridge.start()


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    ros_bridge.stop()


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


def _resolve_map_image_path() -> Path:
    env_raw = os.getenv("ASSISTANT_MAP_IMAGE_PATH", "").strip()
    if env_raw:
        env_path = Path(env_raw).expanduser()
        if env_path.exists() and env_path.is_file():
            return env_path

    candidates = [
        GUI_PACKAGE_DIR / "map_0330_7clean.png",
        GUI_PACKAGE_DIR / "map_0330_7claen.png",
        GUI_PACKAGE_DIR / "map_0330_7.pgm",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError("No map image found. Set ASSISTANT_MAP_IMAGE_PATH.")


def _resolve_map_yaml_path() -> Path | None:
    env_yaml = os.getenv("ASSISTANT_MAP_YAML_PATH", "").strip()
    if env_yaml:
        env_path = Path(env_yaml).expanduser()
        if env_path.exists() and env_path.is_file():
            return env_path

    candidate = GUI_PACKAGE_DIR / "map_0330_7.yaml"
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        width, height = image.size
    return int(width), int(height)


def _load_map_metadata() -> dict[str, Any]:
    image_path = _resolve_map_image_path()
    display_width, display_height = _image_size(image_path)

    resolution = 0.05
    origin_x = -10.0
    origin_y = -10.0
    reference_width = display_width
    reference_height = display_height

    yaml_path = _resolve_map_yaml_path()
    if yaml_path is not None:
        image_name = ""
        try:
            for raw in yaml_path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "image":
                    image_name = value.strip().strip('"\'')
                elif key == "resolution":
                    resolution = float(value)
                elif key == "origin":
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, (list, tuple)) and len(parsed) >= 2:
                        origin_x = float(parsed[0])
                        origin_y = float(parsed[1])
        except Exception:
            pass

        if image_name:
            reference_path = (yaml_path.parent / image_name).resolve()
            if reference_path.exists() and reference_path.is_file():
                reference_width, reference_height = _image_size(reference_path)

    default_rotation = "0" if image_path.suffix.lower() == ".pgm" else "-26"
    rotation_deg = float(os.getenv("ASSISTANT_COORD_ROT_DEG", default_rotation))

    return {
        "image_url": "/api/map/image",
        "label": "YAML 좌표 기반 지도",
        "resolution": resolution,
        "origin_x": origin_x,
        "origin_y": origin_y,
        "rotation_deg": rotation_deg,
        "display_width": display_width,
        "display_height": display_height,
        "reference_width": reference_width,
        "reference_height": reference_height,
    }


def _schedule_data() -> dict[str, list[dict[str, str]]]:
    loaded = _read_json(SCHEDULES_PATH, {})
    return loaded if isinstance(loaded, dict) else {}


def _alarm_data() -> list[dict[str, Any]]:
    loaded = _read_json(ALARMS_PATH, [])
    return loaded if isinstance(loaded, list) else []


def _medication_data() -> dict[str, Any]:
    loaded = _read_json(MEDICATIONS_PATH, {"last_run_date": "", "meds": []})
    if isinstance(loaded, list):
        return {"last_run_date": "", "meds": loaded}
    if not isinstance(loaded, dict):
        return {"last_run_date": "", "meds": []}
    meds = loaded.get("meds", [])
    return {
        "last_run_date": str(loaded.get("last_run_date", "")),
        "meds": meds if isinstance(meds, list) else [],
    }


def _face_asset_names() -> list[str]:
    if not FACE_ASSETS_DIR.exists():
        return []
    return sorted(path.name for path in FACE_ASSETS_DIR.glob("*.svg"))


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/map")
async def map_meta() -> dict[str, Any]:
    try:
        return _load_map_metadata()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/map/image")
async def map_image() -> FileResponse:
    try:
        path = _resolve_map_image_path()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    snap = ros_bridge.get_snapshot()
    return HealthResponse(ok=True, ros_available=bool(snap.get("ros_available", False)))


@app.get("/api/state", response_model=StateResponse)
async def state() -> StateResponse:
    return StateResponse(**ros_bridge.get_snapshot())


@app.get("/api/weather", response_model=WeatherResponse)
async def weather_now() -> WeatherResponse:
    temp, desc, icon = weather.get_now()
    return WeatherResponse(temperature_c=temp, description=desc, icon=icon)


@app.get("/api/gui-data")
async def gui_data() -> dict[str, Any]:
    return {
        "theme": "light",
        "quick_destinations": ["로비", "회의실 A", "탕비실"],
        "menu": [
            {"label": "📅 일정", "page": "schedule"},
            {"label": "⏰ 알람", "page": "alarm"},
            {"label": "💊 복약 확인", "page": "medication"},
            {"label": "✉️ 우편 전달", "page": "mail"},
            {"label": "⚙️ 설정", "page": "settings"},
            {"label": "🎤 음성 테스트", "page": "voice"},
        ],
        "schedules": _schedule_data(),
        "alarms": _alarm_data(),
        "medications": _medication_data(),
        "face_assets": _face_asset_names(),
    }


@app.post("/api/command", response_model=CommandResponse)
async def post_command(payload: CommandRequest) -> CommandResponse:
    ok, detail = ros_bridge.publish_gui_command(payload.text.strip())
    return CommandResponse(accepted=ok, detail=detail)


@app.post("/api/manual-wake", response_model=CommandResponse)
async def manual_wake() -> CommandResponse:
    ok, detail = ros_bridge.publish_manual_wake()
    return CommandResponse(accepted=ok, detail=detail)


@app.post("/api/navigate/click", response_model=CommandResponse)
async def navigate_click(payload: NavigateClickRequest) -> CommandResponse:
    ok, detail = ros_bridge.publish_navigate_xy(payload.x_m, payload.y_m)
    return CommandResponse(accepted=ok, detail=detail)


@app.get("/api/schedules")
async def get_schedules() -> dict[str, list[dict[str, str]]]:
    return _schedule_data()


@app.post("/api/schedules")
async def create_schedule(payload: ScheduleUpsertRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _schedule_data()
        data.setdefault(payload.date, [])
        data[payload.date].append({
            "time": payload.time,
            "todo": payload.todo,
            "place": payload.place,
        })
        _write_json(SCHEDULES_PATH, data)
    return {"ok": True, "schedules": data}


@app.put("/api/schedules/{date_str}/{index}")
async def update_schedule(date_str: str, index: int, payload: ScheduleUpsertRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _schedule_data()
        source_items = data.get(date_str, [])
        if not (0 <= index < len(source_items)):
            raise HTTPException(status_code=404, detail="Schedule item not found")

        moved = date_str != payload.date
        item = {"time": payload.time, "todo": payload.todo, "place": payload.place}
        if moved:
            del source_items[index]
            if not source_items:
                data.pop(date_str, None)
            data.setdefault(payload.date, []).append(item)
        else:
            source_items[index] = item
        _write_json(SCHEDULES_PATH, data)
    return {"ok": True, "schedules": data}


@app.delete("/api/schedules/{date_str}/{index}")
async def delete_schedule(date_str: str, index: int) -> Response:
    with DATA_LOCK:
        data = _schedule_data()
        items = data.get(date_str, [])
        if not (0 <= index < len(items)):
            raise HTTPException(status_code=404, detail="Schedule item not found")
        del items[index]
        if not items:
            data.pop(date_str, None)
        _write_json(SCHEDULES_PATH, data)
    return Response(status_code=204)


@app.get("/api/alarms")
async def get_alarms() -> list[dict[str, Any]]:
    return _alarm_data()


@app.post("/api/alarms")
async def create_alarm(payload: AlarmUpsertRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _alarm_data()
        data.append(payload.model_dump())
        _write_json(ALARMS_PATH, data)
    return {"ok": True, "alarms": data}


@app.put("/api/alarms/{index}")
async def update_alarm(index: int, payload: AlarmUpsertRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _alarm_data()
        if not (0 <= index < len(data)):
            raise HTTPException(status_code=404, detail="Alarm not found")
        data[index] = payload.model_dump()
        _write_json(ALARMS_PATH, data)
    return {"ok": True, "alarms": data}


@app.post("/api/alarms/{index}/toggle")
async def toggle_alarm(index: int, payload: AlarmToggleRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _alarm_data()
        if not (0 <= index < len(data)):
            raise HTTPException(status_code=404, detail="Alarm not found")
        data[index]["active"] = bool(payload.active)
        _write_json(ALARMS_PATH, data)
    return {"ok": True, "alarms": data}


@app.delete("/api/alarms/{index}")
async def delete_alarm(index: int) -> Response:
    with DATA_LOCK:
        data = _alarm_data()
        if not (0 <= index < len(data)):
            raise HTTPException(status_code=404, detail="Alarm not found")
        del data[index]
        _write_json(ALARMS_PATH, data)
    return Response(status_code=204)


@app.get("/api/medications")
async def get_medications() -> dict[str, Any]:
    return _medication_data()


@app.post("/api/medications")
async def create_medication(payload: MedicationUpsertRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _medication_data()
        meds = data["meds"]
        meds.append(payload.model_dump())
        meds.sort(key=lambda item: item.get("time", "00:00"))
        _write_json(MEDICATIONS_PATH, data)
    return {"ok": True, "medications": data}


@app.put("/api/medications/{index}")
async def update_medication(index: int, payload: MedicationUpsertRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _medication_data()
        meds = data["meds"]
        if not (0 <= index < len(meds)):
            raise HTTPException(status_code=404, detail="Medication not found")
        meds[index] = payload.model_dump()
        meds.sort(key=lambda item: item.get("time", "00:00"))
        _write_json(MEDICATIONS_PATH, data)
    return {"ok": True, "medications": data}


@app.post("/api/medications/{index}/toggle")
async def toggle_medication(index: int, payload: MedicationToggleRequest) -> dict[str, Any]:
    with DATA_LOCK:
        data = _medication_data()
        meds = data["meds"]
        if not (0 <= index < len(meds)):
            raise HTTPException(status_code=404, detail="Medication not found")
        meds[index]["active"] = bool(payload.active)
        _write_json(MEDICATIONS_PATH, data)
    return {"ok": True, "medications": data}


@app.delete("/api/medications/{index}")
async def delete_medication(index: int) -> Response:
    with DATA_LOCK:
        data = _medication_data()
        meds = data["meds"]
        if not (0 <= index < len(meds)):
            raise HTTPException(status_code=404, detail="Medication not found")
        del meds[index]
        _write_json(MEDICATIONS_PATH, data)
    return Response(status_code=204)


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "state", "data": ros_bridge.get_snapshot()})
            await asyncio.sleep(settings.ws_push_interval_sec)
    except WebSocketDisconnect:
        return
