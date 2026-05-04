"""
ALEX — Speech-to-Text (whisper.cpp via pywhispercpp)
On-demand: model is loaded only when called, released after transcription.
Audio is recorded via sounddevice and fed as FFT data to the overlay.
"""

import os
import tempfile
import time
import wave
import struct
import numpy as np
import sounddevice as sd
from queue import Queue

import config
from utils.helpers import get_logger

logger = get_logger()


class WhisperSTT:
    """
    Records audio via sounddevice, transcribes using whisper.cpp (base model).
    The whisper model is loaded on demand and unloaded after each transcription.
    """

    def __init__(self, audio_fft_queue: Queue = None):
        """
        Args:
            audio_fft_queue: Optional queue to push FFT data for UI overlay.
        """
        self._fft_queue = audio_fft_queue
        self._sample_rate = config.SAMPLE_RATE
        self._max_seconds = config.RECORD_MAX_SECONDS
        self._silence_thresh = config.SILENCE_THRESHOLD
        self._silence_dur = config.SILENCE_DURATION
        self._num_bars = 64

    def listen_and_transcribe(self, timeout_override: int = None) -> str:
        """
        Record audio from the microphone until silence is detected,
        then transcribe using whisper.cpp. Returns the transcribed text.

        Args:
            timeout_override: Override max recording seconds (for continuous mode).
        """
        logger.info("Recording started... (speak now)")
        audio_data = self._record_audio(timeout_override=timeout_override)

        if audio_data is None or len(audio_data) == 0:
            logger.warning("No audio captured.")
            return ""

        # Save to temp WAV
        tmp_path = self._save_wav(audio_data)

        try:
            # Load whisper model on demand
            logger.info(f"Loading whisper.cpp model '{config.WHISPER_MODEL}'...")
            text = self._transcribe(tmp_path)
            logger.info(f"Transcription: {text}")
            return text.strip()
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _record_audio(self, timeout_override: int = None) -> np.ndarray | None:
        """
        Record audio from the default microphone.
        Stops on silence detection AFTER speech is first detected.
        If no speech within timeout, returns None without transcribing.
        Pushes FFT data to overlay queue in real-time.
        """
        max_seconds = timeout_override or self._max_seconds
        frames = []
        silence_counter = 0
        speech_detected = False
        max_silence_frames = int(
            self._silence_dur * self._sample_rate / 1024
        )
        max_total_frames = int(
            max_seconds * self._sample_rate / 1024
        )

        frame_count = 0

        def callback(indata, frame_count_sd, time_info, status):
            nonlocal silence_counter, frame_count, speech_detected
            if status:
                logger.debug(f"Audio status: {status}")

            chunk = indata[:, 0].copy()
            frames.append(chunk)
            frame_count += 1

            # Compute RMS for silence detection
            rms = np.sqrt(np.mean(chunk ** 2))

            if rms >= self._silence_thresh:
                speech_detected = True
                silence_counter = 0
            else:
                if speech_detected:
                    # Only count silence AFTER speech has started
                    silence_counter += 1

            # Push FFT data to overlay
            if self._fft_queue is not None:
                try:
                    windowed = chunk * np.hanning(len(chunk))
                    fft_raw = np.abs(np.fft.rfft(windowed))
                    fft_binned = self._bin_fft(fft_raw, self._num_bars)
                    fft_max = fft_binned.max()
                    if fft_max > 0:
                        fft_binned = fft_binned / fft_max
                    self._fft_queue.put_nowait(fft_binned)
                except Exception:
                    pass

        try:
            with sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                blocksize=1024,
                callback=callback,
            ):
                logger.info("Listening... (waiting for speech)")
                while True:
                    time.sleep(0.05)
                    # Only stop for silence AFTER speech was detected
                    if speech_detected and silence_counter >= max_silence_frames:
                        logger.info("Silence after speech, stopping.")
                        break
                    # Timeout with no speech at all → return None
                    if not speech_detected and frame_count >= max_total_frames:
                        logger.info("Timeout: no speech detected.")
                        return None
                    # Max duration even with speech
                    if frame_count >= max_total_frames:
                        logger.info("Max recording duration reached.")
                        break

        except sd.PortAudioError as e:
            logger.error(f"Audio device error: {e}")
            return None

        if not frames or not speech_detected:
            return None

        return np.concatenate(frames)

    def _bin_fft(self, fft_data: np.ndarray, num_bins: int) -> np.ndarray:
        """Reduce FFT data to a fixed number of bins by averaging."""
        n = len(fft_data)
        if n < num_bins:
            # Pad with zeros if fewer FFT bins than display bars
            padded = np.zeros(num_bins)
            padded[:n] = fft_data
            return padded
        bin_size = n // num_bins
        binned = np.array([
            np.mean(fft_data[i * bin_size : (i + 1) * bin_size])
            for i in range(num_bins)
        ])
        return binned

    def _save_wav(self, audio: np.ndarray) -> str:
        """Save numpy audio array to a temporary WAV file."""
        tmp = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, dir=config.PROJECT_ROOT
        )
        tmp_path = tmp.name
        tmp.close()

        # Convert float32 to int16
        audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)

        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_int16.tobytes())

        logger.debug(f"Saved recording to {tmp_path} ({len(audio)} samples)")
        return tmp_path

    def _transcribe(self, audio_path: str) -> str:
        """
        Load whisper.cpp model, transcribe the audio file, then unload.
        Uses pywhispercpp for the actual inference.
        """
        try:
            from pywhispercpp.model import Model as WhisperModel

            model = WhisperModel(config.WHISPER_MODEL, print_realtime=False)
            segments = model.transcribe(audio_path)
            text = " ".join(seg.text for seg in segments)

            # Explicitly delete to free memory
            del model
            logger.info("Whisper model unloaded.")
            return text

        except ImportError:
            logger.error(
                "pywhispercpp not installed. "
                "Install with: pip install pywhispercpp"
            )
            return ""
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""
