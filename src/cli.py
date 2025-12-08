import sys


def prompt_username() -> str:
    """Получить имя пользователя из аргументов или запросить ввод."""
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        username = input("Введите ваше имя: ").strip()
        if not username:
            username = "Anonymous"

    return username
