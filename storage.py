import json
from pathlib import Path
from typing import Any, Dict, List

CAMERA_DB = Path("data/cameras.json")


def _normalize_camera(name: str, stream_url: str, enabled: bool = True) -> Dict[str, Any]:
    return {
        "name": name.strip(),
        "stream_url": stream_url.strip(),
        "enabled": bool(enabled),
    }


def load_cameras() -> List[Dict[str, Any]]:
    if not CAMERA_DB.exists():
        return []

    try:
        with CAMERA_DB.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        broken = CAMERA_DB.with_suffix(".broken.json")
        CAMERA_DB.replace(broken)
        return []

    if not isinstance(data, list):
        return []

    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        stream_url = str(item.get("stream_url", "")).strip()
        enabled = bool(item.get("enabled", True))
        if name and stream_url:
            cleaned.append(_normalize_camera(name, stream_url, enabled))
    return cleaned


def save_cameras(cameras: List[Dict[str, Any]]) -> None:
    CAMERA_DB.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = CAMERA_DB.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(cameras, f, ensure_ascii=False, indent=2)
    tmp_path.replace(CAMERA_DB)


def add_camera(name: str, stream_url: str, enabled: bool = True) -> None:
    payload = _normalize_camera(name, stream_url, enabled)
    if not payload["name"] or not payload["stream_url"]:
        return

    cameras = load_cameras()
    for idx, cam in enumerate(cameras):
        if cam.get("stream_url") == payload["stream_url"]:
            cameras[idx] = payload
            save_cameras(cameras)
            return

    cameras.append(payload)
    save_cameras(cameras)
