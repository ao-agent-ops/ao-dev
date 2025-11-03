# Backend Python Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY src/ /app/src/
COPY pyproject.toml /app/
RUN pip install --upgrade pip && pip install -e .
EXPOSE 5959
CMD ["python", "-m", "src.server.develop_server"]
