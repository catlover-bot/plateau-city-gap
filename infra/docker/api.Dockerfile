FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY analysis ./analysis
COPY backend ./backend
COPY infra ./infra
RUN pip install --no-cache-dir ".[platform]" \
    && useradd --create-home --uid 10001 citygap

USER citygap
EXPOSE 8000
CMD ["uvicorn", "backend.citygap_platform.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
