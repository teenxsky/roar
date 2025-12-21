import array
import math
import time

import pyaudio
from loguru import logger


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
        notes = [
            (261.63, 0.3),  # C4
            (293.66, 0.3),  # D4
            (329.63, 0.3),  # E4
            (349.23, 0.3),  # F4
            (392.00, 0.3),  # G4
            (440.00, 0.3),  # A4
            (493.83, 0.3),  # B4
            (523.25, 0.3),  # С5
            (261.63, 0.3),  # C4
            (293.66, 0.3),  # D4
            (329.63, 0.3),  # E4
            (349.23, 0.3),  # F4
            (392.00, 0.3),  # G4
            (440.00, 0.3),  # A4
            (493.83, 0.3),  # B4
            (523.25, 0.3),  # С5
            (392.00, 0.3),  # G4
            (440.00, 0.3),  # A4
            (493.83, 0.3),  # B4
            (523.25, 0.3),  # С5
            (587.33, 0.3),  # D5
            (659.26, 0.3),  # E5
            (698.46, 0.3),  # F5
            (783.99, 0.3),  # G5
            (392.00, 0.3),  # G4
            (440.00, 0.3),  # A4
            (493.83, 0.3),  # B4
            (523.25, 0.3),  # С5
            (587.33, 0.3),  # D5
            (659.26, 0.3),  # E5
            (698.46, 0.3),  # F5
            (783.99, 0.3),  # G5
            (293.66, 0.8),  # D4
            (261.63, 0.8),  # C4
            (293.66, 0.8),  # D4
            (261.63, 0.8),  # C4
            (329.63, 0.3),  # E4
            (293.66, 0.3),  # D4
            (261.63, 0.6),  # C4
            (246.94, 0.8),  # B3
            (246.94, 0.6),  # B3
            (261.63, 0.3),  # C4
            (220.00, 1.5),  # A3
        ]

        # volume = 0.08
        volume = 0

        while not stop_event.is_set():
            for freq, duration in notes:
                if stop_event.is_set():
                    break

                frames = array.array('h')
                samples_count = int(self.RATE * duration)

                for i in range(samples_count):
                    t = i / samples_count
                    envelope = t / 0.1 if t < 0.1 else (1 - (t - 0.9) / 0.1) if t > 0.9 else 1
                    envelope = max(0.0, min(1.0, envelope))

                    sample = int(32767 * volume * envelope * math.sin(2 * math.pi * freq * i / self.RATE))
                    frames.append(sample)

                self.out_stream.write(frames.tobytes())

            time.sleep(0.2)
