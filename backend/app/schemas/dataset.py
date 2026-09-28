"""
dataset.py
Pydantic schemas for dataset upload and metadata responses.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DatasetOut(BaseModel):
    id: str
    conversation_id: str
    filename: str
    original_filename: str
    n_rows: Optional[int]
    n_cols: Optional[int]
    size_bytes: Optional[int]
    detected_target: Optional[str]
    task_type: Optional[str]
    columns: Optional[List[str]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    dataset_id: str
    conversation_id: str
    filename: str
    n_rows: Optional[int] = None
    n_cols: Optional[int] = None
    size_bytes: int
    columns: List[str] = []
    detected_target: Optional[str] = None
    missing_summary: Dict[str, Any] = {}
    dtypes: Dict[str, str] = {}
    preview: List[Dict[str, Any]] = []  # first 5 rows as JSON-safe records
    media_type: Optional[str] = None
