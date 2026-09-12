FROM python:3.12-slim

WORKDIR /app

# dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app code
COPY server.py ledger.py policy.py rag.py compression.py router.py \
     copilot.py config.py realtime.py game.py telegram_notify.py ./
COPY web/ ./web/
COPY observer/ ./observer/
COPY agent/ ./agent/

# non-root, data dir mounted as volume
RUN useradd -m appuser && mkdir -p /data && chown appuser /data
USER appuser

ENV FB_DATA_DIR=/data
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8765"]
