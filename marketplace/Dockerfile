FROM node:24-alpine AS frontend-build

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FRONTEND_DIST_PATH=/app/frontend-dist

WORKDIR /app/backend

RUN addgroup --system safarismart \
    && adduser --system --ingroup safarismart --home /app safarismart

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend-build /build/frontend/dist /app/frontend-dist

RUN python -m pip install --no-cache-dir . \
    && chown -R safarismart:safarismart /app

USER safarismart

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; port=os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "python -m alembic upgrade head && python -m app.seed.destinations && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
