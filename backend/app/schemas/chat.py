"""
chat.py
Pydantic request/response schemas for the chat API.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ── Requests ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    dataset_id: Optional[str] = None
    target_col: Optional[str] = None
    business_objective: Optional[str] = None
    test_size: float = 0.2
    cv_folds: int = 5


class NewConversationRequest(BaseModel):
    session_id: str
    title: str = "New Analysis"


class RenameConversationRequest(BaseModel):
    title: str


# ── Responses ─────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    message_type: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageOut] = []

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── SSE Event Types ────────────────────────────────────────────────────

class SSEEvent(BaseModel):
    """A single Server-Sent Event payload."""
    event: str  # "progress" | "chunk" | "dataset_card" | "model_card" | "chart" | "done" | "error"
    data: Any
