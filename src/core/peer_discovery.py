import json
import socket
import threading
import time

from loguru import logger

from src.config import config


class PeerDiscovery:
    """Обнаружение пиров в локальной сети через UDP broadcast."""

    def __init__(
        self,
        username: str,
        broadcast_port: int | None = None,
        tcp_port: int | None = None,
    ) -> None:
        """
        Инициализация модуля обнаружения пиров.

        Args:
            username: Имя пользователя
            broadcast_port: Порт для UDP broadcast
            tcp_port: Порт для TCP соединений
        """
        self.username = username
        self.broadcast_port = broadcast_port or config.BROADCAST_PORT
        self.tcp_port = tcp_port or config.TCP_PORT
        self.peers = {}  # {ip: {"username": str, "last_seen": float}}
        self.running = False
        self.local_ip = self.get_local_ip()

        logger.debug(f'PeerDiscovery инициализирован для {username} на {self.local_ip}')

    def get_local_ip(self) -> str:
        """Получить локальный IP адрес."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.warning(f'Не удалось определить IP, использую 127.0.0.1: {e}')
            return '127.0.0.1'

    def start(self) -> None:
        """Запустить процесс обнаружения пиров."""
        self.running = True

        announce_thread = threading.Thread(target=self._announce_loop, daemon=True)
        announce_thread.start()

        listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        listen_thread.start()

        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        logger.success('PeerDiscovery запущен')

    def stop(self) -> None:
        """Остановить процесс обнаружения."""
        self.running = False
        logger.info('PeerDiscovery остановлен')

    def _announce_loop(self) -> None:
        """Периодически отправлять broadcast с информацией о себе."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        message = json.dumps(
            {
                'username': self.username,
                'ip': self.local_ip,
                'tcp_port': self.tcp_port,
            },
        )

        while self.running:
            try:
                sock.sendto(message.encode(), ('<broadcast>', self.broadcast_port))
                logger.debug(f'Отправлен broadcast: {self.username}')
            except Exception as e:
                logger.error(f'Ошибка при отправке broadcast: {e}')
                pass

            time.sleep(config.BROADCAST_INTERVAL)

        sock.close()

    def _listen_loop(self) -> None:
        """Прослушивать broadcast от других пиров."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', self.broadcast_port))
        sock.settimeout(1.0)

        logger.debug(f'Прослушивание broadcast на порту {self.broadcast_port}')

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                peer_info = json.loads(data.decode())
                peer_ip = peer_info['ip']

                if peer_ip == self.local_ip:
                    continue

                if peer_ip not in self.peers:
                    logger.success(f'Обнаружен новый пир: {peer_info["username"]} ({peer_ip})')

                self.peers[peer_ip] = {
                    'username': peer_info['username'],
                    'tcp_port': peer_info['tcp_port'],
                    'last_seen': time.time(),
                }

            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f'Ошибка при приеме broadcast: {e}')

        sock.close()

    def _cleanup_loop(self) -> None:
        """Удалять пиров, которые давно не отвечали."""
        while self.running:
            current_time = time.time()
            to_remove = []

            for peer_ip, info in self.peers.items():
                if current_time - info['last_seen'] > config.PEER_TIMEOUT:
                    to_remove.append(peer_ip)

            for peer_ip in to_remove:
                username = self.peers[peer_ip]['username']
                del self.peers[peer_ip]
                logger.warning(f'Пир отключился: {username} ({peer_ip})')

            time.sleep(config.CLEANUP_INTERVAL)

    def get_peers(self) -> dict[str, dict[str, str | int | float]]:
        """Получить список активных пиров."""
        return dict(self.peers)
