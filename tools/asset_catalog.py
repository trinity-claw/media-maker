from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.config import AppSettings
from tools.utils import ensure_dir, now_utc_slug, write_json

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FRAME_CODE_PATTERN = re.compile(r"#\s*(\d+(?:\.\d+)?)")


def _looks_like_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _extract_frame_code(name: str) -> str | None:
    match = FRAME_CODE_PATTERN.search(name)
    if match:
        return match.group(1)
    fallback = re.search(r"\b(\d+(?:\.\d+)?)\b", name)
    if fallback:
        return fallback.group(1)
    return None


def _clean_label(filename_stem: str) -> str:
    text = re.sub(r"^#\s*\d+(?:\.\d+)?", "", filename_stem).strip(" -_")
    text = re.sub(r"\b(front|diagonal|angle|cm|sm)\b", "", text, flags=re.IGNORECASE).strip(" -_")
    return text or filename_stem


def _scan_kind(root: Path, kind: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not _looks_like_image(path):
            continue
        code = _extract_frame_code(path.stem)
        rows.append(
            {
                "kind": kind,
                "frame_code": code,
                "label": _clean_label(path.stem),
                "path": str(path),
                "filename": path.name,
            }
        )
    return rows


def build_asset_catalog(settings: AppSettings) -> dict[str, Any]:
    roots = {
        "raw": settings.assets.raw_frames_root,
        "mockup_angle": settings.assets.mockup_angles_root,
        "mockup_front": settings.assets.mockup_front_root,
        "environment": settings.assets.environments_root,
    }
    all_rows: list[dict[str, Any]] = []
    for kind, root in roots.items():
        all_rows.extend(_scan_kind(root=root, kind=kind))

    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "frame_code": None,
            "labels": set(),
            "assets": {"raw": [], "mockup_angle": [], "mockup_front": [], "environment": []},
        }
    )
    unknown_rows: list[dict[str, Any]] = []
    for row in all_rows:
        frame_code = row.get("frame_code")
        if not frame_code:
            unknown_rows.append(row)
            continue
        bucket = grouped[frame_code]
        bucket["frame_code"] = frame_code
        if row.get("label"):
            bucket["labels"].add(row["label"])
        bucket["assets"][row["kind"]].append(row["path"])

    frames: dict[str, Any] = {}
    for code, data in grouped.items():
        labels = sorted(data["labels"])
        frames[code] = {
            "frame_code": code,
            "preferred_label": labels[0] if labels else f"Quadro #{code}",
            "labels": labels,
            "assets": data["assets"],
        }

    catalog = {
        "generated_at_utc": now_utc_slug(),
        "roots": {key: str(value) for key, value in roots.items()},
        "totals": {
            "all_assets": len(all_rows),
            "mapped_assets": len(all_rows) - len(unknown_rows),
            "unknown_assets": len(unknown_rows),
            "frames": len(frames),
        },
        "frames": frames,
        "unknown_assets": unknown_rows[:500],
    }
    return catalog


def save_asset_catalog(catalog: dict[str, Any], output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    write_json(output_path, catalog)
    return output_path


def load_asset_catalog(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def pick_reference_files_for_frame(
    catalog: dict[str, Any],
    frame_code: str,
    *,
    max_files: int = 3,
) -> list[str]:
    frame = catalog.get("frames", {}).get(frame_code)
    if not frame:
        return []
    assets = frame.get("assets", {})
    ordered: list[str] = []
    for kind in ("mockup_front", "mockup_angle", "raw", "environment"):
        ordered.extend(list(assets.get(kind, [])))
    deduped: list[str] = []
    seen: set[str] = set()
    for item in ordered:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
        if len(deduped) >= max_files:
            break
    return deduped
