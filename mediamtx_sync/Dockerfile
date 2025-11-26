FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy sync service
COPY sync_service.py .
RUN chmod +x sync_service.py

# Run as non-root user
RUN useradd -m -u 1000 syncuser && \
    chown -R syncuser:syncuser /app

USER syncuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/mediamtx/mediamtx.yml') else 1)"

CMD ["python", "-u", "sync_service.py"]
