from __future__ import annotations

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

    def upload_file(self, path: Path) -> str:
        if self.dry_run:
            return f"https://example.invalid/media-maker/{path.name}"
        if not self.api_key:
            raise ValueError("KIE_API_KEY is required for real upload mode.")

        with path.open("rb") as handle:
            response = requests.post(
                self.upload_endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (path.name, handle)},
                timeout=self.timeout_seconds,
            )
        response.raise_for_status()
        payload = response.json() or {}
        for key in ("url", "file_url", "public_url"):
            if key in payload and payload[key]:
                return str(payload[key])
        data = payload.get("data", {}) or {}
        for key in ("url", "file_url", "public_url"):
            if key in data and data[key]:
                return str(data[key])
        raise ValueError("Upload response did not contain a public URL.")
