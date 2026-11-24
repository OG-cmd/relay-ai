
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, Index
from database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    session_id = Column(String(128), nullable=False)

    role = Column(String, nullable=False)

    content = Column(Text, nullable=False)

    metadata_json = Column("metadata", Text, nullable=True)

    created_at = Column(
        String,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat()
    )

    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
    )

