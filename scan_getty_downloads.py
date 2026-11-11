#!/usr/bin/env python3
"""
Scan locally downloaded Getty board images and build art_database.json.

Getty blocks automated downloads (Cloudflare), so download the board in your
browser first, then run this script.

Steps:
  1. Open your collaboration board in Chrome/Safari while signed in.
  2. Select all assets → Download (or download each comp/preview).
  3. Save files into getty_images/  (filenames may include the Getty ID).
  4. Optional: add getty_images/metadata.json for titles/artists (see below).
  5. Run:

       python3 scan_getty_downloads.py
       python3 scan_getty_downloads.py --fresh

Copied, web-ready images land in assets/. The kiosk uses relative paths so
GitHub Pages can serve them without Getty CDN auth.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from build_getty_database import BOARD_URL, OUTPUT_FILE, PARTNER_NAME, build_record
from face_detect_utils import detect_face_in_image_file, ensure_face_landmarker_model, landmarks_from_worker_payload
from face_shape import classify_face_shape_detailed
from face_validation import artwork_exclusion_reason

DOWNLOADS_DIR = Path("getty_images")
ASSETS_DIR = Path("assets")
METADATA_FILE = DOWNLOADS_DIR / "metadata.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
GETTY_ID_RE = re.compile(r"(?<!\d)(\d{6,12})(?!\d)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan downloaded Getty images and build art_database.json.")
    parser.add_argument("--fresh", action="store_true", help="Rebuild database from scratch.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DOWNLOADS_DIR,
        help=f"Folder of downloaded images (default: {DOWNLOADS_DIR})",
    )
    return parser.parse_args()


def load_metadata() -> dict[str, dict[str, Any]]:
    if not METADATA_FILE.exists():
        return {}
    data = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(row.get("id") or row.get("filename", "")): row for row in data}
    if isinstance(data, dict):
        return data
    raise SystemExit("metadata.json must be a JSON object or array.")


def extract_getty_id(path: Path) -> str:
    match = GETTY_ID_RE.search(path.stem)
    if match:
        return match.group(1)
    return path.stem


def human_title(path: Path, entry: dict[str, Any]) -> str:
    if entry.get("title"):
        return str(entry["title"])
    stem = path.stem
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"\bgetty\b", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b\d{6,12}\b", "", stem).strip()
    return stem or path.stem


def image_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files = [
        p for p in sorted(folder.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS and not p.name.startswith(".")
    ]
    return files


def copy_to_assets(src: Path, record_id: str) -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ASSETS_DIR / f"{record_id}{src.suffix.lower()}"
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
    return dest


def make_entry(path: Path, meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    record_id = extract_getty_id(path)
    extra = meta.get(record_id) or meta.get(path.name) or {}
    title = human_title(path, extra)
    source_url = extra.get("sourceUrl") or extra.get("gettyUrl") or f"https://www.gettyimages.com/detail/{record_id}"
    return {
        "id": record_id,
        "title": title,
        "artist": extra.get("artist") or extra.get("photographer") or "",
        "date": extra.get("date") or "",
        "collection": extra.get("collection") or extra.get("category") or "Getty Board",
        "culture": extra.get("culture") or "",
        "category": extra.get("category") or "Portrait",
        "medium": extra.get("medium") or "Photography",
        "tags": extra.get("tags") or [],
        "imagePath": str(path),
        "sourceUrl": source_url,
    }


def main() -> int:
    args = parse_args()
    folder = args.input
    files = image_files(folder)

    if not files:
        print(f"No images found in {folder.resolve()}")
        print()
        print("Download your Getty board in the browser, then save files here:")
        print(f"  {folder.resolve()}")
        print()
        print("Board:")
        print(f"  {BOARD_URL}")
        return 1

    ensure_face_landmarker_model()
    meta = load_metadata()

    results: list[dict[str, Any]] = []
    if not args.fresh and OUTPUT_FILE.exists():
        results = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    saved_ids = {str(r["id"]) for r in results}
    shapes: Counter[str] = Counter(r["faceShape"] for r in results)

    print(f"Scanning {len(files)} images from {folder}...\n")

    for index, path in enumerate(files, start=1):
        entry = make_entry(path, meta)
        record_id = str(entry["id"])
        print(f"[{index}/{len(files)}] {path.name} (id {record_id})...", end=" ", flush=True)

        if record_id in saved_ids and not args.fresh:
            print("skip (already saved)")
            continue

        meta_obj = {
            "title": entry.get("title"),
            "objectName": entry.get("collection"),
            "classification": entry.get("category"),
            "medium": entry.get("medium"),
            "tags": entry.get("tags"),
        }
        meta_reason = artwork_exclusion_reason(meta_obj, path.name)
        if meta_reason:
            print(f"skipped ({meta_reason})")
            continue

        payload = detect_face_in_image_file(path, artwork=True)
        if payload is None or not payload.get("ok"):
            reason = (payload or {}).get("reason", "no_face")
            print(f"skipped ({reason})")
            continue

        asset_path = copy_to_assets(path, record_id)
        entry["imageUrl"] = str(asset_path).replace("\\", "/")

        landmarks = landmarks_from_worker_payload(payload)
        shape, confidence, _, metrics = classify_face_shape_detailed(
            landmarks, int(payload["width"]), int(payload["height"])
        )
        record = build_record(entry, shape, confidence, metrics)
        results.append(record)
        saved_ids.add(record_id)
        shapes[shape] += 1
        OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"saved as {shape!r} ({confidence:.0%})")

    print(f"\nDone. {len(results)} works in {OUTPUT_FILE}")
    print("Assets:", ASSETS_DIR.resolve())
    print("Shapes:", dict(shapes.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
