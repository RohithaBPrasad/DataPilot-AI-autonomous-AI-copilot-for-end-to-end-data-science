"""
session_service.py
Manages sessions and conversations in the database.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session as DBSession

from ..database.models import Session, Conversation, Message, Dataset


class SessionService:
    def get_or_create_session(self, db: DBSession, session_id: Optional[str] = None) -> Session:
        if session_id:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                return session
        new_session = Session(id=session_id or str(uuid.uuid4()))
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    def create_conversation(self, db: DBSession, session_id: str, title: str = "New Analysis") -> Conversation:
        self.get_or_create_session(db, session_id)
        convo = Conversation(session_id=session_id, title=title)
        db.add(convo)
        db.commit()
        db.refresh(convo)
        return convo

    def get_conversation(self, db: DBSession, conversation_id: str) -> Optional[Conversation]:
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()

    def update_conversation_title(self, db: DBSession, conversation_id: str, title: str) -> Optional[Conversation]:
        convo = self.get_conversation(db, conversation_id)
        if not convo:
            return None
        trimmed = title.strip()
        if not trimmed:
            return convo
        convo.title = trimmed
        convo.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(convo)
        return convo

    def list_conversations(self, db: DBSession, session_id: str) -> List[Conversation]:
        return (
            db.query(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )

    def delete_conversation(self, db: DBSession, conversation_id: str) -> bool:
        convo = self.get_conversation(db, conversation_id)
        if not convo:
            return False
        db.delete(convo)
        db.commit()
        return True

    def add_message(
        self,
        db: DBSession,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[dict] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_json=metadata,
        )
        db.add(msg)
        # Update conversation's updated_at timestamp
        convo = self.get_conversation(db, conversation_id)
        if convo:
            convo.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(msg)
        return msg

    def get_chat_history(self, db: DBSession, conversation_id: str) -> List[tuple]:
        """Returns list of (question, answer) tuples for DataChatAgent."""
        messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .all()
        )
        history = []
        user_msg = None
        for msg in messages:
            if msg.role == "user":
                user_msg = msg.content
            elif msg.role == "assistant" and user_msg is not None:
                history.append((user_msg, msg.content))
                user_msg = None
        return history

    def register_dataset(
        self,
        db: DBSession,
        conversation_id: str,
        filename: str,
        original_filename: str,
        file_path: str,
        n_rows: Optional[int],
        n_cols: Optional[int],
        size_bytes: int,
        detected_target: Optional[str] = None,
        profile_json: Optional[dict] = None,
    ) -> Dataset:
        dataset = Dataset(
            conversation_id=conversation_id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            n_rows=n_rows,
            n_cols=n_cols,
            size_bytes=size_bytes,
            detected_target=detected_target,
            profile_json=profile_json,
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset

    def get_latest_dataset(self, db: DBSession, conversation_id: str) -> Optional[Dataset]:
        return (
            db.query(Dataset)
            .filter(Dataset.conversation_id == conversation_id)
            .order_by(Dataset.created_at.desc())
            .first()
        )


_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
