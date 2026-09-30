FROM python:3.12.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY .streamlit .streamlit
COPY app.py .

EXPOSE 8501
CMD ["uv", "run", "--no-sync", "streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
