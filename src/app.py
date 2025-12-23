import time

from loguru import logger

from src.config import config
from src.core.audio_handler import AudioHandler
from src.core.network_manager import NetworkManager
from src.core.peer_discovery import PeerDiscovery
import threading


class VoiceP2PChat:
    """P2P голосовой чат для локальной сети."""

    def __init__(self, username: str) -> None:
        """
        Инициализация P2P голосового чата.

        Args:
            username: Имя пользователя
        """
        self.username = username
        self.running = False
        self.text_message_callback = None  # Callback для UI при получении текста

        self.discovery = PeerDiscovery(username)
        self.network = NetworkManager()
        self.audio = AudioHandler()

        self.waiting_music_stop = threading.Event()
        self.waiting_thread = None

        self.network.set_audio_callback(self._on_audio_received)
        self.network.set_text_callback(self._on_text_received)

        logger.debug(f'VoiceP2PChat инициализирован для {username}')

    def set_text_message_callback(self, callback) -> None:
        """
        Установить callback для обработки полученных текстовых сообщений.

        Args:
            callback: Функция, принимающая (username, message)
        """
        self.text_message_callback = callback

    def _on_audio_received(self, audio_data: bytes, peer_ip: str) -> None:
        """
        Callback для обработки полученного аудио.

        Args:
            audio_data: Байты аудио данных
            peer_ip: IP адрес отправителя
        """
        self.audio.play_audio(audio_data, peer_ip)

    def _on_text_received(self, message: str, peer_ip: str) -> None:
        """
        Callback для обработки полученного текстового сообщения.

        Args:
            message: Текстовое сообщение
            peer_ip: IP адрес отправителя
        """
        # Получаем имя пользователя по IP
        peers = self.discovery.get_peers()
        username = peers.get(peer_ip, {}).get('username', peer_ip)

        logger.info(f'{username}: {message}')

        # Вызываем callback для UI если установлен
        if self.text_message_callback:
            self.text_message_callback(username, message)

    def send_message(self, message: str) -> None:
        """
        Отправить текстовое сообщение всем подключенным пирам.

        Args:
            message: Текстовое сообщение
        """
        if message and message.strip():
            self.network.send_text(message)
            logger.info(f'Вы: {message}')

    def start(self) -> None:
        """Запустить чат."""
        self.running = True

        # Запустить обнаружение пиров
        self.discovery.start()

        # Запустить сетевой менеджер
        self.network.start()

        # Начать запись аудио
        self.audio.start_recording()

        self.waiting_thread = threading.Thread(
            target=self.audio.melody, args=(self.waiting_music_stop,), daemon=True
        )
        self.waiting_thread.start()

        logger.success(f'Чат запущен! Пользователь: {self.username}')

        # Главный цикл
        try:
            last_connection_check = 0

            while self.running:
                current_time = time.time()

                # Периодически проверяем новых пиров и подключаемся к ним
                if current_time - last_connection_check > config.CONNECTION_CHECK_INTERVAL:
                    self._connect_to_new_peers()
                    last_connection_check = current_time

                # Получить аудио и отправить всем
                audio_chunk = self.audio.get_audio_chunk()
                if audio_chunk:
                    self.network.send_audio(audio_chunk)

                time.sleep(config.AUDIO_SEND_INTERVAL)

        except KeyboardInterrupt:
            logger.info('Получен сигнал остановки (Ctrl+C)')
        finally:
            self.stop()

    def _connect_to_new_peers(self) -> None:
        """Подключиться к новым обнаруженным пирам."""
        discovered_peers = self.discovery.get_peers()
        connected_peers = self.network.get_connected_peers()

        for peer_ip, peer_info in discovered_peers.items():
            if peer_ip not in connected_peers:
                logger.debug(f'Попытка подключения к {peer_info["username"]} ({peer_ip})')
                self.network.connect_to_peer(peer_ip, peer_info['tcp_port'])

    def stop(self) -> None:
        """Остановить чат."""
        self.running = False

        logger.info('Остановка чата...')

        self.audio.stop_recording()
        self.network.stop()
        self.discovery.stop()

        logger.success('Чат остановлен')

    def print_status(self) -> None:
        """Вывести текущий статус."""
        discovered = self.discovery.get_peers()
        connected = self.network.get_connected_peers()

        logger.info('=== Статус чата ===')
        logger.info(f'Пользователь: {self.username}')
        logger.info(f'Обнаружено пиров: {len(discovered)}')
        logger.info(f'Подключенных пиров: {len(connected)}')

        if discovered:
            logger.info('Обнаруженные пиры:')
            for peer_ip, info in discovered.items():
                status = 'подключен' if peer_ip in connected else 'не подключен'
                logger.info(f'  - {info["username"]} ({peer_ip}) - {status}')
        else:
            logger.info('Пиры не обнаружены')
