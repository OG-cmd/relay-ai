
from fastapi.middleware.cors import CORSMiddleware


import os
import time

from fastapi import Header
from typing import Optional

from schemas import ChatRequest
from llm_service import (
    generate_with_fallback,
    AllProvidersUnavailable,
    PROVIDERS
)

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Message

from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import Base, engine
import models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables when the server starts
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Lyftr AI Chatbot",
    version="1.0.0",
    lifespan=lifespan
)

# Allow the React frontend to communicate with FastAPI.
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Simulate-Failure"],
)



@app.get("/health")
def health():
    from sqlalchemy import text
    import litellm

    # Verify the SQLite database is reachable.
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="database unavailable"
        )

    # Count configured API keys.
    keys_configured = sum(
        1 for provider in PROVIDERS
        if provider.get("api_key")
    )

    # Verify LiteLLM caching is initialized.
    cache_enabled = litellm.cache is not None

    if keys_configured < 2 or not cache_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI gateway not ready"
        )

    return {
        "status": "ok",
        "keys_configured": keys_configured,
        "cache_enabled": cache_enabled
    }



@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    db: Session = SessionLocal()

    try:
        messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.id.asc())
            .all()
        )

        if not messages:
            raise HTTPException(
                status_code=404,
                detail="session not found"
            )

        history = []

        for message in messages:
            item = {
                "role": message.role,
                "content": message.content
            }

            if message.role == "assistant":
                item["metadata"] = (
                    json.loads(message.metadata_json)
                    if message.metadata_json
                    else {}
                )

            history.append(item)

        return {
            "session_id": session_id,
            "messages": history
        }

    finally:
        db.close()


@app.post("/chat")
def chat(
    request: ChatRequest,
    x_simulate_failure: Optional[str] = Header(default=None)
):
    start_time = time.perf_counter()

    # Parse the optional failure-simulation header
    simulated_failures = {}

    if (
        os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower()
        == "true"
        and x_simulate_failure
    ):
        for entry in x_simulate_failure.split(","):
            parts = entry.strip().split("=")

            if len(parts) == 2:
                key_id, status = parts

                if status.strip() in ("429", "500", "502", "503"):
                    simulated_failures[key_id.strip()] = int(
                        status.strip()
                    )

    db = SessionLocal()

    try:
        # Retrieve earlier conversation messages
        previous_messages = (
            db.query(Message)
            .filter(Message.session_id == request.session_id)
            .order_by(Message.id.asc())
            .all()
        )

        # Build the complete LLM conversation context
        messages = [
            {
                "role": "system",
                "content": request.system_prompt
                or "You are a helpful AI assistant."
            }
        ]

        for stored_message in previous_messages:
            messages.append({
                "role": stored_message.role,
                "content": stored_message.content
            })

        messages.append({
            "role": "user",
            "content": request.message
        })

        # Call the AI gateway with automatic fallback
        try:
            result = generate_with_fallback(
                messages=messages,
                simulated_failures=simulated_failures
            )

        except AllProvidersUnavailable:
            raise HTTPException(
                status_code=503,
                detail="all providers unavailable"
            )

        # Calculate response latency
        latency_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        # Response metadata
        metadata = {
            "resolution_source": result["resolution_source"],
            "model": result["model"],
            "latency_ms": latency_ms,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "key_id": result["key_id"],
            "fallback_attempts": result["fallback_attempts"]
       }

        # Store the user's message
        db.add(Message(
            session_id=request.session_id,
            role="user",
            content=request.message
        ))

        # Store the assistant's response
        db.add(Message(
            session_id=request.session_id,
            role="assistant",
            content=result["reply"],
            metadata_json=json.dumps(metadata)
        ))

        # Commit both messages together
        db.commit()

        return {
            "session_id": request.session_id,
            "reply": result["reply"],
            "metadata": metadata
        }

    finally:
        db.close()
