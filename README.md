# Relay AI — Resilient LLM Chatbot

A full-stack AI chatbot built with **React, FastAPI, LiteLLM, and SQLite**, featuring automatic API-key failover, response caching, multi-turn conversation memory, and detailed gateway diagnostics.

Relay AI is designed to remain functional when an AI provider experiences rate limits or temporary service failures.

## Features

- **Multi-provider inference:** Gemini and Groq through LiteLLM.
- **Automatic failover:** Switches to the next configured provider on supported failures.
- **Response caching:** Uses LiteLLM's built-in local cache.
- **Conversation memory:** Stores messages in SQLite and retrieves previous conversations.
- **Per-request metadata:** Displays model, latency, token usage, and resolution source.
- **Gateway Diagnostics:** Shows provider attempts, failure reasons, and response times.
- **Containerized deployment:** Multi-stage Docker builds with persistent SQLite storage.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI |
| AI gateway | LiteLLM |
| AI providers | Google Gemini, Groq |
| Database | SQLite, SQLAlchemy |
| Frontend container | Nginx |
| Container orchestration | Docker Compose |
| Testing | pytest, FastAPI TestClient |

---


## 1. Live URLs

**Frontend:** https://relay-ai-frontend-p429.onrender.com

**Backend:** https://relay-ai-backend-fu2b.onrender.com

**API Documentation:** https://relay-ai-backend-fu2b.onrender.com/docs

**Health Endpoint:** https://relay-ai-backend-fu2b.onrender.com/health

**GitHub Repository:** https://github.com/OG-cmd/relay-ai

### Deployment Notes

The frontend is hosted as a Render Static Site, and the
backend runs as a Render Docker Web Service.

The application uses Gemini and Groq through LiteLLM,
with automatic provider failover and response caching.

The public deployment uses Render's free tier, which
provides ephemeral storage. SQLite history can be lost
after instance replacement or redeployment.

The local Docker Compose deployment uses a persistent
named volume mounted at /data, and its persistence
has been verified across container restarts.


## 2. Run locally: with Docker and without

### Prerequisites

- Docker Desktop with Docker Compose
- GNU Make (for the `make up` command)
- Python 3.10+
- Node.js and npm
- Valid Gemini and Groq API keys

### Environment configuration

Create `backend/.env` using the placeholders in the root `.env.example`.

Configure:

```dotenv
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
LLM_API_KEYS=${GEMINI_API_KEY},${GROQ_API_KEY}
DATABASE_URL=sqlite:///./app.db
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
ENABLE_FAILURE_SIMULATION=true
```

The application uses `LLM_API_KEYS` as an ordered key pool. The first key is assigned `key_1` and routed to Gemini; the second is assigned `key_2` and routed to Groq.

Never commit real API credentials.

### Run with Docker

From the repository root:

```bash
make up
```

This builds and starts the backend and frontend containers.

Open:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- API documentation: http://localhost:8000/docs

SQLite is stored in a named Docker volume mounted at `/data`, so conversation history survives container restarts.

Stop the stack:

```bash
make down
```

View logs:

```bash
make logs
```

Do not use `docker compose down -v` unless you intentionally want to delete the persistent database volume.

### Run without Docker

Start the backend:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

On Linux or macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start FastAPI:

```bash
python -m uvicorn main:app --reload --port 8000
```

In a separate terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173.

### Run backend tests

From the `backend` directory:

```bash
python -m pytest tests/ -v
```

The project currently contains 18 automated tests covering request validation, API responses, simulated failover, cache metadata, and session isolation.

## 3. Design decisions: key fallback, caching, SQLite session storage

### Key fallback

Relay AI uses LiteLLM with an ordered provider pool.

1. Gemini is attempted using `key_1`.
2. If Gemini encounters a supported retryable error, the gateway attempts Groq using `key_2`.
3. If both providers fail, the API returns HTTP 503 with the required JSON error.

Supported failure conditions include HTTP 429, selected quota and service errors, HTTP 5xx responses, connection errors, and timeouts.

The gateway uses provider-specific request timeouts to reduce delays when a provider is unavailable.

