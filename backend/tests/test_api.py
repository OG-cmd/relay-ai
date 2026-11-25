
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Allow tests to import our backend modules.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Enable failure simulation for tests.
os.environ["ENABLE_FAILURE_SIMULATION"] = "true"


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
import main
from database import Base
from llm_service import AllProvidersUnavailable

# Create a separate in-memory SQLite database for tests.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)

Base.metadata.create_all(bind=test_engine)

# Redirect application database sessions to the test database.
main.SessionLocal = TestSessionLocal

# Use the test database for the health endpoint as well.
main.engine = test_engine

client = TestClient(main.app)



# ==========================================
# 1. HEALTH ENDPOINT
# ==========================================

def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["keys_configured"] >= 2
    assert data["cache_enabled"] is True


# ==========================================
# 2. REQUEST VALIDATION
# ==========================================

@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"session_id": "test"},
        {"message": "Hello"},
        {"session_id": "", "message": "Hello"},
        {"session_id": "test", "message": ""},
        {"session_id": "test", "message": "   "},
        {"session_id": "test", "message": "x" * 4001},
        {"session_id": "x" * 129, "message": "Hello"},
    ],
)
def test_invalid_chat_requests(payload):
    response = client.post("/chat", json=payload)

    assert response.status_code == 422


# ==========================================
# 3. UNKNOWN SESSION
# ==========================================

def test_unknown_session():
    response = client.get(
        "/sessions/nonexistent-test-session/messages"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "session not found"
    }


# ==========================================
# 4. ALL PROVIDERS UNAVAILABLE
# ==========================================

def test_all_providers_unavailable():
    session_id = "pytest-all-failed"

    with patch(
        "main.generate_with_fallback",
        side_effect=AllProvidersUnavailable(
            "all providers unavailable"
        ),
    ):
        response = client.post(
            "/chat",
            json={
                "session_id": session_id,
                "message": "Hello",
            },
            headers={
                "X-Simulate-Failure": "*=429"
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "all providers unavailable"
    }

    # Failed requests must not be saved.
    history = client.get(
        f"/sessions/{session_id}/messages"
    )

    assert history.status_code == 404


# ==========================================
# 5. SUCCESSFUL CHAT RESPONSE
# ==========================================

def test_successful_chat():
    mock_result = {
        "reply": "Hello from Relay AI!",
        "model": "groq/openai/gpt-oss-20b",
        "resolution_source": "LIVE_INFERENCE",
        "key_id": "key_2",
        "fallback_attempts": 1,
        "input_tokens": 25,
        "output_tokens": 8,
    }

    with patch(
        "main.generate_with_fallback",
        return_value=mock_result,
    ):
        response = client.post(
            "/chat",
            json={
                "session_id": "pytest-success",
                "message": "Hello",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["reply"] == "Hello from Relay AI!"
    assert data["metadata"]["resolution_source"] == (
        "LIVE_INFERENCE"
    )
    assert data["metadata"]["key_id"] == "key_2"
    assert data["metadata"]["fallback_attempts"] == 1
    assert data["metadata"]["input_tokens"] == 25
    assert data["metadata"]["output_tokens"] == 8
    assert isinstance(
        data["metadata"]["latency_ms"],
        int,
    )
