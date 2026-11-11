#!/usr/bin/env python3
"""
Build art_database.json from a Getty Images board manifest.

Export assets from your Getty collaboration board into getty_manifest.json
(see getty_manifest.example.json), place image files or URLs, then run:

  python3 build_getty_database.py
  python3 build_getty_database.py --fresh
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests

from face_detect_utils import (
    detect_face_in_image_file,
    ensure_face_landmarker_model,
    landmarks_from_worker_payload,
)
from face_shape import classify_face_shape_detailed
from face_validation import artwork_exclusion_reason

MANIFEST_FILE = Path("getty_manifest.json")
OUTPUT_FILE = Path("art_database.json")
PARTNER_NAME = "Getty Images"
BOARD_URL = (
    "https://www.gettyimages.com/collaboration/boards/"
    "eAGAgBoofEe_WRznFnIkxw"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build art_database.json from Getty manifest.")
    parser.add_argument("--fresh", action="store_true", help="Overwrite existing database.")
    return parser.parse_args()


def load_manifest() -> list[dict[str, Any]]:
    if not MANIFEST_FILE.exists():
        print(f"Missing {MANIFEST_FILE}. Copy getty_manifest.example.json to start.")
        return []
    data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Manifest must be a JSON array.")
    return data


def download_image(url: str, session: requests.Session) -> Any:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    image_array = np.frombuffer(response.content, dtype=np.uint8)
    return cv2.imdecode(image_array, cv2.IMREAD_COLOR)


def resolve_image_path(entry: dict[str, Any], session: requests.Session) -> Path | None:
    """Return a temp or local image path ready for face detection."""
    local = (entry.get("imagePath") or "").strip()
    if local:
        path = Path(local)
        if path.exists():
            return path

    url = (entry.get("imageUrl") or "").strip()
    if not url:
        return None

    image = download_image(url, session)
    if image is None:
        return None

    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(handle.name, image)
    handle.close()
    return Path(handle.name)


def build_record(entry: dict[str, Any], face_shape: str, confidence: float, metrics: dict[str, float]) -> dict[str, Any]:
    source_url = entry.get("sourceUrl") or entry.get("gettyUrl") or ""
    if not source_url and entry.get("id"):
        source_url = f"https://www.gettyimages.com/detail/{entry['id']}"

    return {
        "id": entry.get("id") or entry.get("gettyId") or entry.get("title", "unknown"),
        "title": entry.get("title") or "",
        "artist": entry.get("artist") or entry.get("photographer") or "",
        "date": entry.get("date") or "",
        "collection": entry.get("collection") or entry.get("category") or "",
        "culture": entry.get("culture") or "",
        "imageUrl": entry.get("imageUrl") or "",
        "sourceUrl": source_url,
        "partner": PARTNER_NAME,
        "boardUrl": BOARD_URL,
        "faceShape": face_shape,
        "shapeConfidence": round(confidence, 3),
        "faceMetrics": {k: round(v, 3) for k, v in metrics.items()},
    }


def main() -> int:
    args = parse_args()
    manifest = load_manifest()
    if not manifest:
        return 1

    ensure_face_landmarker_model()
    session = requests.Session()
    session.headers.update({"User-Agent": "BeautyCollectiveICP/1.0 (educational prototype)"})

    results: list[dict[str, Any]] = []
    if not args.fresh and OUTPUT_FILE.exists():
        results = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    saved_ids = {str(r["id"]) for r in results}
    shapes: Counter[str] = Counter()

    print(f"Processing {len(manifest)} Getty manifest entries...\n")

    for index, entry in enumerate(manifest, start=1):
        entry_id = str(entry.get("id") or entry.get("gettyId") or index)
        title = (entry.get("title") or "")[:50]
        print(f"[{index}/{len(manifest)}] {entry_id} — {title!r}...", end=" ", flush=True)

        if entry_id in saved_ids and not args.fresh:
            print("skip (already saved)")
            continue

        meta_obj = {
            "title": entry.get("title"),
            "objectName": entry.get("collection"),
            "classification": entry.get("category"),
            "medium": entry.get("medium"),
            "tags": entry.get("tags"),
        }
        meta_reason = artwork_exclusion_reason(meta_obj, entry.get("imageUrl") or "")
        if meta_reason:
            print(f"skipped ({meta_reason})")
            continue

        temp_path: Path | None = None
        try:
            image_path = resolve_image_path(entry, session)
            if image_path is None:
                print("skipped (no image)")
                continue
            if str(entry.get("imageUrl") or "").startswith("http"):
                temp_path = image_path

            payload = detect_face_in_image_file(image_path, artwork=True)
            if payload is None or not payload.get("ok"):
                reason = (payload or {}).get("reason", "no_face")
                print(f"skipped ({reason})")
                continue

            landmarks = landmarks_from_worker_payload(payload)
            shape, confidence, _, metrics = classify_face_shape_detailed(
                landmarks, int(payload["width"]), int(payload["height"])
            )
            record = build_record(entry, shape, confidence, metrics)
            results.append(record)
            saved_ids.add(entry_id)
            shapes[shape] += 1
            OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"saved as {shape!r} ({confidence:.0%})")
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    print(f"\nDone. {len(results)} works in {OUTPUT_FILE}")
    print("Shapes:", dict(shapes.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
