FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy all files first (needed for setuptools build)
COPY . .

# Install dependencies using uv
RUN uv sync

# Expose the port that Cloud Run will use
EXPOSE $PORT

# Run the server
CMD ["uv", "run", "server.py"]