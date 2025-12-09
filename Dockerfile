FROM python:3.13.9-alpine3.22

WORKDIR /app

# TODO: проверить те ли это библиотеки
RUN apk update && apk add --no-cache \
    portaudio-dev \
    && rm -rf /var/cache/apk/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env.example .env

ENV PYTHONUNBUFFERED=1

# Открываем необходимые порты для P2P коммуникации
EXPOSE 5000-5010

CMD ["python", "-m", "src.main"]
