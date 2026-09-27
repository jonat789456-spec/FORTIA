from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageOps


IMAGE_SIZE = (16, 16)


def _as_image(value: str | Path | Image.Image | np.ndarray) -> Image.Image:
    if isinstance(value, (str, Path)):
        return Image.open(value)
    if isinstance(value, Image.Image):
        return value
    array = np.asarray(value)
    if array.dtype != np.uint8:
        if array.size and array.max() <= 1.0:
            array = array * 255
        array = np.clip(array, 0, 255).astype(np.uint8)
    if array.ndim == 2:
        return Image.fromarray(array, mode="L")
    return Image.fromarray(array[:, :, :3], mode="RGB")


def image_feature(value: str | Path | Image.Image | np.ndarray) -> np.ndarray:
    image = _as_image(value)
    try:
        image = ImageOps.exif_transpose(image).convert("RGB").resize(IMAGE_SIZE)
        array = np.asarray(image, dtype=np.float32) / 255.0
        return array.reshape(-1)
    finally:
        if isinstance(value, (str, Path)):
            image.close()


def crops_feature(values: Iterable[str | Path | Image.Image | np.ndarray]) -> np.ndarray:
    matrix = np.vstack([image_feature(value) for value in values])
    return np.concatenate([matrix.mean(axis=0), matrix.std(axis=0)]).reshape(1, -1)


def sequence_feature(values: Iterable[str | Path | Image.Image | np.ndarray]) -> np.ndarray:
    vectors = [image_feature(value) for value in list(values)[:6]]
    if not vectors:
        raise ValueError("La secuencia necesita al menos un frame")
    vectors.extend([np.zeros_like(vectors[0])] * (6 - len(vectors)))
    return np.concatenate(vectors).reshape(1, -1)


def single_image_feature(value: str | Path | Image.Image | np.ndarray) -> np.ndarray:
    return image_feature(value).reshape(1, -1)

