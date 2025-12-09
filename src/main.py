import threading
import time

from loguru import logger

from src.app import VoiceP2PChat
from src.cli import prompt_username
from src.config import config
from src.logging import setup_logging

setup_logging()


def main() -> None:
    """Точка входа в приложение."""

    username = config.USERNAME
    if not username:
        username = prompt_username()

    chat = VoiceP2PChat(username)

    chat_thread = threading.Thread(target=chat.start, daemon=True)
    chat_thread.start()

    time.sleep(2)

    try:
        while chat.running:
            cmd = input('> ').strip().lower()

            if cmd == 'status':
                chat.print_status()
            elif cmd == 'quit':
                break
            elif cmd:
                pass

    except KeyboardInterrupt:
        pass
    finally:
        chat.stop()
        time.sleep(1)
        logger.info('Программа завершена')


if __name__ == '__main__':
    main()
