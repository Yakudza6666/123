from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from lpr import DetectionConfig, process_video
from storage import add_camera, load_cameras

app = Flask(__name__)


LOG_PATH = Path("data/detections.log")


def _read_tail(log_path: Path, max_lines: int = 20):
    if not log_path.exists():
        return []
    try:
        return log_path.read_text(encoding="utf-8").splitlines()[-max_lines:]
    except OSError:
        return []


@app.get("/")
def index():
    return render_template(
        "index.html",
        cameras=load_cameras(),
        lines=reversed(_read_tail(LOG_PATH)),
        result=None,
        error=None,
    )


@app.post("/camera")
def create_camera():
    name = request.form.get("name", "").strip()
    stream_url = request.form.get("stream_url", "").strip()
    enabled = request.form.get("enabled") == "on"

    if name and stream_url:
        add_camera(name=name, stream_url=stream_url, enabled=enabled)

    return redirect(url_for("index"))


@app.post("/test-video")
def test_video():
    video_path = request.form.get("video_path", "").strip()

    try:
        frame_step = int(request.form.get("frame_step", 8) or 8)
    except ValueError:
        frame_step = 8

    cameras = load_cameras()
    lines = _read_tail(LOG_PATH)

    if not video_path:
        return render_template(
            "index.html",
            cameras=cameras,
            lines=reversed(lines),
            result=None,
            error="Укажите путь к видео.",
        )

    try:
        config = DetectionConfig(frame_step=frame_step)
        result = process_video(video_path, config)
        lines = _read_tail(LOG_PATH)
        return render_template(
            "index.html",
            cameras=cameras,
            lines=reversed(lines),
            result=result,
            error=None,
        )
    except Exception as exc:
        return render_template(
            "index.html",
            cameras=cameras,
            lines=reversed(lines),
            result=None,
            error=str(exc),
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
