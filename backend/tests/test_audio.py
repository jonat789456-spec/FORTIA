import numpy as np

from app.audio.capture import AudioConfig, mel_spectrogram


def test_mel_spectrogram_shape() -> None:
    config = AudioConfig(duration_sec=0.25)
    result = mel_spectrogram(np.zeros(int(config.sample_rate * config.duration_sec)), config)
    assert result.shape[0] == config.n_mels
    assert result.shape[1] > 0

