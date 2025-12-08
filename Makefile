.PHONY: help
help:
	@echo "\033[33mДоступные команды:\033[0m"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


#--------------- КОМАНДЫ ДЛЯ ПРИЛОЖЕНИЯ ---------------#

.PHONY: env
env: ## Скопировать пример .env.example в .env
	@cp .env.example .env

.PHONY: run-app
run-app: ## Запустить приложение
	@python3.13 -m src.main

.PHONY: create-venv
create-venv: ## Создать виртуальное окружение python
	@python3.13 -m venv venv

.PHONY: install
install: ## Установить зависимости
	@pip install -r requirements.txt

.PHONY: freeze
freeze: ## Зафиксировать зависимости
	@pip freeze > requirements.txt


#--------------- КОМАНДЫ ДЛЯ КОД-СТИЛЯ ---------------#

.PHONY: lint
lint: ## Проверить стиль кода (линтинг)
	@./venv/bin/ruff check --config=ruff.toml

.PHONY: fix
fix: ## Исправить ошибки стиля (форматировать код)
	@./venv/bin/ruff check --fix --unsafe-fixes --config=ruff.toml