### Response caching

LiteLLM's built-in local response cache is enabled.

The cache is associated with the model and the full LLM message context, including the system prompt, previous conversation messages, and new user message.

A cache hit returns:

- `resolution_source: LLM_CACHE`
- `key_id: null`
- `fallback_attempts: 0`
- The cached response text and token usage

A new model inference returns `LIVE_INFERENCE`.

The cache is local to the backend process and is not designed to persist across container restarts.

### SQLite session storage

Messages are stored in SQLite and associated with a `session_id`.

For every successful request, the backend stores the user's message and the assistant's response.

The backend retrieves previous messages to construct the next LLM request, enabling multi-turn conversation memory.

The database is initialized automatically at startup and stored in a persistent Docker volume when running through Docker Compose.

### API endpoints

The backend exposes three application endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Database, key-pool and cache initialization status |
| POST | `/chat` | Generate an AI response with failover and caching |
| GET | `/sessions/{session_id}/messages` | Retrieve session history |

FastAPI also provides interactive API documentation at `/docs`.

## 4. Verification: how to see failover, cache hits and per-message token usage

### Verify backend health

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

### Verify automatic failover

Open the FastAPI Swagger interface at http://localhost:8000/docs.

Send a POST request to `/chat` with:

```json
{
  "session_id": "failover-demo-001",
  "message": "Explain Python in one sentence."
}
```

Set the request header:

```text
X-Simulate-Failure: key_1=429
```

Expected behavior: Gemini is simulated as failing, and Groq answers using `key_2`.

The response should report `fallback_attempts: 1` for a live fallback response.

### Verify all-provider failure

Send a request with a new session ID and:

```text
X-Simulate-Failure: *=429
```

Expected result:

- HTTP 503
- `{"detail":"all providers unavailable"}`
- The unsuccessful request is not saved to SQLite.

### Verify response caching

Send the same first message in two different new sessions, without a failure-simulation header.

The first request should return `LIVE_INFERENCE` if no matching cache entry exists.

The second request should return `LLM_CACHE` when the same model and message context are reused.

On a cache hit, the reply should be identical and the response should report `key_id: null`.

### Verify token tracking

Each assistant response displays:

- Input tokens
- Output tokens
- Model name
- Latency in milliseconds
- Resolution source

Token usage represents the individual request, not the accumulated conversation total.

## 5. Setup Used: your editor and AI tools

**Development environment:** Visual Studio Code, Windows, PowerShell, Ubuntu through WSL 2, Docker Desktop, Git, and GitHub.

**AI-assisted development:** ChatGPT was used for implementation guidance, debugging, code review, and testing assistance.

**API providers:** Google Gemini and Groq.

All application behavior was tested locally using FastAPI, pytest, and Docker Compose.

## 6. Bonus features (if any): what you added beyond the requirements and why

### Gateway Diagnostics

Relay AI includes an expandable diagnostics panel that displays the individual AI-provider attempts made during a request.

Each entry includes:

- Provider name and key identifier
- Success or failure status
- Failure reason
- Whether the failure was simulated
- Provider attempt duration

This makes the gateway's failover behavior transparent and easier to debug.

The diagnostics use an additional `failover_log` metadata field without removing or renaming any required API fields.

### Conversation history sidebar

The frontend provides a conversation history sidebar, allowing users to reopen previously created sessions.

Conversation references are retained in browser storage, while message contents remain in SQLite.

### Midnight Slate interface

The frontend uses a responsive dark interface designed for readability, with subdued colors, clearly separated message panels, and compact response metadata.

---

## Security considerations

- API credentials are stored in environment variables and excluded from Git.
- Responses expose key identifiers, never actual credentials.
- Docker build contexts exclude local secrets.
- The backend runs as a non-root user.
- CORS origins are configurable.
- Simulated failures can be controlled using `ENABLE_FAILURE_SIMULATION`.

## Project structure

```text
lyftr-ai-chatbot/
├── backend/
│   ├── main.py
│   ├── llm_service.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
├── frontend/
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example
├── .gitignore
└── README.md
```

---

**Relay AI — Intelligence without interruption.**