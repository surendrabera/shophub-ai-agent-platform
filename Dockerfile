FROM python:3.12-slim AS builder

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appgroup /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup tests/ /app/tests/
COPY --chown=appuser:appgroup requirements.txt /app/requirements.txt

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.orchestrator:app", "--host", "0.0.0.0", "--port", "8000"]
