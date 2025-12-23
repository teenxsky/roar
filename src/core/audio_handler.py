import array
import math
import threading
import time
from queue import Empty, Queue

import pyaudio
from loguru import logger


class AudioHandler:
    """Безопасный обработчик аудио с защитой от buffer overflow и jitter buffer."""

    CHUNK = 4096
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100

    PLAYBACK_QUEUE_SIZE = 50

    JITTER_BUFFER_MIN = 8

    def __init__(self) -> None:
        self.recording: bool = False
        self.running: bool = True
        self.playback_started: bool = False

        # Очередь для безопасного воспроизведения с jitter buffer
        self.playback_queue: Queue = Queue(maxsize=self.PLAYBACK_QUEUE_SIZE)

        # Инициализация PyAudio
        self.pa = None
        self.input_stream = None
        self.output_stream = None

        try:
            self.pa = pyaudio.PyAudio()

            # Входной поток (запись с микрофона) - увеличен буфер
            self.input_stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=None,  # blocking mode для стабильности
            )

            # Выходной поток (воспроизведение) - увеличен буфер
            self.output_stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
                stream_callback=None,  # blocking mode для стабильности
            )

            logger.success(
                f'AudioHandler инициализирован (CHUNK={self.CHUNK}, '
                f'QUEUE={self.PLAYBACK_QUEUE_SIZE}, JITTER={self.JITTER_BUFFER_MIN})'
            )

        except Exception as e:
            logger.error(f'Ошибка инициализации AudioHandler: {e}')
            self._cleanup()
            raise

        # Запускаем отдельный поток для воспроизведения
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def start_recording(self) -> None:
        """Открывает поток для записи с микрофона."""
        self.recording = True
        logger.info('Запись с микрофона начата')

    def stop_recording(self) -> None:
        """Закрывает поток записи с микрофона."""
        self.recording = False
        logger.info('Запись с микрофона остановлена')

    def get_audio_chunk(self) -> bytes | None:
        """
        Возвращает chunk из потока записи.

        Returns:
            bytes или None в случае ошибки
        """
        if not self.recording or not self.input_stream:
            return None

        try:
            # exception_on_overflow=False предотвращает crash при переполнении INPUT буфера
            data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
            return data
        except OSError as e:
            logger.warning(f'Ошибка при чтении аудио: {e}')
            return None
        except Exception as e:
            logger.error(f'Критическая ошибка при чтении аудио: {e}')
            return None

    def play_audio(self, data: bytes, peer_ip: str | None = None) -> None:
        """
        Безопасное воспроизведение полученных данных через очередь с jitter buffer.

        Args:
            data: полученные аудио данные
            peer_ip: IP пира от кого пришли данные
        """
        if not data:
            return

        try:
            # Пытаемся добавить в очередь (non-blocking)
            self.playback_queue.put_nowait(data)

            queue_size = self.playback_queue.qsize()

            # Логируем только важные события для производительности
            if queue_size == self.JITTER_BUFFER_MIN and not self.playback_started:
                logger.info(f'Jitter buffer заполняется: {queue_size}/{self.JITTER_BUFFER_MIN}')
            elif queue_size % 20 == 0:
                logger.debug(f'Очередь: {queue_size}/{self.PLAYBACK_QUEUE_SIZE} чанков')

        except:
            # Очередь полна - удаляем 5 старых фреймов и добавляем новый
            # Это предотвращает накопление задержки
            try:
                for _ in range(5):
                    self.playback_queue.get_nowait()
                self.playback_queue.put_nowait(data)
                logger.warning(f'Очередь переполнена, удалено 5 старых фреймов')
            except:
                # Если и это не помогло - просто пропускаем фрейм
                logger.warning(f'Пропущен аудио фрейм от {peer_ip}')

    def _playback_loop(self) -> None:
        """
        Отдельный поток для безопасного воспроизведения аудио из очереди.
        Использует jitter buffer для компенсации нестабильности сети.
        """
        logger.info(f'Поток воспроизведения запущен с jitter buffer ({self.JITTER_BUFFER_MIN} чанков)')

        while self.running:
            try:
                # Jitter buffer: ждем минимального заполнения перед началом
                if not self.playback_started:
                    queue_size = self.playback_queue.qsize()
                    if queue_size < self.JITTER_BUFFER_MIN:
                        time.sleep(0.02)  # подождем накопления буфера
                        continue
                    else:
                        self.playback_started = True
                        logger.success(
                            f'Jitter buffer готов ({queue_size} чанков), '
                            f'начинаем плавное воспроизведение'
                        )

                # Получаем данные из очереди с коротким таймаутом
                try:
                    data = self.playback_queue.get(timeout=0.02)
                except Empty:
                    # Очередь опустела - сбрасываем флаг для повторного заполнения jitter buffer
                    if self.playback_started:
                        logger.warning(
                            'Очередь опустела (сетевые задержки), '
                            'пауза для накопления jitter buffer'
                        )
                        self.playback_started = False
                    time.sleep(0.01)
                    continue

                if not self.output_stream:
                    continue

                try:
                    # КРИТИЧЕСКИ ВАЖНО: оборачиваем write() в try-except
                    self.output_stream.write(data)
                except OSError as e:
                    # Обработка buffer overflow/underflow
                    if hasattr(e, 'errno'):
                        if e.errno == pyaudio.paOutputUnderflowed:
                            logger.debug('Output buffer underflow, пропуск фрейма')
                        elif e.errno == pyaudio.paOutputOverflowed:
                            logger.warning('Output buffer overflow, пропуск фрейма')
                        else:
                            logger.warning(f'OSError при воспроизведении: {e}')
                    else:
                        logger.warning(f'OSError при воспроизведении: {e}')
                    # НЕ бросаем исключение - просто пропускаем фрейм
                    continue

                except Exception as e:
                    logger.error(f'Ошибка при воспроизведении аудио: {e}')
                    continue

            except Exception as e:
                logger.error(f'Ошибка в playback loop: {e}')
                time.sleep(0.1)

        logger.info('Поток воспроизведения остановлен')

    def melody(self, stop_event) -> None:
        """
        Воспроизведение мелодии через безопасную очередь.

        Args:
            stop_event: Event для остановки воспроизведения
        """
        notes = [
            (261.63, 0.2),  # C4
            (293.66, 0.2),  # D4
            (329.63, 0.2),  # E4
            (349.23, 0.2),  # F4
            (392.00, 0.2),  # G4
            (440.00, 0.2),  # A4
            (493.83, 0.2),  # B4
            (523.25, 0.2),  # C5
            (261.63, 0.2),  # C4
            (293.66, 0.2),  # D4
            (329.63, 0.2),  # E4
            (349.23, 0.2),  # F4
            (392.00, 0.2),  # G4
            (440.00, 0.2),  # A4
            (493.83, 0.2),  # B4
            (523.25, 0.2),  # C5
            (392.00, 0.2),  # G4
            (440.00, 0.2),  # A4
            (493.83, 0.2),  # B4
            (523.25, 0.2),  # C5
            (587.33, 0.2),  # D5
            (659.26, 0.2),  # E5
            (698.46, 0.2),  # F5
            (783.99, 0.2),  # G5
            (392.00, 0.2),  # G4
            (440.00, 0.2),  # A4
            (493.83, 0.2),  # B4
            (523.25, 0.2),  # C5
            (587.33, 0.2),  # D5
            (659.26, 0.2),  # E5
            (698.46, 0.2),  # F5
            (783.99, 0.2),  # G5
        ]

        volume = 0  # отключена по умолчанию

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

                # Используем безопасный метод воспроизведения через очередь
                self.play_audio(frames.tobytes(), peer_ip='melody')

            time.sleep(0.2)

    def _cleanup(self) -> None:
        """Безопасная очистка ресурсов."""
        logger.info('Начинается cleanup AudioHandler...')

        # Останавливаем поток воспроизведения
        self.running = False

        # Даем потоку времени на завершение
        if hasattr(self, 'playback_thread') and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)

        # Закрываем потоки PyAudio
        if self.input_stream:
            try:
                if self.input_stream.is_active():
                    self.input_stream.stop_stream()
                self.input_stream.close()
                logger.debug('Input stream закрыт')
            except Exception as e:
                logger.warning(f'Ошибка при закрытии input stream: {e}')
            finally:
                self.input_stream = None

        if self.output_stream:
            try:
                if self.output_stream.is_active():
                    self.output_stream.stop_stream()
                self.output_stream.close()
                logger.debug('Output stream закрыт')
            except Exception as e:
                logger.warning(f'Ошибка при закрытии output stream: {e}')
            finally:
                self.output_stream = None

        # Завершаем PyAudio
        if self.pa:
            try:
                self.pa.terminate()
                logger.debug('PyAudio terminated')
            except Exception as e:
                logger.warning(f'Ошибка при завершении PyAudio: {e}')
            finally:
                self.pa = None

        logger.success('AudioHandler cleanup завершен')

    def __del__(self) -> None:
        """Деструктор - гарантирует освобождение ресурсов."""
        try:
            self._cleanup()
        except:
            pass
