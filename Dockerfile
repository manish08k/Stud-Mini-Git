# ── stage 1: build deps ───────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# copy installed packages
COPY --from=builder /install /usr/local

# copy source
COPY stud/ ./stud/
COPY backend/ ./backend/

# data volume (overridden by Kubernetes PVC in production)
RUN mkdir -p /data && chown appuser:appgroup /data
ENV STUD_SERVER_DATA=/data

USER appuser
EXPOSE 8000

# health-check – hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
