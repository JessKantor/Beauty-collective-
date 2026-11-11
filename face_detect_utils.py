"""Shared face-detection helpers for database builders."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

FACE_LANDMARKER_MODEL_PATH = Path("face_landmarker.task")
FACE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
FACE_DETECT_WORKER = Path(__file__).resolve().parent / "face_detect_worker.py"
FACE_DETECT_TIMEOUT = 120
REQUEST_TIMEOUT = 30


class _LandmarkPoint:
    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


def landmarks_from_worker_payload(payload: dict[str, Any]) -> list[_LandmarkPoint]:
    landmarks: list[_LandmarkPoint] = [_LandmarkPoint(0.0, 0.0, 0.0)] * 500
    for index_str, coords in payload["landmarks"].items():
        landmarks[int(index_str)] = _LandmarkPoint(coords["x"], coords["y"], coords["z"])
    return landmarks


def ensure_face_landmarker_model() -> Path:
    if FACE_LANDMARKER_MODEL_PATH.exists():
        return FACE_LANDMARKER_MODEL_PATH

    print(f"Downloading Face Landmarker model to {FACE_LANDMARKER_MODEL_PATH}...")
    response = requests.get(FACE_LANDMARKER_MODEL_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    FACE_LANDMARKER_MODEL_PATH.write_bytes(response.content)
    print("Model download complete.\n")
    return FACE_LANDMARKER_MODEL_PATH


def detect_face_in_image_file(image_path: Path, *, artwork: bool = False) -> dict[str, Any] | None:
    ensure_face_landmarker_model()
    try:
        cmd = [sys.executable, str(FACE_DETECT_WORKER), "--image", str(image_path)]
        if artwork:
            cmd.append("--artwork")
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FACE_DETECT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("  [warn] Face detection timed out")
        return None

    stdout = (completed.stdout or "").strip()
    if not stdout:
        stderr = (completed.stderr or "").strip()
        if stderr and completed.returncode != 0:
            print(f"  [warn] Face worker exited {completed.returncode}: {stderr[:200]}")
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        print("  [warn] Face worker returned invalid JSON")
        return None
