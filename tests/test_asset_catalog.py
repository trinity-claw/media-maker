from pathlib import Path

from tools.asset_catalog import _extract_frame_code, build_asset_catalog, pick_reference_files_for_frame
from tools.config import AppSettings


def test_extract_frame_code_patterns() -> None:
    assert _extract_frame_code("#12 Solar System - Front") == "12"
    assert _extract_frame_code("#2.1 - Front") == "2.1"
    assert _extract_frame_code("Frame 45 Example") == "45"


def test_build_catalog_and_pick_reference(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    front = tmp_path / "front"
    angle = tmp_path / "angle"
    env = tmp_path / "env"
    for root in (raw, front, angle, env):
        root.mkdir(parents=True, exist_ok=True)

    (front / "#12 Solar System - Front.jpg").write_bytes(b"x")
    (angle / "#12 - Diagonal.jpg").write_bytes(b"x")
    (raw / "#12 Solar System.jpg").write_bytes(b"x")
    (env / "#12 CM - 1.jpg").write_bytes(b"x")

    settings = AppSettings()
    settings.assets.raw_frames_root = raw
    settings.assets.mockup_front_root = front
    settings.assets.mockup_angles_root = angle
    settings.assets.environments_root = env

    catalog = build_asset_catalog(settings=settings)
    assert catalog["totals"]["frames"] == 1
    refs = pick_reference_files_for_frame(catalog=catalog, frame_code="12", max_files=3)
    assert len(refs) == 3
