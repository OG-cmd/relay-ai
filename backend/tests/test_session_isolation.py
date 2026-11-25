
import sys
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import main

client = TestClient(main.app)


def test_separate_conversation_histories(tmp_path, monkeypatch):
    # Give this test its own SQLite database.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base

    database_path = tmp_path / "sessions.db"

    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    monkeypatch.setattr(
        main, "SessionLocal", TestSessionLocal
    )

    session_a = f"pytest-a-{uuid4().hex}"
    session_b = f"pytest-b-{uuid4().hex}"

    def fake_generate(messages, simulated_failures=None):
        return {
            "reply": f"Reply to: {messages[-1]['content']}",
            "model": "groq/openai/gpt-oss-20b",
            "resolution_source": "LIVE_INFERENCE",
            "key_id": "key_2",
            "fallback_attempts": 0,
            "input_tokens": 20,
            "output_tokens": 10,
        }

    with patch(
        "main.generate_with_fallback",
        side_effect=fake_generate,
    ):
        response_a = client.post(
            "/chat",
            json={
                "session_id": session_a,
                "message": "Python is my favorite language.",
            },
        )

        response_b = client.post(
            "/chat",
            json={
                "session_id": session_b,
                "message": "JavaScript is my favorite language.",
            },
        )

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    history_a = client.get(
        f"/sessions/{session_a}/messages"
    )
    history_b = client.get(
        f"/sessions/{session_b}/messages"
    )

    assert history_a.status_code == 200
    assert history_b.status_code == 200

    messages_a = history_a.json()["messages"]
    messages_b = history_b.json()["messages"]

    assert len(messages_a) == 2
    assert len(messages_b) == 2

    assert messages_a[0]["role"] == "user"
    assert messages_a[1]["role"] == "assistant"

    assert messages_b[0]["role"] == "user"
    assert messages_b[1]["role"] == "assistant"

    assert "Python" in messages_a[0]["content"]
    assert "JavaScript" in messages_b[0]["content"]

    assert all(
        "JavaScript" not in message["content"]
        for message in messages_a
    )

    assert all(
        "Python" not in message["content"]
        for message in messages_b
    )

    engine.dispose()
