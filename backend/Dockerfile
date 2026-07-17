FROM python:3.13-slim

WORKDIR /app

# Можно подсунуть зеркало, если PyPI тянется медленно:
#   docker compose ... build --build-arg PIP_INDEX_URL=https://<зеркало>/simple/
ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.txt .
# Кэш pip живёт в BuildKit-кэше, а не в слое образа: образ не толстеет,
# а повторные сборки не качают пакеты заново по сети.
# Именно поэтому здесь НЕТ --no-cache-dir: он бы этот кэш обессмыслил.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -i "${PIP_INDEX_URL}" -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
