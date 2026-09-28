"""
conversations.py
CRUD endpoints for conversations.
GET  /api/conversations?session_id=...
POST /api/conversations
GET  /api/conversations/{id}
DELETE /api/conversations/{id}
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from ..database.base import get_db
from ..schemas.chat import (
    ConversationOut,
    ConversationSummary,
    MessageOut,
    NewConversationRequest,
    RenameConversationRequest,
)
from ..services.session_service import SessionService, get_session_service

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    session_id: str,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    return session_svc.list_conversations(db, session_id)


@router.post("/conversations", response_model=ConversationSummary)
def create_conversation(
    req: NewConversationRequest,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    convo = session_svc.create_conversation(db, req.session_id, req.title)
    return convo


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: str,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    convo = session_svc.get_conversation(db, conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            message_type=m.message_type,
            metadata=m.metadata_json,
            created_at=m.created_at,
        )
        for m in convo.messages
    ]
    return ConversationOut(
        id=convo.id,
        session_id=convo.session_id,
        title=convo.title,
        created_at=convo.created_at,
        updated_at=convo.updated_at,
        messages=messages,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: str,
    req: RenameConversationRequest,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    convo = session_svc.update_conversation_title(db, conversation_id, req.title)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: DBSession = Depends(get_db),
    session_svc: SessionService = Depends(get_session_service),
):
    deleted = session_svc.delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "id": conversation_id}
