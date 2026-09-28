"""
upload.py
POST /api/upload — accepts a dataset file and returns metadata + preview.
"""
from __future__ import annotations
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session as DBSession

from ..database.base import get_db
from ..schemas.dataset import UploadResponse
from ..services.file_service import FileService, get_file_service
from ..services.session_service import SessionService, get_session_service
from ..utils.config import get_settings

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    conversation_id: str = Form(...),
    session_id: str = Form(default=""),
    db: DBSession = Depends(get_db),
    file_svc: FileService = Depends(get_file_service),
    session_svc: SessionService = Depends(get_session_service),
    settings=Depends(get_settings),
):
    """
    Upload a supported dataset or document file.
    Returns dataset metadata, column list, missing-value summary, and a 5-row preview.
    """
    # Ensure the conversation exists
    convo = session_svc.get_conversation(db, conversation_id)
    if convo is None:
        sid = session_id or str(uuid.uuid4())
        convo = session_svc.create_conversation(db, sid, title="New Analysis")
        conversation_id = convo.id

    # Save file securely
    file_path, ext = await file_svc.save_upload(file, conversation_id)

    size_bytes = file_path.stat().st_size

    # Media files are stored for media workflows and do not enter the tabular
    # data-science pipeline.
    if ext == "mp4":
        dataset = session_svc.register_dataset(
            db=db,
            conversation_id=conversation_id,
            filename=file_path.name,
            original_filename=file.filename or "upload.mp4",
            file_path=str(file_path),
            n_rows=None,
            n_cols=None,
            size_bytes=size_bytes,
        )
        return UploadResponse(
            dataset_id=dataset.id,
            conversation_id=conversation_id,
            filename=file.filename or "upload.mp4",
            size_bytes=size_bytes,
            media_type="video/mp4",
        )

    # Load tabular/document uploads into a DataFrame.
    df = file_svc.read_dataframe(file_path, ext)
    n_rows, n_cols = df.shape

    # Quick auto-detect target (heuristic: last column or 'target'/'label')
    detected_target = None
    for candidate in ["Churn", "churn", "target", "label", "Target", "Label"]:
        if candidate in df.columns:
            detected_target = candidate
            break
    if detected_target is None:
        detected_target = df.columns[-1]

    # Register in DB
    dataset = session_svc.register_dataset(
        db=db,
        conversation_id=conversation_id,
        filename=file_path.name,
        original_filename=file.filename or "upload",
        file_path=str(file_path),
        n_rows=n_rows,
        n_cols=n_cols,
        size_bytes=size_bytes,
        detected_target=detected_target,
    )

    return UploadResponse(
        dataset_id=dataset.id,
        conversation_id=conversation_id,
        filename=file.filename or "upload",
        n_rows=n_rows,
        n_cols=n_cols,
        size_bytes=size_bytes,
        columns=df.columns.tolist(),
        detected_target=detected_target,
        missing_summary=file_svc.get_missing_summary(df),
        dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
        preview=file_svc.get_preview(df),
    )
