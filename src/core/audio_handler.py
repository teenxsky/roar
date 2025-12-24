import io
import threading
import time
from queue import Empty, Queue

import numpy as np
import pyaudio
import soundfile as sf
from loguru import logger


class AudioHandler:
    """
    Простой аудио обработчик с Vorbis сжатием.

    Архитектура:
    - Микрофон → numpy array → Vorbis (OGG) → Network
    - Network → Vorbis decode → numpy array → суммирование → PyAudio
    """

    # Аудио параметры (из статьи Habr)
    CHUNK = 2048  # Размер чанка
    FORMAT = pyaudio.paInt16  # 16-bit PCM
    CHANNELS = 1  # Mono для голоса
    RATE = 16000  # 16 kHz (достаточно для речи, меньше трафика)

    PLAYBACK_QUEUE_SIZE = 50  # Размер очереди воспроизведения

    def __init__(self) -> None:
        """Инициализация аудио обработчика."""
        self.recording: bool = False
        self.running: bool = True

        # Очередь для воспроизведения
        self.playback_queue: Queue = Queue(maxsize=self.PLAYBACK_QUEUE_SIZE)

        # PyAudio
        self.pa = None
        self.input_stream = None
        self.output_stream = None

        try:
            self.pa = pyaudio.PyAudio()

            # Входной поток (микрофон)
            self.input_stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
            )

            # Выходной поток (динамики)
            self.output_stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
            )

            logger.success(
                f'AudioHandler инициализирован | '
                f'Rate: {self.RATE}Hz | Chunk: {self.CHUNK} | '
                f'Codec: Vorbis (OGG) ~4x compression'
            )

        except Exception as e:
            logger.error(f'Ошибка инициализации PyAudio: {e}')
            self._cleanup()
            raise

        # Запуск потока воспроизведения
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def start_recording(self) -> None:
        """Начать запись с микрофона."""
        self.recording = True
        logger.info('Запись с микрофона начата')

    def stop_recording(self) -> None:
        """Остановить запись."""
        self.recording = False
        logger.info('Запись остановлена')

    def get_audio_chunk(self) -> bytes | None:
        """
        Получить сжатый аудио chunk (Vorbis/OGG).

        Процесс:
        1. Читаем RAW PCM с микрофона
        2. Конвертируем в numpy array (int16 → float32)
        3. Сжимаем через soundfile (Vorbis codec)
        4. Возвращаем сжатые OGG bytes

        Returns:
            Сжатые OGG данные или None при ошибке/тишине
        """
        if not self.recording or not self.input_stream:
            return None

        try:
            # Читаем RAW PCM с микрофона
            raw_pcm = self.input_stream.read(self.CHUNK, exception_on_overflow=False)

            # Конвертируем в numpy array (int16 → float32 для soundfile)
            signal = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32)

            # Нормализуем в диапазон [-1.0, 1.0]
            signal = signal / 32768.0

            # Сжимаем через Vorbis (soundfile)
            # Используем BytesIO чтобы не писать на диск
            byte_io = io.BytesIO()
            sf.write(byte_io, signal, self.RATE, format='OGG')

            # Получаем сжатые bytes
            ogg_data = bytes(byte_io.getbuffer())

            # Логируем степень сжатия (раз в 100 чанков)
            if hasattr(self, '_compression_counter'):
                self._compression_counter += 1
            else:
                self._compression_counter = 1

            if self._compression_counter % 100 == 0:
                compression_ratio = len(raw_pcm) / len(ogg_data)
                logger.debug(
                    f'Vorbis compression: {len(raw_pcm)}→{len(ogg_data)} bytes ({compression_ratio:.1f}x)'
                )

            return ogg_data

        except Exception as e:
            logger.error(f'Ошибка при кодировании аудио: {e}')
            return None

    def play_audio(self, ogg_data: bytes, peer_ip: str | None = None) -> None:
        """
        Воспроизвести полученные OGG данные.

        Args:
            ogg_data: Сжатые Vorbis/OGG данные
            peer_ip: IP адрес отправителя (для логирования)
        """
        if not ogg_data:
            return

        try:
            # Добавляем в очередь воспроизведения
            self.playback_queue.put_nowait(ogg_data)

            # Логируем размер очереди
            queue_size = self.playback_queue.qsize()
            if queue_size % 20 == 0:
                logger.debug(f'Очередь: {queue_size}/{self.PLAYBACK_QUEUE_SIZE}')

        except:
            # Очередь полна - удаляем старые пакеты
            try:
                for _ in range(5):
                    self.playback_queue.get_nowait()
                self.playback_queue.put_nowait(ogg_data)
                logger.warning('Очередь переполнена, удалено 5 старых пакетов')
            except:
                logger.warning(f'Пропущен пакет от {peer_ip}')

    def _playback_loop(self) -> None:
        """
        Поток воспроизведения с суммированием аудиопотоков.

        Алгоритм (из статьи Habr):
        1. Собираем все доступные пакеты из очереди (non-blocking)
        2. Декодируем каждый из Vorbis → numpy array
        3. СУММИРУЕМ все arrays (это позволяет слышать всех одновременно!)
        4. Конвертируем обратно в PCM и воспроизводим
        """
        logger.info('Поток воспроизведения запущен (суммирование потоков)')

        while self.running:
            try:
                # ========== Собираем все доступные пакеты ==========
                packets = []

                # Читаем все что есть в очереди (non-blocking)
                while True:
                    try:
                        ogg_data = self.playback_queue.get_nowait()
                        packets.append(ogg_data)
                    except Empty:
                        # Очередь пуста - выходим из цикла
                        break

                # Если нет пакетов - ждем
                if not packets:
                    time.sleep(0.01)
                    continue

                # ========== Декодируем и суммируем ==========
                summed_audio = None

                for ogg_data in packets:
                    try:
                        # Декодируем Vorbis → numpy array
                        byte_io = io.BytesIO(ogg_data)
                        audio_float, _ = sf.read(byte_io)

                        # Суммируем потоки (ключевая фича!)
                        if summed_audio is None:
                            summed_audio = audio_float.copy()
                        else:
                            # Убеждаемся что размеры совпадают
                            min_len = min(len(summed_audio), len(audio_float))
                            summed_audio = summed_audio[:min_len] + audio_float[:min_len]

                    except Exception as e:
                        logger.warning(f'Ошибка декодирования пакета: {e}')
                        continue

                if summed_audio is None:
                    continue

                # ========== Конвертируем и воспроизводим ==========
                try:
                    # float32 [-1.0, 1.0] → int16 [-32768, 32767]
                    audio_int16 = (summed_audio * 32768.0).astype(np.int16)

                    # Воспроизводим
                    self.output_stream.write(audio_int16.tobytes())

                    # Логируем количество суммированных потоков
                    if len(packets) > 1:
                        logger.debug(f'Суммировано {len(packets)} аудиопотоков')

                except OSError as e:
                    logger.warning(f'OSError при воспроизведении: {e}')
                    continue
                except Exception as e:
                    logger.error(f'Ошибка при воспроизведении: {e}')
                    continue

            except Exception as e:
                logger.error(f'Ошибка в playback loop: {e}')
                time.sleep(0.1)

        logger.info('Поток воспроизведения остановлен')

    def melody(self, stop_event) -> None:
        """
        Воспроизведение тестовой мелодии через Vorbis кодек.

        Args:
            stop_event: Event для остановки воспроизведения
        """
        import array
        import math

        # Нотная последовательность (частота, длительность)
        notes = [
            (261.63, 0.2),  # C4
            (293.66, 0.2),  # D4
            (329.63, 0.2),  # E4
            (349.23, 0.2),  # F4
            (392.00, 0.2),  # G4
            (440.00, 0.2),  # A4
            (493.83, 0.2),  # B4
            (523.25, 0.2),  # C5
        ]

        volume = 0.0  # Отключена по умолчанию (0.0-1.0)

        logger.info('Мелодия запущена (для тестирования)')

        while not stop_event.is_set():
            for freq, duration in notes:
                if stop_event.is_set():
                    break

                # Генерация синусоидального сигнала
                frames = array.array('h')  # signed short (int16)
                samples_count = int(self.RATE * duration)

                for i in range(samples_count):
                    # Плавное нарастание/затухание (envelope)
                    t = i / samples_count
                    if t < 0.1:
                        envelope = t / 0.1
                    elif t > 0.9:
                        envelope = 1 - (t - 0.9) / 0.1
                    else:
                        envelope = 1.0
                    envelope = max(0.0, min(1.0, envelope))

                    # Генерация семпла
                    sample = int(32767 * volume * envelope * math.sin(2 * math.pi * freq * i / self.RATE))
                    frames.append(sample)

                # Конвертируем в bytes
                raw_pcm = frames.tobytes()

                # Кодируем в Vorbis и воспроизводим
                try:
                    # Конвертируем в numpy для soundfile
                    signal = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32)
                    signal = signal / 32768.0

                    # Сжимаем в Vorbis
                    byte_io = io.BytesIO()
                    sf.write(byte_io, signal, self.RATE, format='OGG')
                    ogg_data = bytes(byte_io.getbuffer())

                    # Воспроизводим через обычный механизм
                    self.play_audio(ogg_data, peer_ip='melody')
                except Exception as e:
                    logger.debug(f'Ошибка генерации мелодии: {e}')

            time.sleep(0.2)

        logger.info('Мелодия остановлена')

    def _cleanup(self) -> None:
        """Безопасная очистка ресурсов."""
        logger.info('Cleanup AudioHandler...')

        # Останавливаем поток воспроизведения
        self.running = False

        if hasattr(self, 'playback_thread') and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)

        # Закрываем PyAudio потоки
        if self.input_stream:
            try:
                if self.input_stream.is_active():
                    self.input_stream.stop_stream()
                self.input_stream.close()
            except Exception as e:
                logger.warning(f'Ошибка закрытия input stream: {e}')
            finally:
                self.input_stream = None

        if self.output_stream:
            try:
                if self.output_stream.is_active():
                    self.output_stream.stop_stream()
                self.output_stream.close()
            except Exception as e:
                logger.warning(f'Ошибка закрытия output stream: {e}')
            finally:
                self.output_stream = None

        # Завершаем PyAudio
        if self.pa:
            try:
                self.pa.terminate()
            except Exception as e:
                logger.warning(f'Ошибка terminate PyAudio: {e}')
            finally:
                self.pa = None

        logger.success('Cleanup завершен')

    def __del__(self) -> None:
        """Деструктор."""
        try:
            self._cleanup()
        except:
            pass
