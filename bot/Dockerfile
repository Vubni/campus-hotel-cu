FROM python:3.13-slim

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.txt .
# См. комментарий в backend/Dockerfile: кэш pip живёт в BuildKit-кэше, не в слое,
# поэтому повторные сборки не качают пакеты по сети заново.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -i "${PIP_INDEX_URL}" -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
