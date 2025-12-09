# roar

Простой голосовой чат с архитектурой peer-to-peer для общения в режиме реального времени без центрального сервера.
Автоматическое обнаружение участников в сети и мгновенная передача аудио.

## Требования

### Для локальной разработки:
- MacOS
- Homebrew
- Python >=3.13

### Для Docker:
- Docker
- Docker Compose

## Установка для разработки

### 1. Создать виртуальное окружение

```bash
make create-venv
source venv/bin/activate
```

### 2. Установить зависимости

```bash
make install
```

### Доступные команды для разработки

```bash
make help                 # Показать все команды
make create-venv          # Создать виртуальное окружение
make install              # Установить зависимости
make run-app              # Запустить приложение
make lint                 # Проверить код (линтинг)
make fix                  # Автоисправление стиля кода
make freeze               # Зафиксировать зависимости
```

## Запуск

### Локальная сеть (один WiFi роутер)

```bash
# Устройство 1
make run-app

# Устройство 2
make run-app
```

### Удаленное подключение через Tailscale

#### 1: Установка [Tailscale](https://tailscale.com/)

```bash
brew install tailscale
```

#### 2: Подключение

```bash
sudo tailscale up
```

#### 3: Проверка соединения

```bash
tailscale ip -4
```

#### 4: Запуск

```bash
make run-app
```

## Запуск через Docker

### Быстрый старт

```bash
docker-compose up --build
# or
docker-compose up -d
# or
docker-compose logs -f
```

### Запуск с тремя участниками

```bash
# Запустить все 3 пира (включая опциональный третий)
docker-compose --profile full up --build
```
