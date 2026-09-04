# Seller OS — free, local-first ($0). Single service + ./data volume.
FROM python:3.11-slim

# Free OCR runtime (Tesseract) + minimal build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Minimal seller deps first (cached layer)
COPY requirements-seller.txt ./
RUN pip install --no-cache-dir -r requirements-seller.txt

# App code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY web/ ./web/
COPY docs/ ./docs/

ENV PYTHONPATH=/app/src
ENV PORT=5003
ENV DUCKDB_PATH=/app/data/omni.duckdb
ENV AUDIT_PATH=/app/data/audit.jsonl
ENV ALLOWED_ROOT=/app/data/inbox
ENV SELLER_LLM=mock
ENV SELLER_MAX_LLM_USD=0.0
ENV ENVIRONMENT=production

VOLUME ["/app/data"]
EXPOSE 5003

CMD ["uvicorn", "omni_one.api.fastapi_app:create_omni_one_app", "--factory", "--host", "0.0.0.0", "--port", "5003"]
