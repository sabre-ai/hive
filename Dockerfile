FROM python:3.12-slim

WORKDIR /app

# Install build deps for psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached unless pyproject.toml changes)
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir \
    psycopg2-binary pgvector \
    fastapi uvicorn click rich mcp httpx sqlalchemy alembic "tomli-w>=1.0"

# Copy source and install the package (fast — deps already cached)
COPY src/ src/
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0
RUN pip install --no-cache-dir --no-deps .

EXPOSE 3000

CMD ["hive", "serve", "--port", "3000"]
