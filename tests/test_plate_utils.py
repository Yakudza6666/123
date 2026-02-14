from pathlib import Path

from lpr import DetectionConfig, log_detections, normalize_plate


def test_normalize_plate_positive():
    assert normalize_plate(" 01 a 123 bc ") == "01A123BC"


def test_normalize_plate_with_confusable_chars():
    # OCR mistakes: O->0 and 8->B in letter position
    assert normalize_plate("O1A1238C") == "01A123BC"


def test_normalize_plate_cyrillic_equivalents():
    assert normalize_plate("01А123ВС") == "01A123BC"


def test_normalize_plate_negative():
    assert normalize_plate("HELLO123") == ""


def test_log_detections(tmp_path: Path):
    log = tmp_path / "detections.log"
    log_detections(["01A123BC"], source="unit-test", log_file=log)
    content = log.read_text(encoding="utf-8")
    assert "01A123BC" in content
    assert "unit-test" in content


def test_detection_config_clamps_values():
    cfg = DetectionConfig(frame_step=0, min_width=0, min_height=0, max_frame_errors=0)
    assert cfg.frame_step == 1
    assert cfg.min_width == 10
    assert cfg.min_height == 10
    assert cfg.max_frame_errors == 1
