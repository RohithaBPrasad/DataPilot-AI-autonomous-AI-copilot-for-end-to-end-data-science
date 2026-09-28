"""
chat.py
POST /api/chat — the main chat endpoint.
Streams SSE events: progress stages, charts, model cards, and LLM text chunks.
"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from ..database.base import get_db
from ..schemas.chat import ChatRequest
from ..services.session_service import SessionService, get_session_service
from ..services.web_answer import get_web_answer
from ..agent.runner import run_agent_streaming, get_result
from ..utils.config import get_settings

router = APIRouter()
settings = get_settings()


def _sse(event: str, data) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


async def _chat_stream(
    req: ChatRequest,
    db: DBSession,
    session_svc: SessionService,
) -> AsyncGenerator[str, None]:
    """
    Core SSE generator.
    Detects whether this is a full-pipeline run or a follow-up chat message.
    """
    conversation_id = req.conversation_id
    user_message = req.message.strip()

    # Persist user message
    session_svc.add_message(db, conversation_id, "user", user_message)

    # Check if we have an existing run result (follow-up chat)
    existing_result = get_result(conversation_id)

    is_analysis_request = (
        existing_result is None and req.dataset_id is not None and req.target_col is not None
    ) or any(
        kw in user_message.lower()
        for kw in ["analyze", "analyse", "train", "build model", "predict", "run analysis"]
    )

    if existing_result is None and req.dataset_id is not None and is_analysis_request:
        # ── Full Pipeline Run ─────────────────────────────────────────
        # Find dataset file path
        dataset = session_svc.get_latest_dataset(db, conversation_id)
        if dataset is None:
            yield _sse("error", {"message": "No dataset found. Please upload a dataset first."})
            return

        csv_path = dataset.file_path
        target_col = req.target_col or dataset.detected_target or ""
        if not target_col:
            yield _sse("error", {"message": "Please specify a target column."})
            return

        # Create output directory for this conversation
        output_dir = os.path.join(settings.reports_dir, conversation_id)
        os.makedirs(output_dir, exist_ok=True)

        full_response_parts = []
        async for event in run_agent_streaming(
            csv_path=csv_path,
            target_col=target_col,
            business_objective=req.business_objective or user_message,
            output_dir=output_dir,
            test_size=req.test_size,
            cv_folds=req.cv_folds,
            conversation_id=conversation_id,
        ):
            yield _sse(event["event"], event["data"])
            if event["event"] == "chunk":
                full_response_parts.append(event["data"].get("text", ""))

        # Persist assistant message
        full_response = "".join(full_response_parts)
        if full_response:
            session_svc.add_message(
                db, conversation_id, "assistant", full_response, message_type="analysis"
            )

    elif existing_result is not None:
        # ── Follow-up Chat ────────────────────────────────────────────
        yield _sse("progress", {"stage": 0, "label": "Thinking...", "total": 1})

        history = session_svc.get_chat_history(db, conversation_id)
        chat_agent = getattr(existing_result, "chat_agent", None)
        if chat_agent is None:
            answer = (
                "Chat is unavailable for this run because the result did not include a chat agent. "
                "Please rerun the analysis or upload the dataset again to enable follow-up questions."
            )
        else:
            answer = chat_agent.ask(user_message, history)

        # Stream the answer word by word
        words = answer.split(" ")
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size]) + (" " if i + chunk_size < len(words) else "")
            yield _sse("chunk", {"text": chunk})

        session_svc.add_message(db, conversation_id, "assistant", answer)
        yield _sse("done", {"conversation_id": conversation_id})

    else:
        # ── General web question ─────────────────────────────────────
        # A dataset in the conversation should not prevent ordinary questions
        # from being answered with current outside information.
        answer = get_web_answer(user_message)
        words = answer.split(" ")
        for i in range(0, len(words), 6):
            yield _sse("chunk", {"text": " ".join(words[i:i + 6]) + " "})

        session_svc.add_message(db, conversation_id, "assistant", answer)
        yield _sse("done", {"conversation_id": conversation_id})


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    """
    Main chat endpoint — streams SSE events to the frontend.
    Content-Type: text/event-stream
    """
    return StreamingResponse(
        _chat_stream(req, db, session_svc),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
