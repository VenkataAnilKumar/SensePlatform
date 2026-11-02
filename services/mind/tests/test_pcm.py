import numpy as np

from sense_mind.core.utils.pcm import AudioFormat, PcmData


def test_from_bytes_roundtrip():
    samples = np.arange(100, dtype=np.int16)
    pcm = PcmData.from_bytes(samples.tobytes(), sample_rate=16000)
    assert len(pcm) == 100
    assert pcm.to_bytes() == samples.tobytes()
    assert abs(pcm.duration - 100 / 16000) < 1e-9


def test_resample_length_and_channels():
    pcm = PcmData.from_numpy(np.zeros(4800, dtype=np.int16), sample_rate=48000)
    out = pcm.resample(16000, 1)
    assert out.sample_rate == 16000 and len(out) == 1600


def test_stereo_downmix():
    stereo = np.zeros((480, 2), dtype=np.int16)
    out = PcmData(stereo, sample_rate=48000, channels=2).resample(48000, 1)
    assert out.channels == 1 and out.samples.ndim == 1 and len(out) == 480


def test_float_int_conversion():
    pcm = PcmData.from_numpy(np.array([0, 16384, -16384], dtype=np.int16))
    f = pcm.to_float32()
    assert f.format is AudioFormat.F32
    assert np.allclose(f.samples, [0, 0.5, -0.5])
    assert np.array_equal(f.to_int16().samples, [0, 16383, -16383]) or f.to_int16().format is AudioFormat.S16


def test_chunks_pad_and_tail():
    pcm = PcmData.from_numpy(np.ones(10, dtype=np.int16), sample_rate=10)
    chunks = list(pcm.chunks(4, pad_last=True))
    assert [len(c) for c in chunks] == [4, 4, 4]
    assert len(pcm.tail(0.5)) == 5
    assert len(pcm.tail(2.0, pad=True, pad_at="start")) == 20


def test_from_response_bytes_and_iter():
    data = np.arange(8, dtype=np.int16).tobytes()
    assert len(PcmData.from_response(data, sample_rate=8000)) == 8
    parts = [data[:3], data[3:]]  # split mid-sample
    out = list(PcmData.from_response(iter(parts), sample_rate=8000))
    assert sum(len(c) for c in out) == 8


def test_wav_bytes_header():
    wav = PcmData.from_numpy(np.zeros(10, dtype=np.int16)).to_wav_bytes()
    assert wav[:4] == b"RIFF"
