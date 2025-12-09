from loguru import logger


class AudioHandler:
    """Заглушка для обработки аудио (будет реализовано с PyAudio)."""

    def __init__(self) -> None:
        self.recording: bool = False

    def start_recording(self) -> None:
        """Открывает поток для записи с микрофона."""
        self.recording = True
        logger.warning('Запись начата (заглушка)')

    def stop_recording(self) -> None:
        """Закрывает поток записи с микрофона."""
        self.recording = False
        logger.warning('Запись остановлена (заглушка)')

    def get_audio_chunk(self) -> bytes | None:
        """
        Возвращает chunk из потока записи.

        Returns:
            bytes или None
        """
        return b'suba_bratik'

    def play_audio(self, data: bytes, peer_ip: str | None = None) -> None:
        """
        Воспроизводит полученные данные
        Можно использовать очередь для плавного воспроизведения.

        Args:
            data: полученные данные
            peer_ip: ip пира от кого пришли данные
        """
        logger.debug(f'Воспроизведение аудио от {peer_ip} ({len(data)} байт)')
