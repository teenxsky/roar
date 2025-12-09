import builtins
import contextlib
import socket
import struct
import threading
from collections.abc import Callable

from loguru import logger

from src.config import config


class NetworkManager:
    """Управление TCP соединениями для передачи аудио."""

    def __init__(self, tcp_port: int | None = None) -> None:
        """
        Инициализация сетевого менеджера.

        Args:
            tcp_port: Порт для TCP соединений
        """
        self.tcp_port = tcp_port or config.TCP_PORT
        self.connections = {}  # {peer_ip: socket}
        self.running = False
        self.audio_callback = None  # Функция для обработки полученного аудио
        self.lock = threading.Lock()

        logger.debug(f'NetworkManager инициализирован на порту {tcp_port}')

    def set_audio_callback(self, callback: Callable[[bytes, str], None]) -> None:
        """
        Установить callback для обработки полученного аудио.

        Args:
            callback: Функция, принимающая (data, peer_ip)
        """
        self.audio_callback = callback

    def start(self) -> None:
        """Запустить сервер для приема соединений."""
        self.running = True

        accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
        accept_thread.start()

        logger.success('NetworkManager запущен')

    def stop(self) -> None:
        """Остановить все соединения."""
        self.running = False

        with self.lock:
            for peer_ip, conn in self.connections.items():
                with contextlib.suppress(Exception):
                    conn.close()
                    logger.debug(f'Закрыто соединение с {peer_ip}')

            self.connections.clear()

        logger.info('NetworkManager остановлен')

    def _accept_connections(self) -> None:
        """Принимать входящие TCP соединения."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((config.TCP_HOST, self.tcp_port))
        server_socket.listen(5)
        server_socket.settimeout(1.0)

        logger.debug(f'Прослушивание TCP соединений на порту {self.tcp_port}')

        while self.running:
            try:
                conn, addr = server_socket.accept()
                peer_ip = addr[0]

                with self.lock:
                    if peer_ip not in self.connections:
                        self.connections[peer_ip] = conn
                        logger.success(f'Входящее соединение от {peer_ip}')

                        receive_thread = threading.Thread(
                            target=self._receive_from_peer,
                            args=(conn, peer_ip),
                            daemon=True,
                        )
                        receive_thread.start()
                    else:
                        conn.close()
                        logger.debug(f'Соединение от {peer_ip} уже существует')

            except TimeoutError:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f'Ошибка при приеме соединения: {e}')

        server_socket.close()

    def connect_to_peer(self, peer_ip: str, peer_port: int) -> bool:
        """
        Подключиться к пиру.

        Args:
            peer_ip: IP адрес пира
            peer_port: TCP порт пира
        """
        with self.lock:
            if peer_ip in self.connections:
                logger.debug(f'Соединение с {peer_ip} уже существует')
                return True

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((peer_ip, peer_port))

            with self.lock:
                self.connections[peer_ip] = sock

            self.waiting_music_stop.set()

            logger.success(f'Подключено к {peer_ip}:{peer_port}')

            # Запустить поток для приема данных
            receive_thread = threading.Thread(
                target=self._receive_from_peer,
                args=(sock, peer_ip),
                daemon=True,
            )
            receive_thread.start()

            return True

        except Exception as e:
            logger.error(f'Не удалось подключиться к {peer_ip}:{peer_port}: {e}')
            return False

    def _receive_from_peer(self, conn: socket.socket, peer_ip: str) -> None:
        """
        Принимать аудио данные от пира.

        Args:
            conn: Socket соединения
            peer_ip: IP адрес пира
        """
        logger.debug(f'Начат прием данных от {peer_ip}')

        while self.running:
            try:
                size_data = self._recv_exact(conn, 4)
                if not size_data:
                    break

                size = struct.unpack('!I', size_data)[0]

                audio_data = self._recv_exact(conn, size)
                if not audio_data:
                    break

                if self.audio_callback:
                    self.audio_callback(audio_data, peer_ip)

            except Exception as e:
                logger.error(f'Ошибка при приеме от {peer_ip}: {e}')
                break

        with self.lock:
            if peer_ip in self.connections:
                del self.connections[peer_ip]

        with contextlib.suppress(builtins.BaseException):
            conn.close()

        logger.warning(f'Соединение с {peer_ip} закрыто')

    def _recv_exact(self, conn: socket.socket, n: int) -> bytes | None:
        """
        Получить ровно n байт из сокета.

        Args:
            conn: Socket соединения
            n: Количество байт для чтения

        Returns:
            Данные или None при ошибке
        """
        data = b''
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def send_audio(self, audio_data: bytes) -> None:
        """
        Отправить аудио всем подключенным пирам.

        Args:
            audio_data: Байты аудио данных
        """
        if not audio_data:
            return

        size = len(audio_data)
        packet = struct.pack('!I', size) + audio_data

        with self.lock:
            disconnected = []

            for peer_ip, conn in self.connections.items():
                try:
                    conn.sendall(packet)
                except Exception as e:
                    logger.error(f'Ошибка отправки к {peer_ip}: {e}')
                    disconnected.append(peer_ip)

            for peer_ip in disconnected:
                del self.connections[peer_ip]
                logger.warning(f'Удалено разорванное соединение с {peer_ip}')

    def get_connected_peers(self) -> list[str]:
        """Получить список подключенных пиров."""
        with self.lock:
            return list(self.connections.keys())
