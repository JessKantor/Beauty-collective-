#!/usr/bin/env python3
"""
Build art_database.json from getty_portraits.csv (metadata + imageUrl).

Each row is downloaded, face-scanned, and copied into assets/ for GitHub Pages.

  python3 build_from_spreadsheet.py
  python3 build_from_spreadsheet.py --fresh
  python3 build_from_spreadsheet.py --csv my_board.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests

from build_getty_database import BOARD_URL, OUTPUT_FILE, build_record
from face_detect_utils import detect_face_in_image_file, ensure_face_landmarker_model, landmarks_from_worker_payload
from face_shape import classify_face_shape_detailed
from face_validation import artwork_exclusion_reason

DEFAULT_CSV = Path("getty_portraits.csv")
TEMPLATE_CSV = Path("getty_portraits.template.csv")
ASSETS_DIR = Path("assets")

CSV_COLUMNS = (
    "id",
    "title",
    "artist",
    "date",
    "collection",
    "culture",
    "category",
    "medium",
    "imageUrl",
    "sourceUrl",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build art_database.json from a Getty portraits CSV.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Spreadsheet file (CSV).")
    parser.add_argument("--fresh", action="store_true", help="Rebuild database from scratch.")
    parser.add_argument("--keep-remote-url", action="store_true", help="Keep Getty CDN URLs instead of local assets/.")
    return parser.parse_args()


def normalize_row(row: dict[str, str]) -> dict[str, Any]:
    lowered = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
    entry: dict[str, Any] = {}
    for key in CSV_COLUMNS:
        entry[key] = lowered.get(key.lower(), "")
    if not entry["sourceUrl"] and entry["id"]:
        entry["sourceUrl"] = f"https://www.gettyimages.com/detail/{entry['id']}"
    return entry


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        print(f"Missing {path}")
        if TEMPLATE_CSV.exists():
            print(f"Copy {TEMPLATE_CSV} → {path} or run scripts/export_getty_board.js in your browser.")
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("CSV has no header row.")
        for raw in reader:
            entry = normalize_row(raw)
            if not entry.get("imageUrl"):
                continue
            if not entry.get("id"):
                entry["id"] = entry["imageUrl"].split("/")[-2]
            rows.append(entry)
    return rows


def download_image(url: str, session: requests.Session) -> np.ndarray | None:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    image_array = np.frombuffer(response.content, dtype=np.uint8)
    return cv2.imdecode(image_array, cv2.IMREAD_COLOR)


def save_asset(image: np.ndarray, record_id: str, suffix: str = ".jpg") -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ASSETS_DIR / f"{record_id}{suffix}"
    cv2.imwrite(str(dest), image)
    return dest


def resolve_image(
    entry: dict[str, Any],
    session: requests.Session,
) -> tuple[Path | None, np.ndarray | None, Path | None]:
    """Return (path_for_detection, decoded_image, temp_path_to_delete)."""
    local = (entry.get("imagePath") or "").strip()
    if local:
        path = Path(local)
        if path.exists():
            return path, None, None

    url = (entry.get("imageUrl") or "").strip()
    if not url:
        return None, None, None

    image = download_image(url, session)
    if image is None:
        return None, None, None

    handle = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(handle.name, image)
    handle.close()
    return Path(handle.name), image, Path(handle.name)


def main() -> int:
    args = parse_args()
    manifest = load_csv(args.csv)
    if not manifest:
        return 1

    ensure_face_landmarker_model()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "BeautyCollectiveICP/1.0 (educational prototype)",
            "Referer": BOARD_URL,
        }
    )

    results: list[dict[str, Any]] = []
    if not args.fresh and OUTPUT_FILE.exists():
        results = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    saved_ids = {str(r["id"]) for r in results}
    shapes: Counter[str] = Counter(r.get("faceShape", "") for r in results if r.get("faceShape"))

    print(f"Processing {len(manifest)} rows from {args.csv}...\n")

    for index, entry in enumerate(manifest, start=1):
        entry_id = str(entry.get("id") or index)
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
            image_path, decoded, temp_path = resolve_image(entry, session)
            if image_path is None:
                print("skipped (download failed)")
                continue

            payload = detect_face_in_image_file(image_path, artwork=True)
            if payload is None or not payload.get("ok"):
                reason = (payload or {}).get("reason", "no_face")
                print(f"skipped ({reason})")
                continue

            if decoded is not None and not args.keep_remote_url:
                asset_path = save_asset(decoded, entry_id)
                entry["imageUrl"] = str(asset_path).replace("\\", "/")

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
        except requests.RequestException as exc:
            print(f"skipped (HTTP {exc})")
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    print(f"\nDone. {len(results)} works in {OUTPUT_FILE}")
    if not args.keep_remote_url:
        print("Assets:", ASSETS_DIR.resolve())
    print("Shapes:", dict(shapes.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
