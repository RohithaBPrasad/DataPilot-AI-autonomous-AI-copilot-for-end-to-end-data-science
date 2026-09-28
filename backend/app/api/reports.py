"""
reports.py
GET  /api/datasets/{dataset_id}
POST /api/report/{conversation_id}/download
GET  /api/report/{conversation_id}/status
"""
from __future__ import annotations
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session as DBSession

from ..database.base import get_db
from ..schemas.dataset import DatasetOut
from ..services.session_service import SessionService, get_session_service
from ..utils.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: str,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    from ..database.models import Dataset
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    from ..services.file_service import get_file_service
    file_svc = get_file_service()
    columns = None
    try:
        from pathlib import Path
        ext = dataset.filename.rsplit(".", 1)[-1].lower()
        df = file_svc.read_dataframe(Path(dataset.file_path), ext)
        columns = df.columns.tolist()
    except Exception:
        pass

    return DatasetOut(
        id=dataset.id,
        conversation_id=dataset.conversation_id,
        filename=dataset.filename,
        original_filename=dataset.original_filename,
        n_rows=dataset.n_rows,
        n_cols=dataset.n_cols,
        size_bytes=dataset.size_bytes,
        detected_target=dataset.detected_target,
        task_type=dataset.task_type,
        columns=columns,
        created_at=dataset.created_at,
    )


@router.get("/report/{conversation_id}/download")
def download_report(conversation_id: str):
    """Download the generated Markdown report."""
    report_path = os.path.join(settings.reports_dir, conversation_id, "report.md")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report not found. Run the analysis first.")
    return FileResponse(
        report_path,
        media_type="text/markdown",
        filename="data_scientist_report.md",
    )


@router.get("/report/{conversation_id}/text")
def get_report_text(conversation_id: str):
    """Return the report as plain text (for in-browser display)."""
    report_path = os.path.join(settings.reports_dir, conversation_id, "report.md")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report not found.")
    with open(report_path, "r", encoding="utf-8") as f:
        return PlainTextResponse(f.read())


    @router.get("/media/{conversation_id}/download")
    def download_uploaded_media(conversation_id: str, db: DBSession = Depends(get_db)):
        """Download the latest uploaded MP4 for a conversation."""
        from ..database.models import Dataset

        media = (
            db.query(Dataset)
            .filter(Dataset.conversation_id == conversation_id, Dataset.original_filename.ilike("%.mp4"))
            .order_by(Dataset.created_at.desc())
            .first()
        )
        if media is None or not os.path.exists(media.file_path):
            raise HTTPException(status_code=404, detail="Uploaded MP4 not found.")
        return FileResponse(media.file_path, media_type="video/mp4", filename=media.original_filename)


@router.get("/report/{conversation_id}/status")
def report_status(conversation_id: str):
    """Check whether a report exists for this conversation."""
    from ..agent.runner import get_result
    result = get_result(conversation_id)
    report_path = os.path.join(settings.reports_dir, conversation_id, "report.md")
    return {
        "has_result": result is not None,
        "has_report": os.path.exists(report_path),
        "best_model": result.best_model_name if result else None,
        "metrics": result.metrics if result else None,
    }
