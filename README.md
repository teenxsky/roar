# ROAR - P2P Voice Chat

Простой голосовой чат с архитектурой peer-to-peer для общения в режиме реального времени без центрального сервера.
Автоматическое обнаружение участников в сети и мгновенная передача аудио.

## Требования

- MacOS
- Homebrew
- Python >=3.13

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
