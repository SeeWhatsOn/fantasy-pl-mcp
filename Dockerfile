FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy all files first (needed for setuptools build)
COPY . .

# Install dependencies using uv
RUN uv sync

# Make sure Python can find our modules
ENV PYTHONPATH="/app/src:/app:$PYTHONPATH"

# Expose the port that Cloud Run will use
EXPOSE $PORT

# Run the simple, reliable Cloud Run MCP server
CMD ["uv", "run", "simple_cloud_run_server.py"]