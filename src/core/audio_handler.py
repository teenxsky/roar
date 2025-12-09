from loguru import logger
import pyaudio
import time
import array
import threading
import math


class AudioHandler:
    """Заглушка для обработки аудио (будет реализовано с PyAudio)."""

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100

    def __init__(self) -> None:
        self.recording: bool = False

        self.p = pyaudio.PyAudio()

        self.stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK,
        )

        self.out_stream = self.p.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK,
        )

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
        return self.stream.read(self.CHUNK, exception_on_overflow=False)

    def play_audio(self, data: bytes, peer_ip: str | None = None) -> None:
        """
        Воспроизводит полученные данные
        Можно использовать очередь для плавного воспроизведения.

        Args:
            data: полученные данные
            peer_ip: ip пира от кого пришли данные
        """
        logger.debug(f'Воспроизведение аудио от {peer_ip} ({len(data)} байт)')
        self.out_stream.write(data)

    def melody(self, stop_event) -> None:
        duration = 0.3
        notes = [440, 554, 659, 554]

        while not stop_event.is_set():
            for freq in notes:
                if stop_event.is_set():
                    break

                frames = array.array('h')
                for i in range(int(self.RATE * duration)):
                    sample = int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / self.RATE))
                    frames.append(sample)

                self.out_stream.write(frames.tobytes())

            time.sleep(0.1)
