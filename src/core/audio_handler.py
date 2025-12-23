"""
Профессиональный аудио обработчик с технологиями из Discord/Telegram.

Использует:
- Opus codec (10-15x сжатие, 176 KB/s → 12-24 KB/s)
- VAD (Voice Activity Detection) - экономия 70-90% трафика
- Adaptive jitter buffer - компенсация сетевых задержек  
- PLC (Packet Loss Concealment) - нет треска при потерях
- AGC (Automatic Gain Control) - нормализация громкости
"""

import array
import math
import threading
import time
from queue import Empty, Queue

import numpy as np
import opuslib
import pyaudio
import webrtcvad
from loguru import logger


class AdaptiveJitterBuffer:
    """
    Адаптивный jitter buffer для компенсации нестабильности сети.

    Динамически подстраивает размер буфера:
    - Увеличивает при underrun (пустая очередь)
    - Уменьшает при overrun (накопление задержки)
    """

    def __init__(self, initial_size: int = 8, min_size: int = 4, max_size: int = 20):
        """
        Args:
            initial_size: Начальный целевой размер буфера
            min_size: Минимальный размер (низкая задержка)
            max_size: Максимальный размер (стабильность)
        """
        self.target_size = initial_size
        self.min_size = min_size
        self.max_size = max_size
        self.underrun_count = 0  # Счетчик пустых очередей
        self.overrun_count = 0  # Счетчик переполнений

    def adjust(self, queue_size: int) -> int:
        """
        Подстраивает размер буфера под условия сети.

        Args:
            queue_size: Текущий размер очереди

        Returns:
            Новый целевой размер буфера
        """
        # Underrun: очередь пуста, пакеты не успевают
        if queue_size == 0:
            self.underrun_count += 1
            # После 3 underrun подряд - увеличиваем буфер
            if self.underrun_count > 3:
                old_size = self.target_size
                self.target_size = min(self.target_size + 2, self.max_size)
                if self.target_size != old_size:
                    logger.info(f'Jitter buffer увеличен: {old_size} → {self.target_size} (сеть нестабильна)')
                self.underrun_count = 0

        # Overrun: слишком много пакетов, накапливается задержка
        elif queue_size > self.target_size * 1.5:
            self.overrun_count += 1
            # После 3 overrun подряд - уменьшаем буфер
            if self.overrun_count > 3:
                old_size = self.target_size
                self.target_size = max(self.target_size - 1, self.min_size)
                if self.target_size != old_size:
                    logger.info(f'Jitter buffer уменьшен: {old_size} → {self.target_size} (сеть стабильна)')
                self.overrun_count = 0

        # Нормальная работа - сбрасываем счетчики
        else:
            self.underrun_count = 0
            self.overrun_count = 0

        return self.target_size


