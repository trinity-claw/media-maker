from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from tools.utils import chunked


@dataclass
class AirtableCredentials:
    api_key: str
    base_id: str


def build_content_table_definition(table_name: str = "Content") -> dict[str, Any]:
    return {
        "name": table_name,
        "fields": [
            {"name": "Ad Name", "type": "singleLineText"},
            {"name": "Product", "type": "singleLineText"},
            {"name": "Reference Images", "type": "multipleAttachments"},
            {"name": "Image Prompt", "type": "multilineText"},
            {"name": "Image Model", "type": "singleSelect", "options": {"choices": [{"name": "nano-banana-2"}, {"name": "gemini"}]}},
            {
                "name": "Image Status",
                "type": "singleSelect",
                "options": {"choices": [{"name": "Pending"}, {"name": "Generated"}, {"name": "Approved"}, {"name": "Rejected"}]},
            },
            {"name": "Generated Image", "type": "multipleAttachments"},
            {"name": "Video Prompt", "type": "multilineText"},
            {"name": "Video Model", "type": "singleSelect", "options": {"choices": [{"name": "veo-3.1"}, {"name": "kie-video"}]}},
            {
                "name": "Video Status",
                "type": "singleSelect",
                "options": {"choices": [{"name": "Pending"}, {"name": "Generated"}, {"name": "Approved"}, {"name": "Rejected"}]},
            },
            {"name": "Generated Video", "type": "multipleAttachments"},
            {"name": "Prompt JSON", "type": "multilineText"},
            {
                "name": "Prompt Schema",
                "type": "singleSelect",
                "options": {"choices": [{"name": "dense"}, {"name": "deep_grid"}, {"name": "hybrid"}]},
            },
            {
                "name": "Provider Used",
                "type": "singleSelect",
                "options": {"choices": [{"name": "kie"}, {"name": "google"}]},
            },
            {"name": "Estimated Cost", "type": "number", "options": {"precision": 2}},
            {"name": "Actual Cost", "type": "number", "options": {"precision": 2}},
            {"name": "Batch ID", "type": "singleLineText"},
            {"name": "Generation Error", "type": "multilineText"},
            {"name": "Convexe Insight Source", "type": "singleLineText"},
            {"name": "Cloud Asset Path", "type": "singleLineText"},
        ],
    }


class AirtableClient:
    def __init__(
        self,
        credentials: AirtableCredentials,
        table_name: str = "Content",
        timeout_seconds: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        self.credentials = credentials
        self.table_name = table_name
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.credentials.api_key}",
            "Content-Type": "application/json",
        }

    def _meta_url(self, suffix: str = "") -> str:
        base = f"https://api.airtable.com/v0/meta/bases/{self.credentials.base_id}"
        return f"{base}{suffix}"

    def _data_url(self) -> str:
        table_ref = quote(self.table_name, safe="")
        return f"https://api.airtable.com/v0/{self.credentials.base_id}/{table_ref}"

    def list_tables(self) -> list[dict[str, Any]]:
        response = self.session.get(
            self._meta_url("/tables"),
            headers=self._headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json() or {}
        return list(payload.get("tables", []))

    def setup_content_table(self) -> dict[str, Any]:
        tables = self.list_tables()
        existing_table: dict[str, Any] | None = None
        for table in tables:
            if table.get("name") == self.table_name or table.get("id") == self.table_name:
                existing_table = table
                break

        if existing_table is not None:
            table_id = str(existing_table.get("id", "")).strip()
            self._ensure_required_fields(
                table_id=table_id,
                existing_table=existing_table,
                expected_fields=build_content_table_definition(table_name="Content")["fields"],
            )
            refreshed = self.list_tables()
            for table in refreshed:
                if table.get("id") == table_id:
                    return table
            return existing_table

        if self.table_name.startswith("tbl"):
            raise ValueError(
                f"Configured AIRTABLE_TABLE_ID {self.table_name} not found in this base."
            )

        payload = build_content_table_definition(table_name=self.table_name)
        response = self.session.post(
            self._meta_url("/tables"),
            headers=self._headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _ensure_required_fields(
        self,
        *,
        table_id: str,
        existing_table: dict[str, Any],
        expected_fields: list[dict[str, Any]],
    ) -> None:
        existing_names = {field.get("name") for field in existing_table.get("fields", [])}
        missing = [field for field in expected_fields if field.get("name") not in existing_names]
        for field_def in missing:
            response = self.session.post(
                self._meta_url(f"/tables/{table_id}/fields"),
                headers=self._headers,
                json=field_def,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()

    def create_content_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for bucket in chunked(records, 10):
            payload = {"records": [{"fields": row} for row in bucket]}
            response = self.session.post(
                self._data_url(),
                headers=self._headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            created.extend(response.json().get("records", []))
        return created

    def fetch_records_by_status(
        self,
        image_status: str | None = None,
        video_status: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        formula_parts: list[str] = []
        if image_status:
            formula_parts.append(f"{{Image Status}}='{image_status}'")
        if video_status:
            formula_parts.append(f"{{Video Status}}='{video_status}'")
        formula = "AND(" + ",".join(formula_parts) + ")" if formula_parts else ""

        params: dict[str, Any] = {"pageSize": page_size}
        if formula:
            params["filterByFormula"] = formula

        records: list[dict[str, Any]] = []
        offset = None
        while True:
            if offset:
                params["offset"] = offset
            response = self.session.get(
                self._data_url(),
                headers=self._headers,
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json() or {}
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                break
        return records

    def update_record_assets(
        self,
        record_id: str,
        image_url: str | None = None,
        video_url: str | None = None,
        image_status: str | None = None,
        video_status: str | None = None,
        actual_cost: float | None = None,
        provider: str | None = None,
        error: str | None = None,
        video_prompt: str | None = None,
        cloud_asset_path: str | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if image_url:
            fields["Generated Image"] = [{"url": image_url}]
        if video_url:
            fields["Generated Video"] = [{"url": video_url}]
        if image_status:
            fields["Image Status"] = image_status
        if video_status:
            fields["Video Status"] = video_status
        if actual_cost is not None:
            fields["Actual Cost"] = round(actual_cost, 4)
        if provider:
            fields["Provider Used"] = provider
        if error is not None:
            fields["Generation Error"] = error
        if video_prompt:
            fields["Video Prompt"] = video_prompt
        if cloud_asset_path:
            fields["Cloud Asset Path"] = cloud_asset_path

        payload = {"fields": fields}
        response = self.session.patch(
            f"{self._data_url()}/{record_id}",
            headers=self._headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
