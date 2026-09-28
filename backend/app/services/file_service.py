"""
file_service.py
Handles file upload validation, secure storage, and cleanup.
"""
from __future__ import annotations
import json
import uuid
import shutil
from pathlib import Path
from typing import Any, Tuple

import pandas as pd
from fastapi import UploadFile, HTTPException

from ..utils.config import get_settings


MAX_PREVIEW_ROWS = 5


class FileService:
    def __init__(self):
        self.settings = get_settings()
        self.upload_dir = Path(self.settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _validate_extension(self, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in self.settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type '.{ext}' not allowed. Allowed: {self.settings.allowed_extensions}"
            )
        return ext

    async def save_upload(self, file: UploadFile, conversation_id: str) -> Tuple[Path, str]:
        """Saves an uploaded file to a conversation-scoped directory."""
        ext = self._validate_extension(file.filename or "")
        content = await file.read()

        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {self.settings.max_upload_size_mb}MB"
            )

        dest_dir = self.upload_dir / conversation_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}.{ext}"
        dest_path = dest_dir / safe_name
        with open(dest_path, "wb") as f:
            f.write(content)

        return dest_path, ext

    def read_dataframe(self, file_path: Path, ext: str) -> pd.DataFrame:
        """Reads a supported tabular dataset file into a DataFrame."""
        try:
            if ext == "csv":
                return pd.read_csv(file_path)
            if ext in {"xlsx", "xls"}:
                return pd.read_excel(file_path)
            if ext == "json":
                return pd.read_json(file_path)
            if ext == "jsonl":
                return pd.read_json(file_path, lines=True)
            if ext == "parquet":
                return pd.read_parquet(file_path)
            if ext == "feather":
                return pd.read_feather(file_path)
            if ext in {"pdf", "docx", "txt", "md"}:
                return pd.DataFrame([{"content": file_path.read_text(encoding="utf-8", errors="replace")}])
            raise HTTPException(status_code=400, detail=f"Unsupported dataset type: .{ext}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    def get_preview(self, df: pd.DataFrame) -> list:
        """Returns first N rows as JSON-safe list of dicts."""
        return df.head(MAX_PREVIEW_ROWS).fillna("").astype(str).to_dict(orient="records")

    def get_missing_summary(self, df: pd.DataFrame) -> dict:
        missing = df.isna().sum()
        pct = (missing / len(df) * 100).round(2)
        return {
            col: {"count": int(missing[col]), "pct": float(pct[col])}
            for col in df.columns
            if missing[col] > 0
        }

    def cleanup_conversation(self, conversation_id: str) -> None:
        """Remove all uploaded files for a conversation."""
        target = self.upload_dir / conversation_id
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


_file_service: FileService | None = None


def get_file_service() -> FileService:
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service
