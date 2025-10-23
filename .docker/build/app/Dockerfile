FROM python:3.11-slim

# Evita pyc e buffers em logs
ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y python3-pip

RUN mkdir /.local \
    && chown 1000:1000 /.local

WORKDIR /app

# Porta do servidor MCP
EXPOSE 8030