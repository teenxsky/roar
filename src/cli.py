import sys
import threading


def prompt_username() -> str:
    """Получить имя пользователя из аргументов или запросить ввод."""
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        print('                                        ')
        print('                                        ')
        print('  /$$$$$$   /$$$$$$   /$$$$$$   /$$$$$$ ')
        print(' /$$__  $$ /$$__  $$ |____  $$ /$$__  $$')
        print('| $$  \\__/| $$  \\ $$  /$$$$$$$| $$  \\__/')
        print('| $$      | $$  | $$ /$$__  $$| $$      ')
        print('| $$      |  $$$$$$/|  $$$$$$$| $$      ')
        print('|__/       \\______/  \\_______/|__/      ')
        print('                                        ')
        print('                                        ')
        username = input('Введите ваше имя: ').strip()
        if not username:
            username = 'Anonymous'

    return username