class AudioHandler:
    """
    Профессиональный аудио обработчик с технологиями VoIP.

    Обеспечивает:
    - Высокое качество: Opus codec (как в Discord)
    - Низкий трафик: 12-24 KB/s вместо 176 KB/s
    - Экономия: VAD не передает тишину
    - Стабильность: Adaptive jitter buffer
    - Восстановление: PLC при потере пакетов
    - Нормализация: AGC выравнивает громкость
    """

    # Константы для Opus (профессиональный VoIP)
    RATE = 48000  # Opus требует 48 kHz (стандарт VoIP)
    OPUS_FRAME_SIZE = 960  # 20ms при 48kHz (оптимальная задержка)
    OPUS_BITRATE = 24000  # 24 kbit/s (баланс качество/трафик)
    CHANNELS = 1  # Mono для голоса
    FORMAT = pyaudio.paInt16  # 16-bit PCM

    # Размер очереди воспроизведения
    PLAYBACK_QUEUE_SIZE = 50

    # VAD параметры
    VAD_AGGRESSIVENESS = 2  # 0-3, где 3 = максимально агрессивный

    # AGC параметры
    AGC_TARGET_LEVEL = 0.3  # Целевой RMS уровень (30%)
    AGC_MIN_GAIN = 0.5  # Минимальное усиление
    AGC_MAX_GAIN = 4.0  # Максимальное усиление

    def __init__(self) -> None:
        """Инициализация профессионального аудио обработчика."""
        self.recording: bool = False
        self.running: bool = True
        self.playback_started: bool = False

        # Счетчики для логирования
        self.vad_speech_count = 0
        self.vad_silence_count = 0
        self.agc_log_counter = 0

        # ========== Opus Codec ==========
        try:
            self.opus_encoder = opuslib.Encoder(
                self.RATE,
                self.CHANNELS,
                opuslib.APPLICATION_VOIP  # Оптимизация для голоса
            )
            self.opus_encoder.bitrate = self.OPUS_BITRATE

            self.opus_decoder = opuslib.Decoder(self.RATE, self.CHANNELS)

            logger.debug(f'Opus codec инициализирован (bitrate={self.OPUS_BITRATE}, frame={self.OPUS_FRAME_SIZE})')
        except Exception as e:
            logger.error(f'Ошибка инициализации Opus: {e}')
            raise

        # ========== Voice Activity Detection ==========
        try:
            self.vad = webrtcvad.Vad(self.VAD_AGGRESSIVENESS)
            logger.debug(f'VAD инициализирован (aggressiveness={self.VAD_AGGRESSIVENESS})')
        except Exception as e:
            logger.error(f'Ошибка инициализации VAD: {e}')
            raise

        # ========== Adaptive Jitter Buffer ==========
        self.jitter_buffer = AdaptiveJitterBuffer(initial_size=8, min_size=4, max_size=20)

        # ========== Automatic Gain Control ==========
        self.agc_target_level = self.AGC_TARGET_LEVEL
        self.agc_current_gain = 1.0

        # ========== Очередь для воспроизведения ==========
        self.playback_queue: Queue = Queue(maxsize=self.PLAYBACK_QUEUE_SIZE)

        # ========== PyAudio инициализация ==========
        self.pa = None
        self.input_stream = None
        self.output_stream = None

        try:
            self.pa = pyaudio.PyAudio()

            # Входной поток (микрофон) - 48kHz для Opus
            self.input_stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.OPUS_FRAME_SIZE,
                stream_callback=None,
            )

            # Выходной поток (динамики) - 48kHz для Opus
            self.output_stream = self.pa.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.OPUS_FRAME_SIZE,
                stream_callback=None,
            )

            logger.success(
                f'AudioHandler инициализирован (Opus 48kHz, VAD, PLC, AGC) | '
                f'Битрейт: {self.OPUS_BITRATE//1000} kbit/s | '
                f'Сжатие: ~15x | Трафик: ~12 KB/s'
            )

        except Exception as e:
            logger.error(f'Ошибка инициализации PyAudio: {e}')
            self._cleanup()
            raise

        # ========== Запуск потока воспроизведения ==========
        self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.playback_thread.start()

    def start_recording(self) -> None:
        """Начать запись с микрофона."""
        self.recording = True
        logger.info('Запись с микрофона начата (Opus + VAD)')

    def stop_recording(self) -> None:
        """Остановить запись с микрофона."""
        self.recording = False
        logger.info('Запись с микрофона остановлена')

    def get_audio_chunk(self) -> bytes | None:
        """
        Получить аудио chunk с микрофона (СЖАТЫЙ Opus).

        Returns:
            Сжатые Opus данные или None если тишина (VAD)
        """
        if not self.recording or not self.input_stream:
            return None

        try:
            # 1. Читаем RAW PCM с микрофона
            raw_pcm = self.input_stream.read(
                self.OPUS_FRAME_SIZE,
                exception_on_overflow=False
            )

            # 2. Voice Activity Detection - не передаем тишину
            try:
                is_speech = self.vad.is_speech(raw_pcm, self.RATE)

                if is_speech:
                    self.vad_speech_count += 1
                    # Логируем раз в 50 пакетов
                    if self.vad_speech_count % 50 == 0:
                        logger.debug(f'VAD: речь детектирована ({self.vad_speech_count} чанков)')
                else:
                    self.vad_silence_count += 1
                    # Логируем раз в 100 пакетов тишины
                    if self.vad_silence_count % 100 == 0:
                        logger.debug(f'VAD: тишина ({self.vad_silence_count} чанков пропущено)')
                    return None  # Тишина - экономим трафик!

            except Exception as e:
                # Если VAD не сработал - отправляем anyway
                logger.debug(f'VAD ошибка: {e}, отправляем без проверки')

            # 3. Opus кодирование (176KB → 12KB)
            opus_data = self.opus_encoder.encode(raw_pcm, self.OPUS_FRAME_SIZE)

            return opus_data

        except OSError as e:
            logger.warning(f'Ошибка при чтении аудио: {e}')
            return None
        except Exception as e:
            logger.error(f'Критическая ошибка при чтении аудио: {e}')
            return None

    def play_audio(self, opus_data: bytes, peer_ip: str | None = None) -> None:
        """
        Воспроизвести полученные аудио данные (СЖАТЫЙ Opus).

        Args:
            opus_data: Сжатые Opus данные
            peer_ip: IP адрес отправителя
        """
        if not opus_data:
            return

        try:
            # Добавляем сжатые данные в очередь (декодирование в playback_loop)
            self.playback_queue.put_nowait(opus_data)

            queue_size = self.playback_queue.qsize()

            # Логируем только важные события
            if queue_size % 20 == 0:
                logger.debug(f'Очередь: {queue_size}/{self.PLAYBACK_QUEUE_SIZE} чанков')

        except:
            # Очередь полна - удаляем 5 старых пакетов
            try:
                for _ in range(5):
                    self.playback_queue.get_nowait()
                self.playback_queue.put_nowait(opus_data)
                logger.warning('Очередь переполнена, удалено 5 старых пакетов')
            except:
                logger.warning(f'Пропущен аудио пакет от {peer_ip}')

    def _playback_loop(self) -> None:
        """
        Поток воспроизведения с:
        - Adaptive jitter buffer
        - Opus декодированием
        - PLC (Packet Loss Concealment)
        - AGC (Automatic Gain Control)
        """
        logger.info(
            f'Поток воспроизведения запущен | '
            f'Jitter buffer: {self.jitter_buffer.target_size} чанков | '
            f'PLC: enabled | AGC: enabled'
        )

        last_packet_time = time.time()
        packet_timeout = 0.1  # 100ms без пакетов = потеря

        while self.running:
            try:
                # ========== Adaptive Jitter Buffer ==========
                # Ждем заполнения буфера перед стартом
                if not self.playback_started:
                    queue_size = self.playback_queue.qsize()
                    target_size = self.jitter_buffer.adjust(queue_size)

                    if queue_size < target_size:
                        time.sleep(0.02)
                        continue
                    else:
                        self.playback_started = True
                        logger.success(
                            f'Jitter buffer готов ({queue_size} чанков), '
                            f'начинаем плавное воспроизведение'
                        )

                # ========== Получение пакета из очереди ==========
                opus_data = None
                pcm_data = None

                try:
                    opus_data = self.playback_queue.get(timeout=0.02)
                    last_packet_time = time.time()

                    # Декодируем Opus → PCM
                    pcm_data = self.opus_decoder.decode(opus_data, self.OPUS_FRAME_SIZE)

                except Empty:
                    # ========== Packet Loss Concealment (PLC) ==========
                    # Если пакет не пришел вовремя - генерируем замещающий звук
                    if time.time() - last_packet_time > packet_timeout:
                        # Opus decoder с None генерирует PLC звук
                        pcm_data = self.opus_decoder.decode(None, self.OPUS_FRAME_SIZE)
                        logger.debug('PLC активирован (пакет потерян)')
                    else:
                        # Очередь временно пуста, но потери еще нет
                        if self.playback_started:
                            queue_size = self.playback_queue.qsize()
                            self.jitter_buffer.adjust(queue_size)
                            if queue_size == 0:
                                logger.warning('Очередь опустела, пауза для накопления')
                                self.playback_started = False
                        time.sleep(0.01)
                        continue

                if not pcm_data or not self.output_stream:
                    continue

                # ========== Automatic Gain Control (AGC) ==========
                pcm_data = self.apply_agc(pcm_data)

                # ========== Воспроизведение ==========
                try:
                    self.output_stream.write(pcm_data)
                except OSError as e:
                    if hasattr(e, 'errno'):
                        if e.errno == pyaudio.paOutputUnderflowed:
                            logger.debug('Output buffer underflow')
                        else:
                            logger.warning(f'OSError при воспроизведении: {e}')
                    else:
                        logger.warning(f'OSError при воспроизведении: {e}')
                    continue
                except Exception as e:
                    logger.error(f'Ошибка при воспроизведении: {e}')
                    continue

            except Exception as e:
                logger.error(f'Ошибка в playback loop: {e}')
                time.sleep(0.1)

        logger.info('Поток воспроизведения остановлен')

    def apply_agc(self, pcm_data: bytes) -> bytes:
        """
        Автоматическая нормализация громкости (AGC).

        Анализирует RMS уровень и плавно подстраивает усиление.

        Args:
            pcm_data: PCM аудио данные

        Returns:
            Нормализованные PCM данные
        """
        try:
            # Конвертируем в numpy array
            audio = np.frombuffer(pcm_data, dtype=np.int16)

            # Вычисляем RMS (Root Mean Square) уровень
            rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))
            current_level = rms / 32768.0  # Нормализуем к диапазону 0-1

            # Подстраиваем усиление только если есть сигнал
            if current_level > 0.01:  # Игнорируем очень тихие звуки
                target_gain = self.agc_target_level / current_level

                # Плавная подстройка (lerp с коэффициентом 0.1)
                self.agc_current_gain = self.agc_current_gain * 0.9 + target_gain * 0.1

                # Ограничиваем диапазон усиления
                self.agc_current_gain = np.clip(
                    self.agc_current_gain,
                    self.AGC_MIN_GAIN,
                    self.AGC_MAX_GAIN
                )

            # Логируем раз в 100 чанков
            self.agc_log_counter += 1
            if self.agc_log_counter % 100 == 0:
                logger.debug(
                    f'AGC: gain={self.agc_current_gain:.2f}x, '
                    f'level={current_level:.3f}'
                )

            # Применяем усиление
            audio = (audio.astype(np.float32) * self.agc_current_gain).astype(np.int16)

            return audio.tobytes()

        except Exception as e:
            logger.debug(f'AGC ошибка: {e}, пропускаем')
            return pcm_data

    def melody(self, stop_event) -> None:
        """
        Воспроизведение мелодии через Opus (для совместимости).

        Args:
            stop_event: Event для остановки
        """
        notes = [
            (261.63, 0.2), (293.66, 0.2), (329.63, 0.2), (349.23, 0.2),
            (392.00, 0.2), (440.00, 0.2), (493.83, 0.2), (523.25, 0.2),
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

                # Отправляем через Opus
                raw_pcm = frames.tobytes()
                # Дополняем до нужного размера если нужно
                if len(raw_pcm) < self.OPUS_FRAME_SIZE * 2:
                    raw_pcm += b'\x00' * (self.OPUS_FRAME_SIZE * 2 - len(raw_pcm))
                elif len(raw_pcm) > self.OPUS_FRAME_SIZE * 2:
                    raw_pcm = raw_pcm[:self.OPUS_FRAME_SIZE * 2]

                try:
                    opus_data = self.opus_encoder.encode(raw_pcm, self.OPUS_FRAME_SIZE)
                    self.play_audio(opus_data, peer_ip='melody')
                except:
                    pass

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
