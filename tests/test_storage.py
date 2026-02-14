import json

import storage


def test_add_camera_updates_by_stream_url(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "CAMERA_DB", tmp_path / "cameras.json")

    storage.add_camera("Gate 1", "rtsp://camera-1", True)
    storage.add_camera("Gate 1 updated", "rtsp://camera-1", False)

    cams = storage.load_cameras()
    assert len(cams) == 1
    assert cams[0]["name"] == "Gate 1 updated"
    assert cams[0]["enabled"] is False


def test_load_cameras_recovers_from_broken_json(tmp_path, monkeypatch):
    db = tmp_path / "cameras.json"
    monkeypatch.setattr(storage, "CAMERA_DB", db)

    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text("{broken", encoding="utf-8")

    assert storage.load_cameras() == []
    assert (tmp_path / "cameras.broken.json").exists()


def test_save_cameras_writes_json(tmp_path, monkeypatch):
    db = tmp_path / "cameras.json"
    monkeypatch.setattr(storage, "CAMERA_DB", db)

    storage.save_cameras([{"name": "Cam", "stream_url": "rtsp://1", "enabled": True}])
    data = json.loads(db.read_text(encoding="utf-8"))
    assert data[0]["name"] == "Cam"
