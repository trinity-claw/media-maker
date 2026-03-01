from __future__ import annotations

import time
from pathlib import Path

import requests


class KieUploader:
    def __init__(
        self,
        api_key: str,
        upload_endpoint: str,
        timeout_seconds: int = 120,
        dry_run: bool = True,
    ) -> None:
        self.api_key = api_key
        self.upload_endpoint = upload_endpoint
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run

    def _extract_public_url(self, payload: dict) -> str:
        if payload.get("success") is False:
            message = payload.get("msg") or payload.get("message") or "unknown upload error"
            raise ValueError(f"Kie upload failed: {message}")
        if "code" in payload and str(payload.get("code")) not in {"200", "0"}:
            message = payload.get("msg") or payload.get("message") or "unknown upload error"
            raise ValueError(f"Kie upload failed: {message}")
        for key in ("url", "file_url", "public_url"):
            if key in payload and payload[key]:
                return str(payload[key])
        data = payload.get("data", {}) or {}
        for key in ("url", "file_url", "public_url", "fileUrl", "downloadUrl"):
            if key in data and data[key]:
                return str(data[key])
        raise ValueError("Upload response did not contain a public URL.")

    def upload_file(self, path: Path) -> str:
        if self.dry_run:
            return f"https://example.invalid/media-maker/{path.name}"
        if not self.api_key:
            raise ValueError("KIE_API_KEY is required for real upload mode.")

        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                with path.open("rb") as handle:
                    response = requests.post(
                        self.upload_endpoint,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        files={"file": (path.name, handle)},
                        data={"uploadPath": "media-maker"},
                        timeout=self.timeout_seconds,
                    )
                response.raise_for_status()
                payload = response.json() or {}
                return self._extract_public_url(payload)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < 3:
                    time.sleep(1.5 * attempt)
        raise ValueError(f"Kie upload failed after retries: {last_error}")
