import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Конфигурация приложения."""

    # Network Configuration
    TCP_HOST: str = str(os.getenv('TCP_HOST'))
    TCP_PORT: int = int(os.getenv('TCP_PORT'))
    BROADCAST_PORT: int = int(os.getenv('BROADCAST_PORT'))

    # Discovery Configuration
    BROADCAST_INTERVAL: int = int(os.getenv('BROADCAST_INTERVAL', '2'))
    PEER_TIMEOUT: int = int(os.getenv('PEER_TIMEOUT', '10'))
    CLEANUP_INTERVAL: int = int(os.getenv('CLEANUP_INTERVAL', '3'))

    # Network Configuration
    CONNECTION_CHECK_INTERVAL: int = int(os.getenv('CONNECTION_CHECK_INTERVAL', '3'))
    AUDIO_SEND_INTERVAL: float = float(os.getenv('AUDIO_SEND_INTERVAL', '0.05'))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')


config = Config()
