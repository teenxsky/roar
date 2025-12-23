import json
import socket
import subprocess
import threading
import time
import netifaces

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
        self.use_tailscale = self._check_tailscale_available()

        mode = "Tailscale" if self.use_tailscale else "UDP broadcast"
        logger.success(f'PeerDiscovery инициализирован для {username} на {self.local_ip} (режим: {mode})')

    def get_local_ip(self) -> str:
        """Получить локальный IP адрес (предпочтительно Tailscale)."""
        try:
            # Сначала пробуем найти Tailscale интерфейс
            for iface in netifaces.interfaces():
                if 'tailscale' in iface.lower() or 'utun' in iface.lower():
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_INET in addrs:
                        ip = addrs[netifaces.AF_INET][0]['addr']
                        if ip.startswith('100.'):  # Tailscale диапазон 100.64.0.0/10
                            logger.info(f'Используется Tailscale IP: {ip}')
                            return ip

            # Fallback на обычный метод для локальной сети
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.warning(f'Не удалось определить IP, использую 127.0.0.1: {e}')
            return '127.0.0.1'

    def _check_tailscale_available(self) -> bool:
        """Проверить доступен ли Tailscale."""
        try:
            result = subprocess.run(
                ['tailscale', 'status'],
                capture_output=True,
                timeout=2,
                text=True
            )
            if result.returncode == 0:
                logger.info('Tailscale обнаружен и активен')
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.debug(f'Tailscale недоступен: {e}')

        return False

    def _get_tailscale_peers(self) -> dict[str, dict]:
        """Получить список пиров из Tailscale."""
        try:
            result = subprocess.run(
                ['tailscale', 'status', '--json'],
                capture_output=True,
                timeout=3,
                text=True
            )

            if result.returncode != 0:
                logger.warning(f'Ошибка tailscale status: {result.stderr}')
                return {}

            data = json.loads(result.stdout)
            peers = {}

            # Парсим пиров
            for peer_key, peer_info in data.get('Peer', {}).items():
                # Проверяем что пир онлайн
                if not peer_info.get('Online', False):
                    continue

                # Получаем IPv4 адрес (первый в списке TailscaleIPs)
                tailscale_ips = peer_info.get('TailscaleIPs', [])
                if not tailscale_ips:
                    continue

                # Берем только IPv4 (начинается с 100.)
                peer_ip = None
                for ip in tailscale_ips:
                    if ip.startswith('100.'):
                        peer_ip = ip
                        break

                if not peer_ip or peer_ip == self.local_ip:
                    continue

                # Используем HostName как username
                hostname = peer_info.get('HostName', 'Unknown')

                peers[peer_ip] = {
                    'username': hostname,
                    'tcp_port': self.tcp_port,  # Используем стандартный порт
                    'last_seen': time.time(),
                }

            return peers

        except (subprocess.TimeoutExpired, json.JSONDecodeError, subprocess.SubprocessError) as e:
            logger.error(f'Ошибка при получении Tailscale пиров: {e}')
            return {}

    def start(self) -> None:
        """Запустить процесс обнаружения пиров."""
        self.running = True

        if self.use_tailscale:
            # Используем Tailscale discovery
            discovery_thread = threading.Thread(target=self._tailscale_discovery_loop, daemon=True)
            discovery_thread.start()
            logger.success('PeerDiscovery запущен (Tailscale режим)')
        else:
            # Используем классический UDP broadcast
            announce_thread = threading.Thread(target=self._announce_loop, daemon=True)
            announce_thread.start()

            listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            listen_thread.start()

            logger.success('PeerDiscovery запущен (UDP broadcast режим)')

        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

    def stop(self) -> None:
        """Остановить процесс обнаружения."""
        self.running = False
        logger.info('PeerDiscovery остановлен')

    def _tailscale_discovery_loop(self) -> None:
        """Периодически получать список пиров из Tailscale."""
        while self.running:
            try:
                tailscale_peers = self._get_tailscale_peers()

                # Обновляем список пиров
                for peer_ip, peer_info in tailscale_peers.items():
                    if peer_ip not in self.peers:
                        logger.success(f'Обнаружен новый Tailscale пир: {peer_info["username"]} ({peer_ip})')

                    self.peers[peer_ip] = peer_info

                # Удаляем пиров которые больше не в Tailscale сети
                current_peers = set(self.peers.keys())
                tailscale_peer_ips = set(tailscale_peers.keys())
                removed_peers = current_peers - tailscale_peer_ips

                for peer_ip in removed_peers:
                    username = self.peers[peer_ip]['username']
                    del self.peers[peer_ip]
                    logger.warning(f'Tailscale пир отключился: {username} ({peer_ip})')

            except Exception as e:
                logger.error(f'Ошибка в Tailscale discovery loop: {e}')

            time.sleep(config.BROADCAST_INTERVAL)

    def _announce_loop(self) -> None:
        """Периодически отправлять broadcast с информацией о себе (только для локальной сети)."""
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
                # Пробуем broadcast на разные адреса
                for bcast_addr in ['255.255.255.255', '192.168.255.255']:
                    try:
                        sock.sendto(message.encode(), (bcast_addr, self.broadcast_port))
                        logger.debug(f'Отправлен broadcast на {bcast_addr}: {self.username}')
                    except Exception as e:
                        logger.debug(f'Ошибка broadcast на {bcast_addr}: {e}')
            except Exception as e:
                logger.error(f'Ошибка при отправке broadcast: {e}')

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
