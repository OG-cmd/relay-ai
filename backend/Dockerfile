
# ==========================================
# STAGE 1 — BUILD DEPENDENCIES
# ==========================================

FROM python:3.10-slim AS builder

WORKDIR /build

# Install dependencies into a separate directory
COPY requirements.txt .

RUN pip install --no-cache-dir \
    --prefix=/install \
    -r requirements.txt


# ==========================================
# STAGE 2 — PRODUCTION RUNTIME
# ==========================================

FROM python:3.10-slim AS runtime

WORKDIR /app

# Copy installed Python dependencies
COPY --from=builder /install /usr/local

# Copy application source files
COPY main.py .
COPY database.py .
COPY models.py .
COPY schemas.py .
COPY llm_service.py .

# Create directory for persistent SQLite storage
RUN mkdir -p /data

# Run the application as a non-root user
RUN useradd --uid 1000 --create-home appuser \
    && chown -R appuser:appuser /app /data


USER appuser

EXPOSE 8000

# Start FastAPI
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
