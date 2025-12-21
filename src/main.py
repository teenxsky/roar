import curses
import threading
import time

from loguru import logger

from src.app import VoiceP2PChat
from src.cli import app
from src.config import config

# setup_logging()


def main() -> None:
    """Точка входа в приложение."""

    curses.wrapper(app)

    return

    # username = config.USERNAME
    # if not username:
    #     username = prompt_username()

    chat = VoiceP2PChat(config.USERNAME)

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
