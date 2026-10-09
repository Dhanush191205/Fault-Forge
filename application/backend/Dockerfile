FROM python:3.12.13-slim
WORKDIR /srv/backend
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra vector
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --uid 10001 --create-home forge && chown -R forge:forge /srv
USER forge
ENV PATH="/srv/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
