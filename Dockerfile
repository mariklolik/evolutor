FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[dev]" || true

FROM base AS runtime

COPY . .
RUN pip install --no-cache-dir -e .

ENTRYPOINT ["evolutor"]
CMD ["--help"]
