FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy pyproject.toml and uv.lock first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen

# Copy the rest of the project files
COPY . .

# Expose the port that Cloud Run will use
EXPOSE $PORT

# Run the server
CMD ["uv", "run", "server.py"]