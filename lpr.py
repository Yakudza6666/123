import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence

# Uzbek plate examples: 01A123BC, 70B777AA
UZ_PLATE_PATTERN = re.compile(r"\b\d{2}[A-Z]\d{3}[A-Z]{2}\b")
CYR_TO_LAT = str.maketrans({"А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K", "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X", "У": "Y"})


@dataclass
class DetectionConfig:
    frame_step: int = 8
    min_width: int = 90
    min_height: int = 25
    log_file: Path = Path("data/detections.log")
    max_frame_errors: int = 10

    def __post_init__(self) -> None:
        self.frame_step = max(1, int(self.frame_step))
        self.min_width = max(10, int(self.min_width))
        self.min_height = max(10, int(self.min_height))
        self.max_frame_errors = max(1, int(self.max_frame_errors))


def _mask_normalize(text: str) -> str:
    """Force OCR text into plate mask DD L DDD LL using confusable char mapping."""
    if len(text) != 8:
        return text

    digits_idx = {0, 1, 3, 4, 5}
    letters_idx = {2, 6, 7}
    to_digit = {"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
    to_letter = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}

    chars = list(text)
    for idx, ch in enumerate(chars):
        if idx in digits_idx:
            chars[idx] = to_digit.get(ch, ch)
        elif idx in letters_idx:
            chars[idx] = to_letter.get(ch, ch)

    return "".join(chars)


def normalize_plate(raw: str) -> str:
    text = raw.upper().translate(CYR_TO_LAT)
    text = re.sub(r"[^A-Z0-9]", "", text)
    if not text:
        return ""

    candidates = [text]
    if len(text) >= 8:
        for i in range(len(text) - 7):
            candidates.append(text[i : i + 8])

    for candidate in candidates:
        fixed = _mask_normalize(candidate)
        match = UZ_PLATE_PATTERN.search(fixed)
        if match:
            return match.group(0)
    return ""


def _prepare_ocr_variants(roi_gray):
    import cv2

    variants = []
    upscaled = cv2.resize(roi_gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    variants.append(upscaled)

    # Adaptive threshold often improves low-light/low-contrast frames.
    adaptive = cv2.adaptiveThreshold(
        upscaled,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        9,
    )
    variants.append(adaptive)

    _, otsu = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(otsu)

    return variants


def extract_plate_candidates(frame, min_width: int, min_height: int):
    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    edged = cv2.Canny(filtered, 30, 200)

    contours, _ = cv2.findContours(edged, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:25]:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approx) != 4:
            continue

        x, y, w, h = cv2.boundingRect(approx)
        ratio = w / max(h, 1)
        if w >= min_width and h >= min_height and 2.0 <= ratio <= 7.5:
            roi_gray = gray[y : y + h, x : x + w]
            for variant in _prepare_ocr_variants(roi_gray):
                yield variant


def ocr_candidates(candidates: Sequence) -> List[str]:
    import pytesseract

    found = []
    for img in candidates:
        for psm in (7, 8):
            try:
                text = pytesseract.image_to_string(
                    img,
                    config=f"--oem 1 --psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                )
            except Exception:
                continue

            plate = normalize_plate(text)
            if plate:
                found.append(plate)
                break
    return found


def log_detections(plates: Iterable[str], source: str, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as f:
        for plate in plates:
            f.write(f"{timestamp}\t{source}\t{plate}\n")


def process_video(video_path: str, config: DetectionConfig) -> List[str]:
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise RuntimeError("OpenCV не установлен. Установите зависимости из requirements.txt") from exc

    video_file = Path(video_path)
    if not video_file.exists():
        raise ValueError(f"Видео не найдено: {video_path}")

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть видео: {video_path}")

    all_found = set()
    idx = 0
    frame_errors = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            idx += 1
            if idx % config.frame_step != 0:
                continue

            try:
                candidates = list(extract_plate_candidates(frame, config.min_width, config.min_height))
                found = ocr_candidates(candidates)
                for plate in found:
                    all_found.add(plate)
            except Exception:
                frame_errors += 1
                if frame_errors >= config.max_frame_errors:
                    raise RuntimeError("Слишком много ошибок обработки кадров. Проверьте качество видео.")

        sorted_found = sorted(all_found)
        if sorted_found:
            log_detections(sorted_found, source=str(video_file), log_file=config.log_file)
        return sorted_found
    finally:
        cap.release()
