FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY app.py .

# Expose port
EXPOSE 8000

# Run with gunicorn
CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
