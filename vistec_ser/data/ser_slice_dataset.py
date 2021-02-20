from typing import Callable

import pandas as pd
import torch
import torchaudio
from torch.utils.data import Dataset
from torchaudio.compliance import kaldi
from tqdm import tqdm

from .features.padding import pad_dup
from .features.transform import NormalizeSample


class SERSliceDataset(Dataset):
    """Speech Emotion Recognition Dataset
    Storing all dataset in RAM
    """

    def __init__(
            self,
            csv_file: str,
            max_len: int,
            len_thresh: float = 0.5,
            pad_fn: Callable = pad_dup,
            sampling_rate: int = 16000,
            center_feats: bool = True,
            scale_feats: bool = False,
            vad: bool = False,  # experimental
            transform=None):
        """
        Args:
            csv_file (string): Path to the csv file with annotations.
            max_len (int): Maximum length (in second) of audio file. Others will be truncated
            len_thresh (int): A threshold to cut audio sample that duration is shorter than provided length (in second)
            pad_fn (Callable): padding function from vistec_ser.data.features.padding
            sampling_rate (int): target sampling rate of audio. If this isn't match with file's sampling rate,
                result will be resampled into target sampling rate
            transform (callable, optional): Optional transform to be applied
                on a sample.
        """
        assert isinstance(csv_file, str)
        assert isinstance(max_len, int)
        assert isinstance(sampling_rate, int)
        self.sampling_rate = sampling_rate
        self.max_len = max_len
        self.len_thresh = len_thresh
        self.pad_fn = pad_fn
        self.transform = transform
        self.normalize = NormalizeSample(center_feats, scale_feats)
        if vad:
            self.vad = torchaudio.transforms.Vad(sample_rate=self.sampling_rate, trigger_level=6)
        else:
            self.vad = None
        self.samples = self._load_csv(csv_file)

    def _chop_sample(self, sample):
        x, y = sample["feature"], sample["emotion"]
        _, time_dim = x.shape
        x_chopped = list()
        for i in range(time_dim):
            if i % self.max_len == 0 and i != 0:  # if reach self.max_len
                xi = x[:, i - self.max_len:i]
                assert xi.shape[-1] == self.max_len, xi.shape
                x_chopped.append(self.normalize({"feature": xi, "emotion": y}))
        if time_dim < self.max_len:  # if file length not reach self.max_len
            if self.pad_fn:
                xi = self.pad_fn(x, max_len=self.max_len)
                assert xi.shape[-1] == self.max_len
            else:
                xi = x
            x_chopped.append(self.normalize({"feature": xi, "emotion": y}))
        else:  # if file is longer than n_frame, pad remainder
            remainder = x[:, x.shape[-1] - x.shape[0] % self.max_len:]
            if not remainder.shape[-1] <= self.len_thresh:
                if self.pad_fn:
                    xi = self.pad_fn(remainder, max_len=self.max_len)
                else:
                    xi = x
                x_chopped.append(self.normalize({"feature": xi, "emotion": y}))
        return x_chopped

    def _load_feature(self, audio_path):
        audio, sample_rate = torchaudio.backend.sox_backend.load(audio_path)

        # initial preprocess
        # convert to mono, resample, truncate
        audio = torch.unsqueeze(audio.mean(dim=0), dim=0)  # convert to mono
        if self.vad:
            audio = self.vad(self.vad(audio).flip(dims=[1])).flip(dims=[1])  # this VAD is quite slow
        if sample_rate != self.sampling_rate:
            audio = kaldi.resample_waveform(audio, orig_freq=sample_rate, new_freq=self.sampling_rate)
        return audio

    def _load_csv(self, csv_file):
        csv = pd.read_csv(csv_file)
        print("Extracting Features...")
        samples = []
        for i, (path, emotion) in tqdm(csv.iterrows(), total=len(csv)):
            sample = self.transform({"feature": self._load_feature(path), "emotion": emotion})
            samples += self._chop_sample(sample)
        return samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()
        return self.samples[idx]


class SERSliceTestDataset(SERSliceDataset):
    def __init__(
            self,
            csv_file: str,
            center_feats: bool = True,
            scale_feats: bool = False,
            transform=None):
        super().__init__(
            csv_file=csv_file,
            max_len=-1,
            center_feats=center_feats,
            scale_feats=scale_feats,
            transform=transform)

    def _load_csv(self, csv_file):
        csv = pd.read_csv(csv_file)
        print("Extracting Features...")
        samples = []
        for i, (path, emotion) in tqdm(csv.iterrows(), total=len(csv)):
            sample = {"feature": self._load_feature(path), "emotion": emotion}
            samples += [self.normalize(self.transform(sample))]
        return samples
