FROM ghcr.io/astral-sh/uv:python3.14-bookworm

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="."
ENV GRADIO_SERVER_NAME="0.0.0.0"
EXPOSE 7860

COPY . .
CMD ["python", "src/app.py"]