from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.base import Base
from backend.app.database.models import Conversation, Session
from backend.app.services.session_service import SessionService
from backend.app.utils.config import Settings


def test_allowed_extensions_include_document_and_tabular_formats():
    settings = Settings()

    assert "csv" in settings.allowed_extensions
    assert "json" in settings.allowed_extensions
    assert "jsonl" in settings.allowed_extensions
    assert "parquet" in settings.allowed_extensions
    assert "feather" in settings.allowed_extensions
    assert "pdf" in settings.allowed_extensions
    assert "docx" in settings.allowed_extensions
    assert "txt" in settings.allowed_extensions
    assert "md" in settings.allowed_extensions


def test_update_conversation_title():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    session = Session(id="session-1")
    db.add(session)
    db.commit()

    conversation = Conversation(session_id=session.id, title="Old title")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    updated = SessionService().update_conversation_title(db, conversation.id, "New title")

    assert updated is not None
    assert updated.title == "New title"
    assert db.query(Conversation).filter_by(id=conversation.id).one().title == "New title"
