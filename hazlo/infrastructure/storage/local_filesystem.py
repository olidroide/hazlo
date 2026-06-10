"""Local filesystem implementation of RawDocumentStore."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

from hazlo.domain.raw_document import RawDocument


class LocalFilesystemStore:
    def __init__(self, base_path: Path) -> None:
        self._base = base_path

    def _path(self, event_id: UUID) -> Path:
        return self._base / f"{event_id}.raw.json"

    def write(self, event_id: UUID, data: RawDocument) -> Path:
        path = self._path(event_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._serialize(data), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(path)
        return path

    def read(self, event_id: UUID) -> RawDocument:
        path = self._path(event_id)
        if not path.exists():
            msg = f"Raw document not found: {path}"
            raise FileNotFoundError(msg)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        return self._deserialize(raw)

    def exists(self, event_id: UUID) -> bool:
        return self._path(event_id).exists()

    def delete(self, event_id: UUID) -> None:
        path = self._path(event_id)
        if path.exists():
            path.unlink()

    def get_uri(self, event_id: UUID) -> str:
        return str(self._path(event_id))

    @staticmethod
    def _serialize(data: RawDocument) -> dict[str, object]:
        return {
            "event_id": str(data.event_id),
            "source_url": data.source_url,
            "adapter": data.adapter,
            "content_type": data.content_type,
            "body": data.body.decode("utf-8", errors="replace"),
            "payload": data.payload,
            "content_hash": data.content_hash,
            "byte_size": data.byte_size,
            "fetched_at": data.fetched_at.isoformat(),
        }

    @staticmethod
    def _deserialize(raw: dict[str, object]) -> RawDocument:
        from datetime import datetime
        from typing import cast

        payload = cast(dict[str, object], raw["payload"])
        return RawDocument(
            event_id=UUID(str(raw["event_id"])),
            source_url=str(raw["source_url"]),
            adapter=str(raw["adapter"]),
            content_type=str(raw["content_type"]),
            body=str(raw["body"]).encode("utf-8"),
            payload=payload,
            content_hash=str(raw["content_hash"]),
            byte_size=int(cast(int, raw["byte_size"])),
            fetched_at=datetime.fromisoformat(str(raw["fetched_at"])),
        )
